"""
Script executé automatiquement au démarrage pour créer le superuser.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wariconnect.settings')
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()

username = os.environ.get('ADMIN_USERNAME', 'admin')
email = os.environ.get('ADMIN_EMAIL', 'admin@wariconnect.com')
password = os.environ.get('ADMIN_PASSWORD', '')

if password and not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password)
    print(f"Superuser '{username}' créé !")
else:
    print(f"Superuser existe déjà ou ADMIN_PASSWORD manquant.")
