from django.db import models

class Produit(models.Model):
    TYPE_CHOICES = [
        ('personne', '👤 Personne'),
        ('whatsapp', '💬 Groupe WhatsApp'),
        ('telegram', '✈️ Groupe Telegram'),
    ]

    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='personne', verbose_name="Type")
    nom = models.CharField(max_length=200, verbose_name="Nom / Titre")
    photo = models.ImageField(upload_to='profils/', blank=True, null=True, verbose_name="Photo")
    ville = models.CharField(max_length=100, verbose_name="Ville")
    quartier = models.CharField(max_length=100, blank=True, verbose_name="Quartier")
    prix = models.PositiveIntegerField(verbose_name="Prix (FCFA)")
    description = models.TextField(blank=True, verbose_name="Description")
    actif = models.BooleanField(default=True, verbose_name="Visible sur le site")
    ordre = models.PositiveIntegerField(default=0, verbose_name="Ordre d'affichage")
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Produit"
        verbose_name_plural = "Produits"
        ordering = ['ordre', '-cree_le']

    def __str__(self):
        return f"{self.get_type_display()} — {self.nom}"

    def prix_formate(self):
        return f"{self.prix:,} FCFA".replace(",", " ")

    def emoji(self):
        emojis = {'personne': '👤', 'whatsapp': '💬', 'telegram': '✈️'}
        return emojis.get(self.type, '👤')
