import os
import urllib.parse
from functools import wraps
from datetime import datetime
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

db = SQLAlchemy(app)

# ── Modèles ─────────────────────────────────────────────
class Produit(db.Model):
    __tablename__ = 'boutique_produit'
    id          = db.Column(db.Integer, primary_key=True)
    type        = db.Column(db.String(20), default='personne')
    nom         = db.Column(db.String(200))
    photo       = db.Column(db.String(300), nullable=True)
    ville       = db.Column(db.String(100))
    quartier    = db.Column(db.String(100), nullable=True)
    prix        = db.Column(db.Integer)
    description = db.Column(db.Text, nullable=True)
    actif       = db.Column(db.Boolean, default=True)
    ordre       = db.Column(db.Integer, default=0)
    cree_le     = db.Column(db.DateTime, default=datetime.utcnow)

    def prix_formate(self):
        return f"{self.prix:,} FCFA".replace(",", " ")

    def emoji(self):
        return {'personne': '👤', 'whatsapp': '💬', 'telegram': '✈️'}.get(self.type, '👤')

    def type_display(self):
        return {'personne': '👤 Personne', 'whatsapp': '💬 Groupe WhatsApp', 'telegram': '✈️ Groupe Telegram'}.get(self.type, self.type)


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
    type_filtre = request.args.get('type', 'tous')
    query = Produit.query.filter_by(actif=True)
    if type_filtre != 'tous':
        query = query.filter_by(type=type_filtre)
    produits = query.order_by(Produit.ordre, Produit.cree_le.desc()).all()
    return render_template('boutique/accueil.html',
                           produits=produits,
                           type_filtre=type_filtre,
                           whatsapp_number=WHATSAPP_NUMBER,
                           user=session.get('user'))

@app.route('/whatsapp/<int:pk>')
def whatsapp_redirect(pk):
    produit = Produit.query.filter_by(id=pk, actif=True).first_or_404()
    message = (
        f"Bonjour ! Je souhaite rejoindre / contacter : *{produit.nom}*\n"
        f"📍 {produit.quartier}, {produit.ville}\n"
        f"💰 Montant : {produit.prix_formate()}\n"
        f"Paiement : Orange Money ou Moov Money\n"
        f"Merci de me donner le numéro de dépôt."
    )
    whatsapp_url = f"https://wa.me/{WHATSAPP_NUMBER}?text={urllib.parse.quote(message)}"
    return jsonify({'url': whatsapp_url})

@app.route('/connexion', methods=['GET', 'POST'])
def connexion():
    if request.method == 'POST':
        telephone = request.form.get('telephone', '')
        password  = request.form.get('password', '')
        user = User.query.filter_by(username=telephone, is_active=True).first()
        if user and check_password_hash(user.password, password):
            session['user'] = user.username
            return redirect(url_for('accueil'))
        return render_template('boutique/connexion.html', erreur=True)
    return render_template('boutique/connexion.html', erreur=False)

@app.route('/deconnexion')
def deconnexion():
    session.pop('user', None)
    return redirect(url_for('accueil'))


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
    produits = Produit.query.order_by(Produit.ordre, Produit.cree_le.desc()).all()
    total    = Produit.query.count()
    actifs   = Produit.query.filter_by(actif=True).count()
    return render_template('admin/dashboard.html', produits=produits, total=total, actifs=actifs)

@app.route('/admin/produit/nouveau', methods=['GET', 'POST'])
@admin_required
def admin_nouveau():
    if request.method == 'POST':
        produit = Produit(
            type        = request.form.get('type', 'personne'),
            nom         = request.form.get('nom', ''),
            photo       = request.form.get('photo', '') or None,
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
        produit.photo       = request.form.get('photo', '') or None
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
