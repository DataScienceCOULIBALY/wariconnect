# 🇧🇫 WariConnect — Guide de déploiement complet

Plateforme de mise en relation (personnes + groupes WhatsApp/Telegram) pour le Burkina Faso.

---

## 🗂️ Structure du projet

```
wariconnect/
├── wariconnect/          # Config Django
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── boutique/             # Application principale
│   ├── models.py         # Modèle Produit
│   ├── views.py          # Pages et logique
│   ├── admin.py          # Panel admin
│   ├── urls.py           # Routes
│   └── templates/boutique/
│       ├── accueil.html  # Page principale
│       └── connexion.html
├── media/                # Photos uploadées (auto-créé)
├── .github/workflows/    # CI/CD GitHub
├── requirements.txt
├── Procfile              # Pour Railway
├── railway.toml
└── .env.example          # Modèle de config
```

---

## 🚀 Installation locale (ton PC)

### 1. Prérequis
- Python 3.11+
- Git

### 2. Cloner et installer
```bash
git clone https://github.com/TON-USERNAME/wariconnect.git
cd wariconnect
python -m venv venv
source venv/bin/activate   # Mac/Linux
venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

### 3. Configurer l'environnement
```bash
cp .env.example .env
# Ouvre .env et remplis tes valeurs
```

### 4. Base de données locale (SQLite pour tester)
Dans `settings.py`, remplace temporairement DATABASES par :
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
```

### 5. Lancer
```bash
python manage.py migrate
python manage.py createsuperuser   # crée ton compte admin
python manage.py runserver
```

Ouvre http://127.0.0.1:8000 → site
Ouvre http://127.0.0.1:8000/admin → panel admin

---

## 🗄️ Supabase (base de données gratuite)

1. Va sur https://supabase.com → **New Project**
2. Note ton mot de passe
3. Va dans **Settings > Database**
4. Copie les infos dans ton `.env` :
   - `DB_HOST` = Host (commence par `db.`)
   - `DB_NAME` = `postgres`
   - `DB_USER` = `postgres`
   - `DB_PASSWORD` = ton mot de passe
   - `DB_PORT` = `5432`

---

## 🚂 Railway (hébergement gratuit)

1. Va sur https://railway.app → connecte ton GitHub
2. **New Project > Deploy from GitHub repo**
3. Sélectionne ton repo `wariconnect`
4. Dans **Variables**, ajoute toutes les variables de ton `.env` :
   - `SECRET_KEY`
   - `DEBUG=False`
   - `ALLOWED_HOSTS=*.railway.app`
   - `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
   - `WHATSAPP_NUMBER=22670000000` ← ton vrai numéro
5. Railway déploie automatiquement ! ✅

### Après le premier déploiement
Dans Railway, ouvre un terminal et exécute :
```bash
python manage.py migrate
python manage.py createsuperuser
```

---

## 🔄 GitHub (CI/CD automatique)

1. Crée un repo sur https://github.com
2. Dans ton dossier local :
```bash
git init
git add .
git commit -m "🚀 Premier commit WariConnect"
git remote add origin https://github.com/TON-USERNAME/wariconnect.git
git push -u origin main
```
3. Chaque push sur `main` → tests automatiques → Railway redéploie 🎉

---

## 📲 Utilisation du panel admin

1. Va sur `ton-site.railway.app/admin`
2. Connecte-toi avec ton superuser
3. Clique sur **Produits > Ajouter un produit**
4. Remplis : Type (Personne / WhatsApp / Telegram), Nom, Photo, Ville, Quartier, Prix
5. Coche **Actif** → apparaît sur le site immédiatement

---

## 💬 Flux WhatsApp

Quand un visiteur clique "Choisir" :
1. Il voit la fiche avec le prix
2. Il clique "Contacter via WhatsApp"
3. Il est redirigé sur **ton WhatsApp** avec ce message pré-rempli :
   ```
   Bonjour ! Je souhaite rejoindre / contacter : *NOM*
   📍 Quartier, Ville
   💰 Montant : X FCFA
   Paiement : Orange Money ou Moov Money
   Merci de me donner le numéro de dépôt.
   ```
4. Tu reçois le message, tu envoies ton numéro de dépôt, tu confirmes le paiement.

---

## 🔑 Variables d'environnement (résumé)

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Clé secrète Django (génère sur https://djecrety.ir) |
| `DEBUG` | `False` en production |
| `ALLOWED_HOSTS` | Domaine Railway (ex: `*.railway.app`) |
| `DB_*` | Infos Supabase |
| `WHATSAPP_NUMBER` | Ton numéro sans + ni espaces (ex: `22670123456`) |

---

## 💰 Coût total : 0 FCFA

- Django : gratuit
- Supabase : gratuit (500 MB)
- Railway : gratuit (500h/mois)
- GitHub : gratuit
- Tu paies uniquement quand tu encaisses ! 🎉
