import os
import secrets
import hmac
import hashlib
import urllib.parse
from functools import wraps
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from werkzeug.security import check_password_hash
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', '').replace('postgres://', 'postgresql://')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_SECURE']   = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)

CLOUDINARY_URL  = os.environ.get('CLOUDINARY_URL', '')
if CLOUDINARY_URL:
    cloudinary.config(cloudinary_url=CLOUDINARY_URL)

WHATSAPP_NUMBER  = os.environ.get('WHATSAPP_NUMBER', '22670000000')
ADMIN_PASSWORD   = os.environ.get('ADMIN_PASSWORD', 'admin123')
PUB_TEXTE        = os.environ.get('PUB_TEXTE', '')
PUB_LIEN         = os.environ.get('PUB_LIEN', '')
PUB_IMAGE        = os.environ.get('PUB_IMAGE', '')

# ── Orange Money API (activer en ajoutant ces variables dans Vercel) ──
OM_CLIENT_ID      = os.environ.get('OM_CLIENT_ID', '')
OM_CLIENT_SECRET  = os.environ.get('OM_CLIENT_SECRET', '')
OM_WEBHOOK_SECRET = os.environ.get('OM_WEBHOOK_SECRET', '')
OM_CALLBACK_URL   = os.environ.get('OM_CALLBACK_URL', 'https://nongafo.vercel.app/paiement/webhook')
OM_ACTIVE         = bool(OM_CLIENT_ID and OM_CLIENT_SECRET)

db = SQLAlchemy(app)

# ── Modèles ─────────────────────────────────────────────
class Produit(db.Model):
    __tablename__ = 'boutique_produit'
    id          = db.Column(db.Integer, primary_key=True)
    type        = db.Column(db.String(20), default='personne')
    nom         = db.Column(db.String(200))
    photos      = db.Column(db.Text, nullable=True)   # URLs séparées par |
    ville       = db.Column(db.String(100))
    quartier    = db.Column(db.String(100), nullable=True)
    prix        = db.Column(db.Integer)
    description = db.Column(db.Text, nullable=True)
    actif       = db.Column(db.Boolean, default=True)
    ordre       = db.Column(db.Integer, default=0)
    vues          = db.Column(db.Integer, default=0)
    cree_le       = db.Column(db.DateTime, default=datetime.utcnow)
    whatsapp_perso= db.Column(db.String(30), nullable=True)

    def prix_formate(self):
        return f"{self.prix:,} FCFA".replace(",", " ")

    def emoji(self):
        return {'personne': '👤', 'whatsapp': '💬', 'telegram': '✈️'}.get(self.type, '👤')

    def type_display(self):
        return {'personne': '👤 Personne', 'whatsapp': '💬 Groupe WhatsApp', 'telegram': '✈️ Groupe Telegram'}.get(self.type, self.type)

    def photo_principale(self):
        if self.photos:
            return self.photos.split('|')[0].strip()
        return None

    def liste_photos(self):
        if self.photos:
            return [p.strip() for p in self.photos.split('|') if p.strip()]
        return []

    def est_nouveau(self):
        if self.cree_le:
            return datetime.utcnow() - self.cree_le < timedelta(days=7)
        return False


class TentativeLogin(db.Model):
    __tablename__ = 'tentatives_login'
    id        = db.Column(db.Integer, primary_key=True)
    ip        = db.Column(db.String(45), nullable=False)
    cree_le   = db.Column(db.DateTime, default=datetime.utcnow)


class Paiement(db.Model):
    __tablename__ = 'paiements'
    id           = db.Column(db.Integer, primary_key=True)
    profil_id    = db.Column(db.Integer, db.ForeignKey('boutique_produit.id'), nullable=False)
    numero       = db.Column(db.String(20), nullable=False)   # numéro du payeur
    montant      = db.Column(db.Integer, nullable=False)
    # en_attente | confirme | echec | expire
    statut       = db.Column(db.String(20), default='en_attente', nullable=False)
    token        = db.Column(db.String(64), unique=True, nullable=False)
    om_ref       = db.Column(db.String(100))                  # référence transaction OM
    cree_le      = db.Column(db.DateTime, default=datetime.utcnow)
    confirme_le  = db.Column(db.DateTime)
    profil       = db.relationship('Produit', backref='paiements')


