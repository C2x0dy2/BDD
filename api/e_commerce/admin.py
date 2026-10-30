from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import (
    User, Product, Category, Tag, Cart, CartItem, Order,
    OrderItem, SellerRequest, ProductImage, Wishlist
)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """Interface d'administration pour les utilisateurs."""
    list_display = [
        'username', 'email', 'first_name', 'last_name',
        'is_seller', 'is_seller_approved', 'is_email_verified', 'date_joined'
    ]
    list_filter = [
        'is_seller', 'is_seller_approved', 'is_email_verified', 'is_staff', 'is_active'
    ]
    search_fields = ['username', 'email', 'first_name', 'last_name']
    readonly_fields = ['date_joined', 'last_login']
    fieldsets = (
        ('Informations personnelles', {
            'fields': ('username', 'email', 'first_name', 'last_name',
                       'phone', 'address')
        }),
        ('Statut', {
            'fields': ('is_seller', 'is_seller_approved', 'is_email_verified',
                       'is_active', 'is_staff', 'is_superuser')
        }),
        ('Permissions', {
            'fields': ('groups', 'user_permissions'),
            'classes': ('collapse',),
        }),
        ('Dates', {
            'fields': ('date_joined', 'last_login'),
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """
        Surcharge la méthode save pour détecter l'approbation d'un vendeur
        et envoyer un email de confirmation.
        """
        # Si l'objet existe déjà (modification)
        if change:
            # Récupérer l'ancienne version depuis la base de données
            old_obj = User.objects.get(pk=obj.pk)
            old_is_seller_approved = old_obj.is_seller_approved
            old_is_seller = old_obj.is_seller
            
            # Si is_seller_approved passe de False à True
            if not old_is_seller_approved and obj.is_seller_approved:
                # S'assurer que is_seller est aussi True
                obj.is_seller = True
                
                # Envoyer un email de confirmation
                from .utils import send_seller_status_notification
                send_seller_status_notification(obj, 'approved', request)
            
            # Si is_seller_approved est coché mais que is_seller n'est pas coché
            # S'assurer que is_seller est aussi True
            if obj.is_seller_approved and not obj.is_seller:
                obj.is_seller = True
        
        # Sauvegarder l'objet
        super().save_model(request, obj, form, change)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Interface d'administration pour les catégories."""
    list_display = ['name', 'slug', 'product_count', 'created_at']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}

    def product_count(self, obj):
        """Compte le nombre de produits dans la catégorie."""
        return obj.products.count()
    product_count.short_description = 'Nombre de produits'


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    """Interface d'administration pour les tags."""
    list_display = ['name', 'slug']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(SellerRequest)
class SellerRequestAdmin(admin.ModelAdmin):
    """Interface d'administration pour les demandes vendeur."""
    list_display = [
        'user', 'store_name', 'status', 'phone', 'created_at'
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['user__username', 'store_name', 'store_name']
    readonly_fields = ['user', 'created_at', 'reviewed_at']
    actions = ['approve_requests', 'reject_requests']
    
    def save_model(self, request, obj, form, change):
        """
        Surcharge la méthode save pour détecter les changements de statut
        et envoyer les emails appropriés.
        """
        from .utils import send_seller_status_notification
        
        # Si l'objet existe déjà (modification)
        if change:
            # Récupérer l'ancienne version depuis la base de données
            old_obj = SellerRequest.objects.get(pk=obj.pk)
            old_status = old_obj.status
            new_status = obj.status
            
            # Si le statut change vers 'approved'
            if old_status != 'approved' and new_status == 'approved':
                obj.reviewed_at = timezone.now()
                # Mettre à jour le statut de l'utilisateur
                obj.user.is_seller = True
                obj.user.is_seller_approved = True
                obj.user.save()
                # Envoyer un email de confirmation avec lien de connexion
                send_seller_status_notification(obj.user, 'approved', request)
            
            # Si le statut change vers 'rejected'
            elif old_status != 'rejected' and new_status == 'rejected':
                obj.reviewed_at = timezone.now()
                # Envoyer un email de refus
                send_seller_status_notification(obj.user, 'rejected', request)
            
            # Si le statut change mais n'est ni approved ni rejected
            elif old_status != new_status:
                obj.reviewed_at = timezone.now()
        
        # Sauvegarder l'objet
        super().save_model(request, obj, form, change)

    def approve_requests(self, request, queryset):
        """Approuve les demandes vendeur sélectionnées."""
        from .utils import send_seller_status_notification
        
        for seller_request in queryset:
            seller_request.status = 'approved'
            seller_request.reviewed_at = timezone.now()
            seller_request.save()
            
            # Mettre à jour le statut de l'utilisateur
            seller_request.user.is_seller = True
            seller_request.user.is_seller_approved = True
            seller_request.user.save()
            
            # Envoyer un email de confirmation avec lien de connexion
            send_seller_status_notification(
                seller_request.user,
                'approved',
                request
            )
        
        self.message_user(
            request,
            f'{queryset.count()} demande(s) approuvée(s) avec succès. '
            'Les utilisateurs ont été notifiés par email.'
        )
    approve_requests.short_description = 'Approuver les demandes sélectionnées'

    def reject_requests(self, request, queryset):
        """Rejette les demandes vendeur sélectionnées."""
        from .utils import send_seller_status_notification
        
        for seller_request in queryset:
            seller_request.status = 'rejected'
            seller_request.reviewed_at = timezone.now()
            seller_request.save()
            
            # Envoyer un email de refus
            send_seller_status_notification(
                seller_request.user,
                'rejected',
                request
            )
        
        self.message_user(
            request,
            f'{queryset.count()} demande(s) rejetée(s). '
            'Les utilisateurs ont été notifiés par email.'
        )
    reject_requests.short_description = 'Rejeter les demandes sélectionnées'


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Interface d'administration pour les produits."""
    list_display = [
        'name', 'seller', 'price', 'stock', 'category',
        'is_active', 'created_at'
    ]
    list_filter = ['is_active', 'category', 'created_at']
    search_fields = ['name', 'description', 'seller__username']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['seller', 'created_at', 'updated_at']
    filter_horizontal = ['tags']
    fieldsets = (
        ('Informations de base', {
            'fields': ('name', 'slug', 'description', 'price')
        }),
        ('Visuels', {
            'fields': ('image', 'category')
        }),
        ('Mots-clés', {
            'fields': ('tags',)
        }),
        ('Stock', {
            'fields': ('stock', 'is_active')
        }),
        ('Vendeur', {
            'fields': ('seller',)
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


class OrderItemInline(admin.TabularInline):
    """Administration inline pour les articles de commande."""
    model = OrderItem
    extra = 0
    readonly_fields = ['product', 'quantity', 'price']
    fk_name = 'order'


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Interface d'administration pour les commandes."""
    list_display = [
        'order_number', 'user', 'status', 'total_amount',
        'payment_method', 'created_at'
    ]
    list_filter = ['status', 'payment_method', 'created_at']
    search_fields = ['order_number', 'user__username']
    readonly_fields = ['order_number', 'created_at', 'updated_at']
    inlines = [OrderItemInline]
    fieldsets = (
        ('Informations de commande', {
            'fields': ('order_number', 'user', 'status', 'total_amount')
        }),
        ('Livraison', {
            'fields': ('delivery_address', 'phone')
        }),
        ('Paiement', {
            'fields': ('payment_method', 'notes')
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    """Interface d'administration pour les paniers."""
    list_display = ['user', 'created_at']
    readonly_fields = ['created_at', 'updated_at']
    
    def get_total(self, obj):
        """Obtient le total du panier."""
        return obj.get_total()
    get_total.short_description = 'Total'


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    """Interface d'administration pour les articles du panier."""
    list_display = ['cart', 'product', 'quantity', 'total_price']
    list_filter = ['created_at']
    readonly_fields = ['created_at']

    def total_price(self, obj):
        """Affiche le prix total pour un article du panier."""
        return f'{obj.get_total():.0f} FCFA'
    total_price.short_description = 'Total'


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    """Interface d'administration pour les images de produits."""
    list_display = ['product', 'image', 'is_primary', 'order', 'created_at']
    list_filter = ['is_primary', 'created_at']
    search_fields = ['product__name']
    readonly_fields = ['created_at']


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    """Interface d'administration pour les listes de souhaits."""
    list_display = ['user', 'product', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'product__name']
    readonly_fields = ['created_at']

# Les avis produits vivent dans MongoDB (voir api/reviews/) -- pas d'admin
# Django ici ; utiliser Mongo Express (docker/docker-compose.yml) pour les
# consulter.