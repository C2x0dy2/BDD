"""
Modèles pour la plateforme e-commerce SÎKÂ.

Ce module contient tous les modèles de données pour la plateforme e-commerce SÎKÂ,
permettant la gestion des utilisateurs, produits, commandes, paniers, etc.
"""
from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid


class User(AbstractUser):
    """
    Modèle utilisateur étendu pour la plateforme SÎKÂ.
    
    Hérite de AbstractUser de Django et ajoute des champs spécifiques à notre plateforme.
    Gère les utilisateurs clients et vendeurs avec leurs informations respectives.
    """
    # Informations personnelles de base
    email = models.EmailField(unique=True)  # Email unique obligatoire
    first_name = models.CharField(max_length=150, blank=True)  # Prénom
    last_name = models.CharField(max_length=150, blank=True)  # Nom de famille
    phone = models.CharField(max_length=20, blank=True)  # Téléphone personnel
    address = models.TextField(blank=True)  # Adresse personnelle
    
    # Statuts utilisateur
    is_seller = models.BooleanField(
        default=False,
        help_text="Indique si l'utilisateur est un vendeur"
    )
    is_seller_approved = models.BooleanField(
        default=False,
        help_text="Indique si le vendeur a été approuvé par l'administrateur"
    )
    is_email_verified = models.BooleanField(
        default=False,
        help_text="Indique si l'email a été vérifié via le lien d'activation"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Date de création du compte"
    )
    
    # Champs spécifiques aux vendeurs
    # Ces champs sont remplis lors de l'inscription avec l'option "Devenir vendeur"
    store_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Nom de la boutique du vendeur"
    )
    store_description = models.TextField(
        blank=True,
        help_text="Description de la boutique"
    )
    store_phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="Numéro de téléphone professionnel"
    )
    store_address = models.TextField(
        blank=True,
        help_text="Adresse de la boutique"
    )
    identity_photo = models.ImageField(
        upload_to='sellers/identity/',
        blank=True,
        null=True,
        help_text="Photo d'identité du vendeur (requis pour validation)"
    )

    class Meta:
        verbose_name = 'Utilisateur'
        verbose_name_plural = 'Utilisateurs'

    def __str__(self):
        """Retourne le nom d'utilisateur pour l'affichage."""
        return self.username


