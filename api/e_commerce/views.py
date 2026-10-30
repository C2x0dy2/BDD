"""
Vues pour la plateforme e-commerce SÎKÂ.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView
)
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.http import JsonResponse, HttpResponse
from django.urls import reverse_lazy
from types import SimpleNamespace

from .models import (
    User, Product, Category, Tag, Cart, CartItem, Order, OrderItem,
    SellerRequest, ProductImage, Wishlist
)
from .forms import (
    CustomUserCreationForm, LoginForm, SellerRequestForm,
    ProductForm, CartItemForm, OrderForm, ContactForm, CategoryForm, ProductReviewForm
)
from .utils import (
    send_email_verification, send_order_confirmation,
    send_seller_status_notification
)
from reviews.services import (
    get_product_specs, get_user_review, list_reviews_for_product,
    rating_stats, upsert_review,
)


def home(request):
    """
    Vue de la page d'accueil.
    
    Affiche :
    - 8 produits les plus récents (featured products)
    - 6 catégories populaires (avec au moins un produit)
    - Liste des produits favoris de l'utilisateur connecté (pour afficher les cœurs remplis)
    """
    # Récupérer les 8 produits les plus récents actifs
    featured_products = Product.objects.filter(
        is_active=True
    ).order_by('-created_at')[:8]
    
    # Récupérer les 6 catégories les plus populaires (au moins 1 produit)
    categories = Category.objects.annotate(
        product_count=Count('products')
    ).filter(product_count__gt=0)[:6]
    
    # Récupérer la wishlist de l'utilisateur s'il est connecté
    # Pour afficher les boutons cœur remplis sur les produits
    user_wishlist = []
    if request.user.is_authenticated:
        user_wishlist = list(request.user.wishlist.values_list('product_id', flat=True))
    
    context = {
        'featured_products': featured_products,
        'categories': categories,
        'user_wishlist': user_wishlist,
    }
    return render(request, 'partials/home.html', context)


def product_list(request):
    """
    Vue de la liste des produits avec filtres.
    
    Permet de :
    - Lister tous les produits actifs
    - Rechercher par nom ou description (paramètre GET 'q')
    - Filtrer par catégorie (paramètre GET 'category')
    - Paginer les résultats (12 produits par page)
    - Afficher la wishlist de l'utilisateur connecté
    """
    # Base query: tous les produits actifs
    products = Product.objects.filter(is_active=True)
    
    # Recherche textuelle dans le nom ou la description
    query = request.GET.get('q')
    if query:
        products = products.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query)
        )
    
    # Filtre par catégorie via slug
    category_slug = request.GET.get('category')
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=category)
    
    # Pagination: 12 produits par page
    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Récupérer toutes les catégories pour le filtre
    categories = Category.objects.all()
    
    # Récupérer la wishlist de l'utilisateur s'il est connecté
    user_wishlist = []
    if request.user.is_authenticated:
        user_wishlist = list(request.user.wishlist.values_list('product_id', flat=True))
    
    context = {
        'page_obj': page_obj,  # Page courante avec produits
        'categories': categories,
        'query': query,  # Terme de recherche
        'selected_category': category_slug,  # Catégorie sélectionnée
        'user_wishlist': user_wishlist,  # IDs des produits favoris
    }
    return render(request, 'partials/products/list.html', context)


class ProductDetailView(DetailView):
    """
    Vue de détail d'un produit.
    
    Affiche :
    - Détails complets du produit (nom, prix, description, images, etc.)
    - Produits similaires de la même catégorie (4 max)
    - Tous les avis clients avec note moyenne
    - Formulaire pour laisser un avis (si connecté, a commandé, et pas déjà avisé)
    - État de la wishlist de l'utilisateur connecté
    """
    model = Product
    template_name = 'partials/products/detail.html'
    context_object_name = 'product'
    slug_url_kwarg = 'slug'  # Utilise le slug pour identifier le produit
    
    def get_context_data(self, **kwargs):
        """Ajoute les données supplémentaires au contexte."""
        context = super().get_context_data(**kwargs)
        
        # Produits similaires: même catégorie, exclure ce produit, limit 4
        context['related_products'] = Product.objects.filter(
            category=self.object.category,
            is_active=True
        ).exclude(id=self.object.id)[:4]
        
        # Récupérer tous les avis du produit (MongoDB) et joindre les
        # auteurs (PostgreSQL) en une seule requête groupée.
        review_docs = list_reviews_for_product(self.object.id)
        reviewers = User.objects.in_bulk([r['user_id'] for r in review_docs])
        context['reviews'] = [
            SimpleNamespace(
                id=r['id'], rating=r['rating'], comment=r['comment'],
                created_at=r['created_at'],
                user=reviewers.get(r['user_id']),
            )
            for r in review_docs
        ]

        # Note moyenne (pipeline d'agrégation MongoDB)
        stats = rating_stats(self.object.id)
        context['average_rating'] = stats['average_rating'] or 0
        context['total_reviews'] = stats['review_count']

        # Vérifier si l'utilisateur connecté a déjà laissé un avis
        if self.request.user.is_authenticated:
            existing = get_user_review(self.object.id, self.request.user.id)
            context['user_review'] = SimpleNamespace(**existing) if existing else None
            # Vérifier si l'utilisateur a commandé ce produit (obligatoire pour avis)
            context['has_ordered'] = OrderItem.objects.filter(
                order__user=self.request.user,
                product=self.object
            ).exists()
        else:
            context['user_review'] = None
            context['has_ordered'] = False

        # Formulaire pour laisser un avis
        context['review_form'] = ProductReviewForm()

        # Fiche produit enrichie (MongoDB) : attributs flexibles par
        # catégorie, non représentables par des colonnes SQL fixes.
        context['product_specs'] = get_product_specs(self.object.id)
        return context


def register(request):
    """
    Vue d'inscription d'un nouvel utilisateur.
    
    Permet de créer un compte client ou vendeur :
    - Formulaire avec option "Devenir vendeur"
    - Si vendeur: champs supplémentaires (nom boutique, description, etc.)
    - Envoi d'un email de vérification automatique
    - Ne connecte PAS l'utilisateur immédiatement (doit vérifier email)
    - Redirection vers page confirmation envoi email
    """
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST, request.FILES)
        if form.is_valid():
            # Sauvegarder l'utilisateur
            user = form.save()
            
            # Envoyer l'email de vérification (ne pas connecter encore)
            from .utils import send_email_verification
            send_email_verification(user, request)
            
            # Messages différents selon le type de compte
            if user.is_seller:
                messages.success(
                    request,
                    'Compte vendeur créé avec succès! '
                    'Veuillez vérifier votre email pour activer votre compte. '
                    'Votre demande de vendeur sera examinée par notre équipe.'
                )
            else:
                messages.success(
                    request,
                    'Compte créé avec succès! '
                    'Veuillez vérifier votre email pour activer votre compte.'
                )
            return redirect('e_commerce:verification_sent')
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'partials/accounts/register.html', {'form': form})


def verify_email(request, user_id, token):
    """
    Vue de vérification de l'email via token.
    
    Reçoit le lien de vérification envoyé par email et valide :
    - L'utilisateur existe
    - Le token est valide et non expiré (24h max)
    - Le token correspond à cet utilisateur
    
    Si valide: marque l'email comme vérifié et redirige vers login
    Si invalide: affiche erreur et redirige
    """
    from django.contrib.auth import get_user_model
    from django.core import signing
    User = get_user_model()
    
    try:
        # Convertir user_id en int (compatibilité avec différentes URL patterns)
        try:
            uid = int(user_id)
        except (TypeError, ValueError):
            uid = user_id  # Solution de secours si UUID dans une config personnalisée
        
        # Récupérer l'utilisateur
        user = User.objects.get(id=uid)

        # Valider le token signé et vérifier qu'il correspond à cet utilisateur
        # max_age: 24 heures (60 * 60 * 24)
        data = signing.loads(token, salt='email-verify', max_age=60 * 60 * 24)
        if data.get('uid') == user.id:
            # Token valide: marquer email comme vérifié
            user.is_email_verified = True
            user.save()
            messages.success(
                request,
                'Email vérifié avec succès! Vous pouvez maintenant vous connecter.'
            )
            return redirect('e_commerce:login')
        else:
            messages.error(request, 'Lien de vérification invalide ou expiré.')
            return redirect('e_commerce:home')
    except User.DoesNotExist:
        messages.error(request, 'Utilisateur introuvable.')
        return redirect('e_commerce:home')
    except signing.BadSignature:
        messages.error(request, 'Lien de vérification invalide.')
        return redirect('e_commerce:home')
    except signing.SignatureExpired:
        messages.error(request, 'Lien de vérification expiré. Veuillez redemander un email.')
        return redirect('e_commerce:verification_sent')


def verification_sent(request):
    """
    Page de confirmation d'envoi de l'email de vérification.
    
    Affichée après l'inscription pour informer l'utilisateur
    qu'un email de vérification lui a été envoyé.
    """
    return render(request, 'partials/accounts/verification_sent.html')


def user_login(request):
    """
    Vue de connexion unique avec redirection automatique selon le rôle.
    
    Cette vue authentifie l'utilisateur et le redirige automatiquement selon son rôle :
    - Vendeur → Dashboard vendeur
    - Client → Page d'accueil
    
    Permet de se connecter avec :
    - Nom d'utilisateur OU email
    - Mot de passe
    
    Validations :
    - Email doit être vérifié
    - Identifiants corrects
    
    Plus besoin de sélectionner un type de connexion, la redirection se fait automatiquement.
    """
    # Toujours fournir une instance de formulaire au template
    form = LoginForm(request.POST or None)

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        if username and password:
            # Authentifier l'utilisateur avec username ou email
            # D'abord essayer avec le username (méthode Django standard)
            user = authenticate(request, username=username, password=password)
            
            # Si échec, essayer avec l'email
            if user is None:
                try:
                    user_obj = User.objects.get(email=username)
                    if user_obj.check_password(password) and user_obj.is_active:
                        user = user_obj
                except User.DoesNotExist:
                    pass
            
            if user is not None:
                # Vérifier que l'email est vérifié (obligatoire)
                if not user.is_email_verified:
                    messages.error(
                        request,
                        'Veuillez vérifier votre email avant de vous connecter. '
                        'Consultez votre boîte de réception.'
                    )
                    return redirect('e_commerce:login')
                
                # Connecter l'utilisateur
                login(request, user)
                
                # Redirection automatique selon le rôle
                if user.is_seller:
                    messages.success(request, 'Connexion vendeur réussie!')
                    next_url = request.GET.get('next', 'e_commerce:seller_dashboard')
                else:
                    messages.success(request, 'Connexion réussie!')
                    next_url = request.GET.get('next', 'e_commerce:home')
                
                return redirect(next_url)
            else:
                messages.error(
                    request,
                    'Nom d\'utilisateur ou mot de passe incorrect.'
                )
        else:
            messages.error(request, 'Veuillez remplir tous les champs.')

    return render(request, 'partials/accounts/login.html', {'form': form})


def user_logout(request):
    """
    Vue de déconnexion.
    
    Déconnecte l'utilisateur et le redirige vers la page d'accueil
    avec un message de confirmation.
    """
    logout(request)
    messages.info(request, 'Vous avez été déconnecté.')
    return redirect('e_commerce:home')


def about(request):
    """
    Page À propos de SÎKÂ.
    
    Affiche les informations sur l'entreprise, son histoire, ses valeurs.
    """
    return render(request, 'partials/pages/about.html')


def contact(request):
    """
    Page de contact avec envoi d'email.
    
    Permet aux visiteurs d'envoyer un message de contact.
    Le message est envoyé par email à l'administration.
    """
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            from django.core.mail import send_mail
            from django.conf import settings
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            subject = form.cleaned_data['subject']
            message = form.cleaned_data['message']
            full_subject = f"[Contact SÎKÂ] {subject}"
            full_message = (
                f"Nom: {name}\nEmail: {email}\n\nMessage:\n{message}"
            )
            send_mail(full_subject, full_message, settings.DEFAULT_FROM_EMAIL or email,
                      [settings.DEFAULT_FROM_EMAIL or email], fail_silently=True)
            messages.success(request, 'Votre message a été envoyé. Merci!')
            return redirect('e_commerce:contact')
    else:
        form = ContactForm()
    return render(request, 'partials/pages/contact.html', {'form': form})


def privacy_policy(request):
    """
    Page Politique de confidentialité.
    
    Affiche les conditions d'utilisation et politique de confidentialité
    de la plateforme (RGPD, cookies, etc.).
    """
    return render(request, 'partials/pages/privacy_policy.html')


@login_required
def profile(request):
    """
    Page de profil utilisateur.
    
    Affiche les informations personnelles de l'utilisateur connecté
    (email, téléphone, adresse, etc.) avec possibilité de modification.
    """
    return render(request, 'partials/accounts/profile.html')


@login_required
def add_to_cart(request, product_id):
    """
    Ajouter un produit au panier.
    
    Validations :
    - Produit doit avoir du stock
    - Si produit déjà dans panier, incrémenter quantité
    - Vérifier que quantité totale ne dépasse pas le stock
    
    Redirige vers le panier avec message de succès ou d'erreur.
    """
    product = get_object_or_404(Product, id=product_id)
    
    # Vérifier que le stock est disponible
    if product.stock == 0:
        messages.error(request, f'{product.name} est en rupture de stock.')
        return redirect('e_commerce:product_detail', slug=product.slug)
    
    # Créer ou récupérer le panier de l'utilisateur
    cart, created = Cart.objects.get_or_create(user=request.user)
    
    # Créer ou récupérer l'article dans le panier
    cart_item, item_created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={'quantity': 1}
    )
    
    if not item_created:
        # Produit déjà dans panier: vérifier stock avant d'incrémenter
        if cart_item.quantity + 1 > product.stock:
            messages.error(request, f'Stock insuffisant. Stock disponible: {product.stock}')
            return redirect('e_commerce:cart')
        cart_item.quantity += 1
        cart_item.save()
    
    messages.success(request, f'{product.name} ajouté au panier!')
    return redirect('e_commerce:cart')


@login_required
def cart(request):
    """
    Page du panier d'achat.
    
    Affiche tous les articles du panier de l'utilisateur avec :
    - Quantité par produit
    - Prix unitaire et total par produit
    - Total global du panier
    - Boutons pour modifier/supprimer
    - Bouton passer commande
    """
    cart_obj, created = Cart.objects.get_or_create(user=request.user)
    cart_items = cart_obj.items.all()
    
    context = {
        'cart': cart_obj,
        'cart_items': cart_items,
    }
    return render(request, 'partials/cart/view.html', context)


@login_required
def update_cart_item(request, item_id):
    """
    Mettre à jour la quantité d'un article dans le panier.
    
    Validations :
    - Quantité doit respecter le stock disponible
    - Si quantité = 0, supprimer l'article
    
    Redirige vers le panier avec message de confirmation.
    """
    cart_item = get_object_or_404(
        CartItem, id=item_id, cart__user=request.user
    )
    
    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 1))
        if quantity > 0:
            # Vérifier que la quantité ne dépasse pas le stock
            if quantity > cart_item.product.stock:
                messages.error(
                    request,
                    f'Stock insuffisant pour {cart_item.product.name}. '
                    f'Stock disponible: {cart_item.product.stock}'
                )
                return redirect('e_commerce:cart')
            cart_item.quantity = quantity
            cart_item.save()
            messages.success(request, 'Panier mis à jour!')
        else:
            # Quantité 0: supprimer l'article
            cart_item.delete()
            messages.info(request, 'Article supprimé du panier!')
    
    return redirect('e_commerce:cart')


@login_required
def remove_from_cart(request, item_id):
    """
    Supprimer un article du panier.
    
    Retire complètement l'article du panier, peu importe sa quantité.
    Redirige vers le panier avec message de confirmation.
    """
    cart_item = get_object_or_404(
        CartItem, id=item_id, cart__user=request.user
    )
    cart_item.delete()
    messages.info(request, 'Article supprimé du panier!')
    return redirect('e_commerce:cart')


@login_required
def seller_orders(request):
    """
    Vue pour les vendeurs: gestion de leurs commandes.
    
    Affiche toutes les commandes contenant des produits du vendeur connecté.
    Permet de filtrer par statut (pending, confirmed, shipped, delivered, cancelled).
    Pagination: 20 commandes par page.
    """
    if not request.user.is_seller:
        messages.error(request, 'Accès refusé. Vous devez être un vendeur.')
        return redirect('e_commerce:home')
    
    # Récupérer toutes les commandes contenant des produits de ce vendeur
    orders = Order.objects.filter(
        items__product__seller=request.user
    ).distinct().order_by('-created_at')
    
    # Filtre par statut si fourni
    status_filter = request.GET.get('status')
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    # Pagination: 20 commandes par page
    paginator = Paginator(orders, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'status_choices': Order.STATUS_CHOICES,
    }
    return render(request, 'partials/seller/orders.html', context)


@login_required
def update_order_status(request, order_id):
    """
    Vue pour mettre à jour le statut d'une commande (vendeurs uniquement).
    
    Permet au vendeur de changer le statut d'une de ses commandes.
    Validations :
    - L'utilisateur doit être vendeur
    - La commande doit contenir des produits du vendeur
    - Le statut doit être valide
    
    Envoie un email de notification au client lors du changement.
    """
    if not request.user.is_seller:
        messages.error(request, 'Accès refusé. Vous devez être un vendeur.')
        return redirect('e_commerce:home')
    
    order = get_object_or_404(Order, id=order_id)
    
    # Vérifier que cette commande contient des produits de ce vendeur
    seller_products = order.items.filter(product__seller=request.user)
    if not seller_products.exists():
        messages.error(request, 'Cette commande ne contient aucun de vos produits.')
        return redirect('e_commerce:seller_orders')
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in [choice[0] for choice in Order.STATUS_CHOICES]:
            order.status = new_status
            order.save()
            messages.success(request, f'Statut de la commande #{order.order_number} mis à jour.')
            return redirect('e_commerce:seller_orders')
        else:
            messages.error(request, 'Statut invalide.')
    
    context = {
        'order': order,
        'seller_items': seller_products,
        'status_choices': Order.STATUS_CHOICES,
    }
    return render(request, 'partials/seller/update_order_status.html', context)


@login_required
def checkout(request):
    """
    Vue de passage de commande (checkout).
    
    Étapes :
    1. Vérifier que le panier n'est pas vide
    2. Vérifier le stock de tous les articles
    3. Afficher formulaire pré-rempli avec données utilisateur
    4. À la soumission : créer Order + OrderItems, décrémenter stock, vider panier, envoyer email
    
    Validations :
    - Panier non vide
    - Stock suffisant pour tous les articles
    - Formulaire valide
    
    Données spécifiques par méthode de paiement:
    - Mobile Money: opérateur et numéro
    - Carte: 4 derniers chiffres et type stockés
    """
    cart_obj = get_object_or_404(Cart, user=request.user)
    cart_items = cart_obj.items.all()
    
    # Vérifier que le panier n'est pas vide
    if not cart_items.exists():
        messages.warning(request, 'Votre panier est vide!')
        return redirect('e_commerce:cart')
    
    # Vérifier le stock avant de procéder
    insufficient_stock = []
    for cart_item in cart_items:
        if cart_item.product.stock < cart_item.quantity:
            insufficient_stock.append(f"{cart_item.product.name} (Stock disponible: {cart_item.product.stock})")
    
    if insufficient_stock:
        messages.error(request, f"Stock insuffisant pour: {', '.join(insufficient_stock)}")
        return redirect('e_commerce:cart')
    
    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            # Créer la commande
            order = form.save(commit=False)
            order.user = request.user
            order.total_amount = cart_obj.get_total()
            
            # Enregistrer les données spécifiques selon la méthode de paiement
            payment_method = form.cleaned_data['payment_method']
            if payment_method == 'mobile_money':
                order.mobile_money_provider = form.cleaned_data['mobile_money_provider']
                order.payment_reference = form.cleaned_data['mobile_money_phone']
            elif payment_method == 'credit_card':
                card_number = form.cleaned_data['card_number']
                order.card_last_four = card_number[-4:] if card_number else ''
                order.card_brand = 'Visa' if card_number.startswith('4') else 'Mastercard'
            
            order.save()
            
            # Créer les OrderItems et décrémenter le stock
            for cart_item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product=cart_item.product,
                    quantity=cart_item.quantity,
                    price=cart_item.product.price
                )
                
                # Décrémenter le stock du produit
                cart_item.product.stock -= cart_item.quantity
                cart_item.product.save()
            
            # Vider le panier
            cart_items.delete()
            
            # Envoyer l'email de confirmation
            send_order_confirmation(request.user, order)
            
            messages.success(
                request,
                f'Commande #{order.order_number} créée avec succès!'
            )
            return redirect('e_commerce:order_confirmation', order_id=order.id)
    else:
        # Pré-remplir le formulaire avec les informations utilisateur
        form = OrderForm(initial={
            'phone': request.user.phone or request.user.store_phone,
            'delivery_address': request.user.address or request.user.store_address
        })
    
    context = {
        'form': form,
        'cart': cart_obj,
        'cart_items': cart_items,
    }
    return render(request, 'partials/orders/checkout.html', context)


@login_required
def order_confirmation(request, order_id):
    """
    Page de confirmation de commande.
    
    Affiche les détails de la commande créée avec :
    - Numéro de commande unique
    - Articles commandés
    - Montant total
    - Informations de livraison
    - Méthode de paiement
    """
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'partials/orders/confirmation.html',
                  {'order': order})


@login_required
def my_orders(request):
    """
    Liste des commandes de l'utilisateur.
    
    Affiche toutes les commandes du client connecté
    par ordre chronologique (plus récentes en premier).
    """
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    
    context = {
        'orders': orders,
    }
    return render(request, 'partials/orders/list.html', context)


@login_required
def order_detail(request, order_id):
    """
    Détail d'une commande spécifique.
    
    Affiche toutes les informations détaillées d'une commande :
    - Articles avec quantités et prix
    - Statut de la commande
    - Informations de livraison
    - Méthode de paiement
    """
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'partials/orders/detail.html', {'order': order})


@login_required
def become_seller(request):
    """
    Vue pour demander à devenir vendeur.
    
    Permet à un utilisateur client de soumettre une demande pour devenir vendeur.
    Validations :
    - L'utilisateur ne doit pas déjà être vendeur
    - L'utilisateur ne doit pas avoir déjà soumis une demande
    - Formulaire valide avec toutes les informations
    
    Après soumission, l'admin examinera la demande et enverra un email.
    """
    if request.user.is_seller:
        messages.info(request, 'Vous êtes déjà vendeur!')
        return redirect('e_commerce:seller_dashboard')
    
    if hasattr(request.user, 'seller_request'):
        messages.info(request, 'Vous avez déjà soumis une demande!')
        return redirect('e_commerce:seller_request_status')
    
    if request.method == 'POST':
        form = SellerRequestForm(request.POST)
        if form.is_valid():
            seller_request = form.save(commit=False)
            seller_request.user = request.user
            seller_request.save()
            
            # Envoyer un email à l'admin pour notification
            from .utils import send_seller_request_to_admin, send_seller_request_confirmation
            send_seller_request_to_admin(request.user, seller_request, request)
            
            # Envoyer un email de confirmation au client
            send_seller_request_confirmation(request.user, seller_request)
            
            messages.success(
                request,
                'Demande soumise avec succès! '
                'Vous avez reçu un email de confirmation. '
                'Vous recevrez un autre email une fois la décision prise.'
            )
            return redirect('e_commerce:seller_request_status')
    else:
        form = SellerRequestForm()
    
    return render(request, 'partials/seller/request.html', {'form': form})


@login_required
def seller_request_status(request):
    """
    Page de suivi du statut de la demande vendeur.
    
    Affiche le statut actuel de la demande (pending, approved, rejected)
    avec la date de soumission et la date de traitement si disponible.
    """
    try:
        seller_request = request.user.seller_request
    except SellerRequest.DoesNotExist:
        messages.info(request, 'Aucune demande trouvée.')
        return redirect('e_commerce:become_seller')
    
    return render(request, 'partials/seller/request_status.html',
                  {'seller_request': seller_request})


@login_required
def create_category(request):
    """
    Créer une nouvelle catégorie (vendeurs uniquement).
    
    Permet à un vendeur de créer une catégorie directement depuis
    le formulaire de création de produit via modal AJAX.
    
    Il supporte :
    - Requêtes AJAX : retourne JSON
    - Requêtes normales : redirige avec message
    
    Le slug est auto-généré à partir du nom.
    """
    if not request.user.is_seller:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Vous devez être vendeur!'})
        messages.error(request, 'Vous devez être vendeur!')
        return redirect('e_commerce:become_seller')
    
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            from django.utils.text import slugify
            category.slug = slugify(category.name)
            category.save()
            
            # Retourner JSON pour requêtes AJAX (modal)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'category_id': category.id,
                    'category_name': category.name,
                    'message': 'Catégorie créée avec succès!'
                })
            
            messages.success(request, 'Catégorie créée avec succès!')
            next_url = request.GET.get('next', 'e_commerce:seller_dashboard')
            return redirect(next_url)
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'errors': form.errors
                })
    else:
        form = CategoryForm()
    
    return render(request, 'partials/seller/create_category.html', {'form': form})


@login_required
def create_tag(request):
    """
    Créer un nouveau tag (vendeurs uniquement).
    
    Permet à un vendeur de créer un tag directement depuis
    le formulaire de création de produit via modal AJAX.
    
    Supporte :
    - Requêtes AJAX : retourne JSON
    - Requêtes normales : redirige avec message
    
    Le slug est auto-généré à partir du nom.
    Si le tag existe déjà, le retourne sans erreur.
    """
    if not request.user.is_seller:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Vous devez être vendeur!'})
        messages.error(request, 'Vous devez être vendeur!')
        return redirect('e_commerce:become_seller')
    
    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            from django.utils.text import slugify
            tag, created = Tag.objects.get_or_create(
                name=name.strip(),
                defaults={'slug': slugify(name.strip())}
            )
            
            # Retourner JSON pour requêtes AJAX (modal)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'tag_id': tag.id,
                    'tag_name': tag.name,
                    'message': f'Tag "{name}" créé avec succès!' if created else f'Le tag "{name}" existe déjà.'
                })
            
            if created:
                messages.success(request, f'Tag "{name}" créé avec succès!')
            else:
                messages.info(request, f'Le tag "{name}" existe déjà.')
            
            next_url = request.GET.get('next', 'e_commerce:seller_dashboard')
            return redirect(next_url)
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': 'Le nom du tag est requis.'
                })
            messages.error(request, 'Le nom du tag est requis.')
    
    return render(request, 'partials/seller/create_tag.html')


@login_required
def add_to_wishlist(request, product_id):
    """
    Ajouter un produit à la wishlist.
    
    Ajoute un produit aux favoris de l'utilisateur.
    Si déjà présent, informe sans erreur.
    
    Supporte AJAX et requêtes normales.
    """
    product = get_object_or_404(Product, id=product_id)
    
    # Vérifier si déjà dans la wishlist
    wishlist_item, created = Wishlist.objects.get_or_create(
        user=request.user,
        product=product
    )
    
    if created:
        messages.success(request, f'{product.name} ajouté aux favoris!')
    else:
        messages.info(request, f'{product.name} est déjà dans vos favoris!')
    
    # Retourner JSON pour requêtes AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'added': created,
            'message': f'{product.name} ajouté aux favoris!' if created else f'{product.name} est déjà dans vos favoris!'
        })
    
    return redirect('e_commerce:product_detail', slug=product.slug)


@login_required
def remove_from_wishlist(request, product_id):
    """
    Retirer un produit de la wishlist.
    
    Supprime un produit des favoris de l'utilisateur.
    Si absent, affiche une erreur.
    
    Supporte AJAX et requêtes normales.
    """
    product = get_object_or_404(Product, id=product_id)
    
    try:
        wishlist_item = Wishlist.objects.get(user=request.user, product=product)
        wishlist_item.delete()
        messages.success(request, f'{product.name} retiré des favoris!')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'{product.name} retiré des favoris!'
            })
    except Wishlist.DoesNotExist:
        messages.error(request, 'Ce produit n\'est pas dans vos favoris!')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': 'Ce produit n\'est pas dans vos favoris!'
            })
    
    return redirect('e_commerce:wishlist')


@login_required
def wishlist(request):
    """
    Page de la wishlist de l'utilisateur.
    
    Affiche tous les produits favoris de l'utilisateur avec :
    - Images, noms, prix
    - Boutons ajouter au panier et retirer
    - Pagination (12 produits par page)
    """
    wishlist_items = Wishlist.objects.filter(user=request.user).select_related('product')
    
    # Pagination: 12 produits par page
    paginator = Paginator(wishlist_items, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'wishlist_items': wishlist_items,
    }
    return render(request, 'partials/wishlist/view.html', context)


def toggle_wishlist(request, product_id):
    """
    Bascule l'ajout/retrait d'un produit dans la wishlist (AJAX uniquement).
    
    Fonction utilisée par les boutons cœur dans l'interface :
    - Si absent : ajoute
    - Si présent : retire
    
    Retourne toujours JSON.
    """
    if not request.user.is_authenticated:
        return JsonResponse({
            'success': False,
            'message': 'Veuillez vous connecter pour ajouter aux favoris!'
        })
    
    product = get_object_or_404(Product, id=product_id)
    
    try:
        # Produit déjà dans wishlist: retirer
        wishlist_item = Wishlist.objects.get(user=request.user, product=product)
        wishlist_item.delete()
        action = 'removed'
        message = f'{product.name} retiré des favoris!'
    except Wishlist.DoesNotExist:
        # Produit pas dans wishlist: ajouter
        Wishlist.objects.create(user=request.user, product=product)
        action = 'added'
        message = f'{product.name} ajouté aux favoris!'
    
    return JsonResponse({
        'success': True,
        'action': action,
        'message': message,
        'product_id': product_id
    })


@login_required
def submit_review(request, product_id):
    """
    Soumettre un avis sur un produit.
    
    Validations :
    - Utilisateur doit avoir commandé le produit
    - Un seul avis par utilisateur par produit (peut modifier)
    
    Si avis déjà existant, le met à jour au lieu de créer un doublon.
    """
    product = get_object_or_404(Product, id=product_id)
    
    # Vérifier que l'utilisateur a commandé ce produit
    has_ordered = OrderItem.objects.filter(
        order__user=request.user,
        product=product
    ).exists()
    
    if not has_ordered:
        messages.error(request, 'Vous devez avoir commandé ce produit pour laisser un avis.')
        return redirect('e_commerce:product_detail', slug=product.slug)

    if request.method == 'POST':
        # upsert_review met à jour l'avis existant au lieu d'en créer un
        # doublon (un seul avis par produit par utilisateur).
        form = ProductReviewForm(request.POST)
        if form.is_valid():
            upsert_review(
                product.id, request.user.id,
                int(form.cleaned_data['rating']), form.cleaned_data['comment'],
            )
            messages.success(request, 'Merci pour votre avis!')

    return redirect('e_commerce:product_detail', slug=product.slug)


@login_required
def seller_dashboard(request):
    """
    Tableau de bord vendeur avec statistiques complètes.
    
    Affiche les statistiques de vente pour le vendeur connecté :
    - Total des ventes (commandes livrées uniquement)
    - Nombre total de commandes
    - Produits actifs
    - Commandes par statut (pending, confirmed, shipped, delivered, cancelled)
    - 10 dernières commandes
    - Ventes mensuelles sur 6 mois avec pourcentages
    
    Calculs :
    - Ventes = somme des montants des commandes livrées contenant des produits du vendeur
    - Ventes mensuelles = ventes des 6 derniers mois
    """
    if not request.user.is_seller:
        messages.error(request, 'Vous devez être vendeur!')
        return redirect('e_commerce:become_seller')
    
    products = Product.objects.filter(seller=request.user)
    orders = Order.objects.filter(
        items__product__seller=request.user
    ).distinct()
    
    # Statistiques globales
    total_sales = 0
    total_orders_count = orders.count()
    active_products = products.filter(is_active=True).count()
    
    # Calculer les commandes par statut
    pending_orders = orders.filter(status='pending').count()
    confirmed_orders = orders.filter(status='confirmed').count()
    shipped_orders = orders.filter(status='shipped').count()
    delivered_orders = orders.filter(status='delivered').count()
    cancelled_orders = orders.filter(status='cancelled').count()
    
    # Calculer le total des ventes (commandes livrées uniquement)
    for order in orders.filter(status='delivered'):
        # Calculer la portion du vendeur dans cette commande
        seller_items = order.items.filter(product__seller=request.user)
        seller_total = sum(item.get_total() for item in seller_items)
        total_sales += seller_total
    
    # 10 dernières commandes
    recent_orders = orders.order_by('-created_at')[:10]
    
    # Ventes mensuelles (6 derniers mois)
    from django.utils import timezone
    from datetime import timedelta
    import calendar
    
    monthly_sales = []
    for i in range(6):
        month_start = timezone.now().replace(day=1) - timedelta(days=30*i)
        month_end = month_start.replace(day=calendar.monthrange(month_start.year, month_start.month)[1])
        
        month_orders = orders.filter(
            created_at__range=[month_start, month_end],
            status='delivered'
        )
        
        month_sales = 0
        for order in month_orders:
            seller_items = order.items.filter(product__seller=request.user)
            month_sales += sum(item.get_total() for item in seller_items)
        
        monthly_sales.append({
            'month': month_start.strftime('%B %Y'),
            'sales': month_sales,
            'percent': (float(month_sales) / float(total_sales) * 100.0) if total_sales > 0 else 0.0
        })
    
    monthly_sales.reverse()  # Afficher du plus ancien au plus récent
    
    context = {
        'products': products,
        'recent_orders': recent_orders,
        'total_sales': total_sales,
        'total_orders_count': total_orders_count,
        'active_products': active_products,
        'pending_orders': pending_orders,
        'confirmed_orders': confirmed_orders,
        'shipped_orders': shipped_orders,
        'delivered_orders': delivered_orders,
        'cancelled_orders': cancelled_orders,
        'monthly_sales': monthly_sales,
    }
    return render(request, 'partials/seller/dashboard.html', context)


@login_required
def product_create(request):
    """
    Créer un nouveau produit (vendeurs uniquement).
    
    Permet au vendeur de créer un produit avec :
    - Nom, description, prix, catégorie, tags
    - Image principale + jusqu'à 5 images additionnelles
    - Stock initial
    - Slug auto-généré et unique
    
    Après création, redirige vers le dashboard.
    """
    if not request.user.is_seller:
        messages.error(request, 'Vous devez être vendeur!')
        return redirect('e_commerce:become_seller')
    
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.seller = request.user
            
            # Générer slug si non fourni
            if not product.slug:
                from django.utils.text import slugify
                import random
                import string
                
                product.slug = slugify(product.name)
                # Rendre le slug unique en ajoutant un suffixe aléatoire si nécessaire
                while Product.objects.filter(slug=product.slug).exists():
                    random_suffix = ''.join(random.choices(
                        string.ascii_lowercase + string.digits, k=6
                    ))
                    product.slug = f"{slugify(product.name)}-{random_suffix}"
            
            product.save()
            form.save_m2m()  # Sauvegarder les relations many-to-many (tags)
            
            # Gérer les images additionnelles (limite à 5)
            if 'additional_images' in request.FILES:
                files = request.FILES.getlist('additional_images')
                # Limiter à 5 images additionnelles
                files = files[:5]
                for i, file in enumerate(files):
                    ProductImage.objects.create(
                        product=product,
                        image=file,
                        order=i,
                        is_primary=(i == 0)  # Première image est primaire
                    )
            
            messages.success(request, 'Produit créé avec succès!')
            return redirect('e_commerce:seller_dashboard')
    else:
        form = ProductForm()
    
    return render(request, 'partials/seller/product_form.html', {'form': form})


@login_required
def product_update(request, product_id):
    """
    Modifier un produit existant.
    
    Permet au vendeur de modifier tous les champs de son produit :
    - Informations de base
    - Images (principale + additionnelles)
    - Catégorie et tags
    - Stock
    
    Seuls les produits du vendeur connecté peuvent être modifiés.
    """
    product = get_object_or_404(Product, id=product_id, seller=request.user)
    
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, 'Produit modifié avec succès!')
            return redirect('e_commerce:seller_dashboard')
    else:
        form = ProductForm(instance=product)
    
    return render(request, 'partials/seller/product_form.html', {
        'form': form,
        'product': product
    })


@login_required
def product_delete(request, product_id):
    """
    Supprimer un produit.
    
    Affiche une page de confirmation avant suppression définitive.
    Seuls les produits du vendeur connecté peuvent être supprimés.
    
    Attention: suppression irréversible de toutes les données du produit.
    """
    product = get_object_or_404(Product, id=product_id, seller=request.user)
    
    if request.method == 'POST':
        product.delete()
        messages.success(request, 'Produit supprimé!')
        return redirect('e_commerce:seller_dashboard')
    
    return render(request, 'partials/seller/product_delete.html',
                  {'product': product}) 