class User(db.Model):
    __tablename__ = 'auth_user'
    id         = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(150))
    password   = db.Column(db.String(300))
    is_active  = db.Column(db.Boolean, default=True)


# ── Sécurité : headers + masquage stack ──────────────────

@app.after_request
def security_headers(response):
    response.headers['X-Frame-Options']        = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-XSS-Protection']       = '1; mode=block'
    response.headers['Referrer-Policy']        = 'no-referrer'
    response.headers['Permissions-Policy']     = 'geolocation=(), microphone=(), camera=()'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; "
        "img-src * data: blob:; "
        "connect-src 'self'; "
        "frame-ancestors 'none';"
    )
    response.headers.pop('Server', None)
    response.headers.pop('X-Powered-By', None)
    return response


# ── Décorateur admin ─────────────────────────────────────
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


# ── Routes publiques ─────────────────────────────────────
@app.route('/')
def accueil():
    type_filtre = request.args.get('type', 'tous')
    recherche   = request.args.get('q', '').strip()
    query = Produit.query.filter_by(actif=True)
    if type_filtre != 'tous':
        query = query.filter_by(type=type_filtre)
    if recherche:
        query = query.filter(
            db.or_(
                Produit.nom.ilike(f'%{recherche}%'),
                Produit.ville.ilike(f'%{recherche}%'),
                Produit.quartier.ilike(f'%{recherche}%'),
                Produit.description.ilike(f'%{recherche}%'),
            )
        )
    produits = query.order_by(Produit.ordre.asc(), Produit.cree_le.desc()).limit(100).all()
    pub = {'texte': PUB_TEXTE, 'lien': PUB_LIEN, 'image': PUB_IMAGE} if PUB_TEXTE else None
    return render_template('boutique/accueil.html',
                           produits=produits,
                           type_filtre=type_filtre,
                           recherche=recherche,
                           whatsapp_number=WHATSAPP_NUMBER,
                           pub=pub,
                           om_active=OM_ACTIVE)

@app.route('/produit/<int:pk>')
def detail_produit(pk):
    produit = Produit.query.filter_by(id=pk, actif=True).first_or_404()
    produit.vues = (produit.vues or 0) + 1
    db.session.commit()
    message = (
        f"Bonjour ! Je souhaite rejoindre / contacter : *{produit.nom}*\n"
        f"📍 {produit.quartier or ''}, {produit.ville}\n"
        f"💰 Montant : {produit.prix_formate()}\n"
        f"Paiement : Orange Money ou Moov Money\n"
        f"Merci de me donner le numéro de dépôt."
    )
    wa_num = produit.whatsapp_perso or WHATSAPP_NUMBER
    whatsapp_url = f"https://wa.me/{wa_num}?text={urllib.parse.quote(message)}"
    similaires = Produit.query.filter_by(actif=True, type=produit.type).filter(Produit.id != pk).limit(4).all()
    return render_template('boutique/detail.html',
                           produit=produit,
                           whatsapp_url=whatsapp_url,
                           whatsapp_number=WHATSAPP_NUMBER,
                           similaires=similaires)

@app.route('/vue/<int:pk>', methods=['POST'])
def incrementer_vue(pk):
    produit = Produit.query.get_or_404(pk)
    produit.vues = (produit.vues or 0) + 1
    db.session.commit()
    return jsonify({'vues': produit.vues})


# ── Routes Paiement Orange Money ─────────────────────────

@app.route('/paiement/initier', methods=['POST'])
def paiement_initier():
    data      = request.get_json(silent=True) or {}
    profil_id = data.get('profil_id')
    numero    = (data.get('numero') or '').strip().replace(' ', '')
    if not profil_id or not numero:
        return jsonify({'error': 'Données manquantes'}), 400

    profil = Produit.query.filter_by(id=profil_id, actif=True).first()
    if not profil:
        return jsonify({'error': 'Profil introuvable'}), 404

    token    = secrets.token_urlsafe(32)
    paiement = Paiement(profil_id=profil_id, numero=numero,
                        montant=profil.prix, token=token)
    db.session.add(paiement)
    db.session.commit()

    if OM_ACTIVE:
        pass

    return jsonify({'token': token, 'statut': 'en_attente', 'om_active': False})


