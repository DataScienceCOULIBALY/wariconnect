import os
import urllib.parse
from functools import wraps
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-moi')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', '').replace('postgres://', 'postgresql://')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

WHATSAPP_NUMBER = os.environ.get('WHATSAPP_NUMBER', '22670000000')
ADMIN_PASSWORD  = os.environ.get('ADMIN_PASSWORD', 'admin123')
PUB_TEXTE       = os.environ.get('PUB_TEXTE', '')
PUB_LIEN        = os.environ.get('PUB_LIEN', '')
PUB_IMAGE       = os.environ.get('PUB_IMAGE', '')

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
    vues        = db.Column(db.Integer, default=0)
    cree_le     = db.Column(db.DateTime, default=datetime.utcnow)

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


class User(db.Model):
    __tablename__ = 'auth_user'
    id         = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(150))
    password   = db.Column(db.String(300))
    is_active  = db.Column(db.Boolean, default=True)


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
    type_filtre  = request.args.get('type', 'tous')
    recherche    = request.args.get('q', '').strip()
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
    produits = query.order_by(Produit.ordre, Produit.cree_le.desc()).all()
    pub = {'texte': PUB_TEXTE, 'lien': PUB_LIEN, 'image': PUB_IMAGE} if PUB_TEXTE else None
    return render_template('boutique/accueil.html',
                           produits=produits,
                           type_filtre=type_filtre,
                           recherche=recherche,
                           whatsapp_number=WHATSAPP_NUMBER,
                           pub=pub)

@app.route('/produit/<int:pk>')
def detail_produit(pk):
    produit = Produit.query.filter_by(id=pk, actif=True).first_or_404()
    # Incrémenter les vues
    produit.vues = (produit.vues or 0) + 1
    db.session.commit()
    message = (
        f"Bonjour ! Je souhaite rejoindre / contacter : *{produit.nom}*\n"
        f"📍 {produit.quartier or ''}, {produit.ville}\n"
        f"💰 Montant : {produit.prix_formate()}\n"
        f"Paiement : Orange Money ou Moov Money\n"
        f"Merci de me donner le numéro de dépôt."
    )
    whatsapp_url = f"https://wa.me/{WHATSAPP_NUMBER}?text={urllib.parse.quote(message)}"
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


# ── Routes Admin ─────────────────────────────────────────
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))
        return render_template('admin/login.html', erreur=True)
    return render_template('admin/login.html', erreur=False)

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
            type        = request.form.get('type', 'personne'),
            nom         = request.form.get('nom', ''),
            photos      = photos_raw or None,
            ville       = request.form.get('ville', ''),
            quartier    = request.form.get('quartier', '') or None,
            prix        = int(request.form.get('prix', 0)),
            description = request.form.get('description', '') or None,
            actif       = request.form.get('actif') == 'on',
            ordre       = int(request.form.get('ordre', 0)),
            cree_le     = datetime.utcnow(),
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
        produit.type        = request.form.get('type', 'personne')
        produit.nom         = request.form.get('nom', '')
        produit.photos      = request.form.get('photos', '') or None
        produit.ville       = request.form.get('ville', '')
        produit.quartier    = request.form.get('quartier', '') or None
        produit.prix        = int(request.form.get('prix', 0))
        produit.description = request.form.get('description', '') or None
        produit.actif       = request.form.get('actif') == 'on'
        produit.ordre       = int(request.form.get('ordre', 0))
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

@app.route('/admin/produit/<int:pk>/toggle', methods=['POST'])
@admin_required
def admin_toggle(pk):
    produit = Produit.query.get_or_404(pk)
    produit.actif = not produit.actif
    db.session.commit()
    return jsonify({'actif': produit.actif})


if __name__ == '__main__':
    app.run(debug=True)
