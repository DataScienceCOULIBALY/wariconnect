from django.contrib import admin
from django.utils.html import format_html
from .models import Produit

@admin.register(Produit)
class ProduitAdmin(admin.ModelAdmin):
    list_display = ['apercu_photo', 'nom', 'type', 'ville', 'quartier', 'prix_formate', 'actif', 'ordre']
    list_editable = ['actif', 'ordre']
    list_filter = ['type', 'actif', 'ville']
    search_fields = ['nom', 'ville', 'quartier']
    ordering = ['ordre', '-cree_le']

    fieldsets = (
        ('Informations principales', {
            'fields': ('type', 'nom', 'photo', 'description')
        }),
        ('Localisation', {
            'fields': ('ville', 'quartier')
        }),
        ('Prix & Visibilité', {
            'fields': ('prix', 'actif', 'ordre')
        }),
    )

    def apercu_photo(self, obj):
        if obj.photo:
            return format_html('<img src="{}" width="50" height="50" style="object-fit:cover;border-radius:8px;" />', obj.photo.url)
        return format_html('<span style="font-size:1.5rem">{}</span>', obj.emoji())
    apercu_photo.short_description = "Photo"

    def prix_formate(self, obj):
        return obj.prix_formate()
    prix_formate.short_description = "Prix"

# Personnalisation du panel admin
admin.site.site_header = "🇧🇫 WariConnect — Administration"
admin.site.site_title = "WariConnect Admin"
admin.site.index_title = "Gestion de la plateforme"
