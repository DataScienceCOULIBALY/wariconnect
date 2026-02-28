from django.urls import path
from . import views

urlpatterns = [
    path('', views.accueil, name='accueil'),
    path('produit/<int:pk>/', views.detail_produit, name='detail_produit'),
    path('api/whatsapp/<int:pk>/', views.whatsapp_redirect, name='whatsapp_redirect'),
    path('connexion/', views.connexion, name='connexion'),
    path('deconnexion/', views.deconnexion, name='deconnexion'),
]