@app.route('/paiement/statut/<token>')
def paiement_statut(token):
    paiement = Paiement.query.filter_by(token=token).first()
    if not paiement:
        return jsonify({'error': 'Introuvable'}), 404

    if (datetime.utcnow() - paiement.cree_le).total_seconds() > 86400:
        return jsonify({'statut': 'expire'})

    result = {'statut': paiement.statut}
    if paiement.statut == 'confirme':
        profil       = paiement.profil
        wa_num       = profil.whatsapp_perso or WHATSAPP_NUMBER
        locTxt       = f"{profil.quartier + ', ' if profil.quartier else ''}{profil.ville}"
        msg          = (f"Bonjour ! J'ai payé {profil.prix_formate()} via Orange/Moov Money "
                        f"pour contacter : *{profil.nom}*\n📍 {locTxt}\n"
                        f"Merci de m'envoyer le contact 🙏")
        result['contact']    = wa_num
        result['nom']        = profil.nom
        result['whatsapp']   = f"https://wa.me/{wa_num}?text={urllib.parse.quote(msg)}"
    return jsonify(result)


@app.route('/paiement/webhook', methods=['POST'])
def paiement_webhook():
    if OM_WEBHOOK_SECRET:
        sig      = request.headers.get('X-Orange-Signature', '')
        expected = hmac.new(OM_WEBHOOK_SECRET.encode(), request.data, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            abort(403)

    data     = request.get_json(silent=True) or {}
    order_id = (data.get('order_id') or data.get('orderId')
                or request.args.get('token', ''))
    statut   = (data.get('status') or data.get('txnstatus') or '').upper()
    om_ref   = data.get('txnid') or data.get('transactionId') or ''

    if not order_id:
        return jsonify({'error': 'order_id manquant'}), 400

    paiement = Paiement.query.filter_by(token=order_id).first()
    if not paiement:
        return jsonify({'error': 'Paiement non trouvé'}), 404

    if statut in ('SUCCESS', 'SUCCESSFULL', 'SUCCESSFUL', '200'):
        paiement.statut     = 'confirme'
        paiement.om_ref     = om_ref
        paiement.confirme_le = datetime.utcnow()
    elif statut in ('FAILED', 'CANCELLED', 'EXPIRED'):
        paiement.statut = 'echec'

    db.session.commit()
    return jsonify({'ok': True})


def get_client_ip():
    return (request.headers.get('X-Forwarded-For', '') or request.remote_addr or '').split(',')[0].strip()

def is_rate_limited(ip, max_attempts=5, window_minutes=15):
    cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
    count  = TentativeLogin.query.filter(
        TentativeLogin.ip == ip,
        TentativeLogin.cree_le >= cutoff
    ).count()
    return count >= max_attempts

def record_login_attempt(ip):
    db.session.add(TentativeLogin(ip=ip))
    db.session.commit()


# ── Routes Admin ─────────────────────────────────────────
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        ip = get_client_ip()
        if is_rate_limited(ip):
            return render_template('admin/login.html', erreur=True, bloque=True)
        if request.form.get('password') == ADMIN_PASSWORD:
            session.clear()
            session['admin']    = True
            session.permanent   = True
            return redirect(url_for('admin_dashboard'))
        record_login_attempt(ip)
        return render_template('admin/login.html', erreur=True, bloque=False)
    return render_template('admin/login.html', erreur=False, bloque=False)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('admin_login'))

@app.route('/admin')
@admin_required
def admin_dashboard():
    produits   = Produit.query.order_by(Produit.ordre, Produit.cree_le.desc()).all()
    total      = Produit.query.count()
    actifs     = Produit.query.filter_by(actif=True).count()
    total_vues = db.session.query(db.func.sum(Produit.vues)).scalar() or 0
    return render_template('admin/dashboard.html',
                           produits=produits, total=total,
                           actifs=actifs, total_vues=total_vues)

