from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect
from .models import Produit
import urllib.parse

def accueil(request):
    type_filtre = request.GET.get('type', 'tous')
    produits = Produit.objects.filter(actif=True)
    if type_filtre != 'tous':
        produits = produits.filter(type=type_filtre)

    context = {
        'produits': produits,
        'type_filtre': type_filtre,
        'whatsapp_number': settings.WHATSAPP_NUMBER,
    }
    return render(request, 'boutique/accueil.html', context)

def detail_produit(request, pk):
    produit = get_object_or_404(Produit, pk=pk, actif=True)
    whatsapp_number = settings.WHATSAPP_NUMBER

    # Générer le lien WhatsApp avec message pré-rempli
    message = (
        f"Bonjour ! Je souhaite rejoindre / contacter : *{produit.nom}*\n"
        f"📍 {produit.quartier}, {produit.ville}\n"
        f"💰 Montant : {produit.prix_formate()}\n"
        f"Merci de me donner le numéro de dépôt pour procéder au paiement."
    )
    whatsapp_url = f"https://wa.me/{whatsapp_number}?text={urllib.parse.quote(message)}"

    context = {
        'produit': produit,
        'whatsapp_url': whatsapp_url,
    }
    return render(request, 'boutique/detail.html', context)

def whatsapp_redirect(request, pk):
    """API appelée au clic sur 'Contacter' — renvoie l'URL WhatsApp"""
    produit = get_object_or_404(Produit, pk=pk, actif=True)
    whatsapp_number = settings.WHATSAPP_NUMBER

    message = (
        f"Bonjour ! Je souhaite rejoindre / contacter : *{produit.nom}*\n"
        f"📍 {produit.quartier}, {produit.ville}\n"
        f"💰 Montant : {produit.prix_formate()}\n"
        f"Paiement : Orange Money ou Moov Money\n"
        f"Merci de me donner le numéro de dépôt."
    )
    whatsapp_url = f"https://wa.me/{whatsapp_number}?text={urllib.parse.quote(message)}"
    return JsonResponse({'url': whatsapp_url})

def connexion(request):
    if request.method == 'POST':
        telephone = request.POST.get('telephone', '')
        password = request.POST.get('password', '')
        # On utilise le téléphone comme username
        user = authenticate(request, username=telephone, password=password)
        if user:
            login(request, user)
            return redirect('accueil')
        return render(request, 'boutique/connexion.html', {'erreur': True})
    return render(request, 'boutique/connexion.html')

def deconnexion(request):
    logout(request)
    return redirect('accueil')