class Category(models.Model):
    """
    Modèle de catégorie pour organiser les produits.
    
    Permet de regrouper les produits par catégories (ex: Électronique, Vêtements, etc.)
    Chaque catégorie a un slug unique pour les URLs SEO-friendly.
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Nom de la catégorie (ex: Électronique, Vêtements)"
    )
    slug = models.SlugField(
        max_length=100,
        unique=True,
        help_text="URL-friendly version du nom (auto-généré)"
    )
    description = models.TextField(
        blank=True,
        help_text="Description détaillée de la catégorie"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Date de création de la catégorie"
    )

    class Meta:
        verbose_name_plural = 'Catégories'

    def __str__(self):
        """Retourne le nom de la catégorie."""
        return self.name


class Tag(models.Model):
    """
    Modèle de tag/mot-clé pour les produits.
    
    Permet de taguer les produits avec des mots-clés pour faciliter la recherche
    et l'organisation (ex: "promo", "nouveau", "bestseller").
    """
    name = models.CharField(
        max_length=50,
        unique=True,
        help_text="Nom du tag/mot-clé"
    )
    slug = models.SlugField(
        max_length=50,
        unique=True,
        help_text="Version URL-friendly du tag"
    )

    def __str__(self):
        """Retourne le nom du tag."""
        return self.name


class SellerRequest(models.Model):
    """
    Modèle de demande d'inscription pour devenir vendeur.
    
    Quand un utilisateur veut devenir vendeur, une demande est créée avec ses informations
    et soumise à l'administration pour approbation. Le statut évolue de "pending" à 
    "approved" ou "rejected".
    """
    STATUS_CHOICES = [
        ('pending', 'En attente'),  # Demande en attente de validation
        ('approved', 'Approuvé'),   # Demande acceptée par l'admin
        ('rejected', 'Rejeté'),     # Demande refusée par l'admin
    ]
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='seller_request',
        help_text="Utilisateur demandant le statut de vendeur"
    )
    store_name = models.CharField(
        max_length=100,
        help_text="Nom de la boutique"
    )
    description = models.TextField(
        help_text="Description de l'activité de vente"
    )
    phone = models.CharField(
        max_length=20,
        help_text="Numéro de téléphone professionnel"
    )
    address = models.TextField(
        help_text="Adresse de la boutique/activité"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text="Statut de la demande de vendeur"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Date de soumission de la demande"
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date de traitement de la demande par l'administrateur"
    )

    class Meta:
        verbose_name = 'Demande Vendeur'
        verbose_name_plural = 'Demandes Vendeurs'

    def __str__(self):
        """Retourne le nom de la boutique et son statut."""
        return f"{self.store_name} - {self.get_status_display()}"


class Product(models.Model):
    """
    Modèle de produit pour la plateforme e-commerce.
    
    Contient toutes les informations d'un produit vendu sur la plateforme :
    nom, description, prix, images, catégorie, tags, vendeur, stock, etc.
    Le slug est auto-généré pour créer des URLs SEO-friendly.
    """
    name = models.CharField(
        max_length=200,
        help_text="Nom du produit"
    )
    slug = models.SlugField(
        max_length=200,
        unique=True,
        help_text="URL-friendly version du nom (auto-généré)"
    )
    description = models.TextField(
        help_text="Description détaillée du produit"
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Prix du produit en FCFA"
    )
    image = models.ImageField(
        upload_to='products/',
        default='products/default.jpg',
        help_text="Image principale du produit"
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        related_name='products',
        help_text="Catégorie du produit"
    )
    tags = models.ManyToManyField(
        Tag,
        blank=True,
        help_text="Tags/mots-clés associés au produit"
    )
    seller = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='products',
        help_text="Vendeur propriétaire du produit"
    )
    stock = models.PositiveIntegerField(
        default=0,
        help_text="Quantité en stock disponible"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Indique si le produit est actif et visible"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Date de création du produit"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Date de dernière modification"
    )

    class Meta:
        ordering = ['-created_at']  # Plus récents en premier
        indexes = [
            models.Index(fields=['-created_at']),  # Index pour tri rapide
            models.Index(fields=['slug']),  # Index pour recherche slug
        ]

    def __str__(self):
        """Retourne le nom du produit."""
        return self.name

    def save(self, *args, **kwargs):
        """
        Génère automatiquement un slug unique si non fourni ou s'il est dupliqué.
        
        Cette méthode s'assure que chaque produit a un slug unique pour l'URL.
        Si le slug existe déjà, on ajoute un suffixe aléatoire.
        """
        from django.utils.text import slugify
        import random
        import string
        
        # Générer le slug si non défini ou vide
        if not self.slug or self.slug == '':
            # Créer le slug à partir du nom
            base_slug = slugify(self.name)
            self.slug = base_slug
            
            # Vérifier si le slug existe, ajouter suffixe aléatoire si nécessaire
            slug_is_new = self.pk is None  # Produit nouveau ou existant ?
            
            if slug_is_new:
                # Création d'un nouveau produit - vérifier existence du slug
                while Product.objects.filter(slug=self.slug).exists():
                    # Générer 6 caractères aléatoires
                    random_suffix = ''.join(random.choices(
                        string.ascii_lowercase + string.digits, k=6
                    ))
                    self.slug = f"{base_slug}-{random_suffix}"
            else:
                # Mise à jour d'un produit existant - exclure lui-même
                while Product.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                    random_suffix = ''.join(random.choices(
                        string.ascii_lowercase + string.digits, k=6
                    ))
                    self.slug = f"{base_slug}-{random_suffix}"
        
        super().save(*args, **kwargs)


class ProductImage(models.Model):
    """
    Modèle d'images additionnelles pour un produit.
    
    Un produit peut avoir jusqu'à 5 images additionnelles affichées en carrousel.
    L'image principale est stockée dans Product.image, les autres images ici.
    Permet d'afficher plusieurs vues d'un même produit.
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='additional_images',
        help_text="Produit associé à cette image"
    )
    image = models.ImageField(
        upload_to='products/additional/',
        help_text="Image additionnelle du produit"
    )
    is_primary = models.BooleanField(
        default=False,
        help_text="Marque l'image comme principale (usage futur)"
    )
    order = models.PositiveIntegerField(
        default=0,
        help_text="Ordre d'affichage de l'image"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Date d'ajout de l'image"
    )

    class Meta:
        ordering = ['order', '-is_primary', 'created_at']  # Ordre d'affichage
        verbose_name = 'Image Produit'
        verbose_name_plural = 'Images Produits'

    def __str__(self):
        """Retourne une description de l'image."""
        return f"Image pour {self.product.name}"