@app.route('/admin/produit/nouveau', methods=['GET', 'POST'])
@admin_required
def admin_nouveau():
    if request.method == 'POST':
        photos_raw = request.form.get('photos', '')
        produit = Produit(
            type           = request.form.get('type', 'personne'),
            nom            = request.form.get('nom', ''),
            photos         = photos_raw or None,
            ville          = request.form.get('ville', ''),
            quartier       = request.form.get('quartier', '') or None,
            prix           = int(request.form.get('prix', 0)),
            description    = request.form.get('description', '') or None,
            actif          = request.form.get('actif') == 'on',
            ordre          = int(request.form.get('ordre', 0)),
            cree_le        = datetime.utcnow(),
            whatsapp_perso = request.form.get('whatsapp_perso', '') or None,
        )
        db.session.add(produit)
        db.session.commit()
        flash('success|Produit ajouté avec succès !')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin/form.html', produit=None, titre='Nouveau produit')

@app.route('/admin/produit/<int:pk>/modifier', methods=['GET', 'POST'])
@admin_required
def admin_modifier(pk):
    produit = Produit.query.get_or_404(pk)
    if request.method == 'POST':
        produit.type           = request.form.get('type', 'personne')
        produit.nom            = request.form.get('nom', '')
        produit.photos         = request.form.get('photos', '') or None
        produit.ville          = request.form.get('ville', '')
        produit.quartier       = request.form.get('quartier', '') or None
        produit.prix           = int(request.form.get('prix', 0))
        produit.description    = request.form.get('description', '') or None
        produit.actif          = request.form.get('actif') == 'on'
        produit.ordre          = int(request.form.get('ordre', 0))
        produit.whatsapp_perso = request.form.get('whatsapp_perso', '') or None
        db.session.commit()
        flash('success|Produit modifié avec succès !')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin/form.html', produit=produit, titre='Modifier le produit')

@app.route('/admin/produit/<int:pk>/supprimer', methods=['POST'])
@admin_required
def admin_supprimer(pk):
    produit = Produit.query.get_or_404(pk)
    db.session.delete(produit)
    db.session.commit()
    flash('info|Produit supprimé.')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/upload-photo', methods=['POST'])
@admin_required
def admin_upload_photo():
    if not CLOUDINARY_URL:
        return jsonify({'error': 'Cloudinary non configuré'}), 500
    f = request.files.get('file')
    if not f:
        return jsonify({'error': 'Aucun fichier'}), 400
    try:
        result = cloudinary.uploader.upload(f, folder='wariconnect', transformation=[
            {'width': 800, 'height': 1200, 'crop': 'limit', 'quality': 'auto'}
        ])
        return jsonify({'url': result['secure_url']})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/produit/<int:pk>/toggle', methods=['POST'])
@admin_required
def admin_toggle(pk):
    produit = Produit.query.get_or_404(pk)
    produit.actif = not produit.actif
    db.session.commit()
    return jsonify({'actif': produit.actif})


def migrate_db():
    with app.app_context():
        with db.engine.connect() as conn:
            try:
                conn.execute(text('ALTER TABLE boutique_produit ADD COLUMN IF NOT EXISTS whatsapp_perso VARCHAR(30)'))
                conn.commit()
            except Exception:
                pass
            try:
                conn.execute(text('''
                    CREATE TABLE IF NOT EXISTS tentatives_login (
                        id      SERIAL PRIMARY KEY,
                        ip      VARCHAR(45) NOT NULL,
                        cree_le TIMESTAMP DEFAULT NOW()
                    )
                '''))
                conn.commit()
            except Exception:
                pass
            try:
                conn.execute(text('''
                    CREATE TABLE IF NOT EXISTS paiements (
                        id           SERIAL PRIMARY KEY,
                        profil_id    INTEGER NOT NULL REFERENCES boutique_produit(id),
                        numero       VARCHAR(20) NOT NULL,
                        montant      INTEGER NOT NULL,
                        statut       VARCHAR(20) NOT NULL DEFAULT \'en_attente\',
                        token        VARCHAR(64) NOT NULL UNIQUE,
                        om_ref       VARCHAR(100),
                        cree_le      TIMESTAMP DEFAULT NOW(),
                        confirme_le  TIMESTAMP
                    )
                '''))
                conn.commit()
            except Exception:
                pass

migrate_db()

if __name__ == '__main__':
    app.run(debug=True)