# Les avis produits (ex-ProductReview) sont stockés dans MongoDB, pas ici --
# voir api/reviews/mongo_client.py. product.id et user.id restent la
# référence partagée entre les deux bases.


class Cart(models.Model):
    """
    Modèle de panier d'achat.
    
    Chaque utilisateur a un panier unique contenant plusieurs articles (CartItem).
    Le panier est créé automatiquement au premier ajout et persiste jusqu'à
    la validation en commande ou la suppression.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='carts',
        help_text="Utilisateur propriétaire du panier"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Date de création du panier"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Date de dernière modification"
    )

    def get_total(self):
        """
        Calcule le total de tous les articles dans le panier.
        
        Additionne le total de chaque item (prix × quantité).
        """
        total = sum(item.get_total() for item in self.items.all())
        return total

    def __str__(self):
        """Retourne le panier avec le nom d'utilisateur."""
        return f"Panier - {self.user.username}"


class CartItem(models.Model):
    """
    Modèle d'article individuel dans le panier.
    
    Représente un produit avec sa quantité dans le panier d'un utilisateur.
    Il ne peut y avoir qu'un seul CartItem par produit dans un panier donné.
    Si l'utilisateur ajoute à nouveau le même produit, la quantité est incrémentée.
    """
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items',
        help_text="Panier contenant cet article"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='cart_items',
        help_text="Produit ajouté au panier"
    )
    quantity = models.PositiveIntegerField(
        default=1,
        help_text="Quantité du produit dans le panier"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Date d'ajout au panier"
    )

    def get_total(self):
        """
        Calcule le total pour cet article.
        
        Retourne le prix unitaire × la quantité.
        """
        return self.product.price * self.quantity

    class Meta:
        unique_together = ['cart', 'product']  # Un seul item par produit par panier

    def __str__(self):
        """Retourne la quantité et le nom du produit."""
        return f"{self.quantity}x {self.product.name}"


class Order(models.Model):
    """
    Modèle de commande validée.
    
    Quand un client valide son panier, une commande est créée avec :
    - Numéro unique auto-généré (ORD-XXXXXXXX)
    - Statut de suivi (pending, confirmed, shipped, delivered, cancelled)
    - Méthode de paiement et détails spécifiques
    - Adresse de livraison et coordonnées
    - Historique complet pour le vendeur et le client
    """
    STATUS_CHOICES = [
        ('pending', 'En attente'),      # Commande en attente de traitement
        ('confirmed', 'Confirmée'),     # Confirmée par le vendeur
        ('shipped', 'Expédiée'),        # Expédiée au client
        ('delivered', 'Livrée'),        # Livrée au client
        ('cancelled', 'Annulée'),       # Annulée
    ]
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Espèces'),                    # Paiement en espèces à la livraison
        ('mobile_money', 'Mobile Money'),       # Paiement mobile money (MTN, Orange, Moov)
        ('bank_transfer', 'Virement bancaire'), # Virement bancaire
        ('credit_card', 'Carte de crédit'),     # Carte bancaire
        ('wave', 'Wave'),                       # Wave
    ]
    
    MOBILE_MONEY_PROVIDER_CHOICES = [
        ('momo', 'MTN Mobile Money'),   # MTN Mobile Money
        ('orange', 'Orange Money'),     # Orange Money
        ('moov', 'Moov Money'),         # Moov Money
    ]

    order_number = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        help_text="Numéro unique de commande (auto-généré)"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='orders',
        help_text="Client auteur de la commande"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending',
        help_text="Statut actuel de la commande"
    )
    payment_method = models.CharField(
        max_length=20, choices=PAYMENT_METHOD_CHOICES,
        help_text="Méthode de paiement choisie"
    )
    mobile_money_provider = models.CharField(
        max_length=20,
        choices=MOBILE_MONEY_PROVIDER_CHOICES,
        blank=True,
        null=True,
        help_text="Opérateur si paiement mobile money"
    )
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Montant total de la commande en FCFA"
    )
    delivery_address = models.TextField(
        help_text="Adresse complète de livraison"
    )
    phone = models.CharField(
        max_length=20,
        help_text="Numéro de téléphone pour la livraison"
    )
    notes = models.TextField(
        blank=True,
        help_text="Notes additionnelles du client"
    )
    
    # Informations de paiement
    payment_status = models.CharField(
        max_length=20,
        choices=[('pending', 'En attente'), ('paid', 'Payé'), ('failed', 'Échoué')],
        default='pending',
        help_text="Statut du paiement"
    )
    payment_reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="Référence du paiement (numéro transaction, etc.)"
    )
    
    # Informations carte de crédit (stockées de manière sécurisée)
    card_last_four = models.CharField(
        max_length=4,
        blank=True,
        help_text="4 derniers chiffres de la carte"
    )
    card_brand = models.CharField(
        max_length=20,
        blank=True,
        help_text="Type de carte (Visa, Mastercard)"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Date de création de la commande"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Date de dernière modification"
    )

    class Meta:
        ordering = ['-created_at']  # Plus récentes en premier

    def save(self, *args, **kwargs):
        """
        Génère automatiquement un numéro de commande unique si non fourni.
        
        Format: ORD-XXXXXXXX (8 caractères hexadécimaux en majuscules)
        """
        if not self.order_number:
            self.order_number = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def get_total(self):
        """
        Calcule le total de tous les articles de la commande.
        
        Additionne le total de chaque OrderItem.
        Note: Le total est aussi stocké dans total_amount pour l'historique.
        """
        total = sum(item.get_total() for item in self.items.all())
        return total

    def __str__(self):
        """Retourne le numéro de commande et l'utilisateur."""
        return f"Commande {self.order_number} - {self.user.username}"


class Wishlist(models.Model):
    """
    Modèle de liste de souhaits (favoris).
    
    Permet aux utilisateurs de sauvegarder des produits qu'ils souhaitent
    acheter plus tard. Toggle via bouton cœur dans l'interface.
    Un produit ne peut être ajouté qu'une seule fois par utilisateur.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='wishlist',
        help_text="Utilisateur propriétaire de la wishlist"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='wishlist_items',
        help_text="Produit ajouté aux favoris"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Date d'ajout aux favoris"
    )

    class Meta:
        unique_together = ['user', 'product']  # Un seul ajout par produit
        ordering = ['-created_at']  # Plus récents en premier
        verbose_name = 'Article Wishlist'
        verbose_name_plural = 'Articles Wishlist'

    def __str__(self):
        """Retourne l'utilisateur et le produit favori."""
        return f"{self.user.username} - {self.product.name}"


class OrderItem(models.Model):
    """
    Modèle d'article individuel dans une commande.
    
    Représente un produit avec sa quantité et son prix au moment de la commande.
    Le prix est stocké pour conserver l'historique même si le prix du produit
    change après la commande. Si le produit est supprimé, OrderItem reste
    avec une référence null au produit.
    """
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
        help_text="Commande contenant cet article"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        help_text="Produit commandé (peut être null si produit supprimé)"
    )
    quantity = models.PositiveIntegerField(
        help_text="Quantité commandée"
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Prix unitaire au moment de la commande"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Date de création de l'article de commande"
    )

    def get_total(self):
        """
        Calcule le total pour cet article.
        
        Retourne le prix unitaire × la quantité.
        """
        return self.price * self.quantity

    def __str__(self):
        """Retourne la quantité et le nom du produit."""
        return f"{self.quantity}x {self.product.name if self.product else 'Produit supprimé'}"