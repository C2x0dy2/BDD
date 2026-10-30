"""
Configuration des URLs pour l'application e_commerce.
"""
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from . import views

app_name = 'e_commerce'

urlpatterns = [
    # Accueil et produits
    path('', views.home, name='home'),
    path('products/', views.product_list, name='product_list'),
    path('products/<slug:slug>/', views.ProductDetailView.as_view(),
         name='product_detail'),
    
    # Authentification
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('profile/', views.profile, name='profile'),
    
    # Réinitialisation du mot de passe
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='registration/password_reset_form.html',
        email_template_name='registration/password_reset_email.html',
        subject_template_name='registration/password_reset_subject.txt',
        success_url='/password-reset/done/'
    ), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html'
    ), name='password_reset_done'),
    path('password-reset/confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html',
        success_url='/password-reset/complete/'
    ), name='password_reset_confirm'),
    path('password-reset/complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html'
    ), name='password_reset_complete'),
    
    # Vérification de l'email
    path('verify-email/<int:user_id>/<str:token>/', views.verify_email, name='verify_email'),
    path('verification-sent/', views.verification_sent, name='verification_sent'),
    # Chemin de compatibilité pour les emails utilisant le pattern users/activate/...
    path('users/activate/<str:user_id>/<str:token>/', views.verify_email, name='verify_email_compat'),
    
    # Panier
    path('cart/', views.cart, name='cart'),
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/update/<int:item_id>/', views.update_cart_item,
         name='update_cart_item'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart,
         name='remove_from_cart'),
    
    # Commandes
    path('checkout/', views.checkout, name='checkout'),
    path('orders/', views.my_orders, name='my_orders'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
    path('order-confirmation/<int:order_id>/', views.order_confirmation,
         name='order_confirmation'),
    
    # Liste de souhaits
    path('wishlist/', views.wishlist, name='wishlist'),
    path('wishlist/add/<int:product_id>/', views.add_to_wishlist, name='add_to_wishlist'),
    path('wishlist/remove/<int:product_id>/', views.remove_from_wishlist, name='remove_from_wishlist'),
    path('wishlist/toggle/<int:product_id>/', views.toggle_wishlist, name='toggle_wishlist'),
    
    # Avis
    path('products/<int:product_id>/review/', views.submit_review, name='submit_review'),
    
    # Vendeur
    path('become-seller/', views.become_seller, name='become_seller'),
    path('seller-request-status/', views.seller_request_status,
         name='seller_request_status'),
    path('seller/dashboard/', views.seller_dashboard, name='seller_dashboard'),
    path('seller/product/create/', views.product_create, name='product_create'),
    path('seller/product/<int:product_id>/edit/', views.product_update,
         name='product_update'),
    path('seller/product/<int:product_id>/delete/', views.product_delete,
         name='product_delete'),
    path('seller/orders/', views.seller_orders, name='seller_orders'),
    path('seller/orders/<int:order_id>/update-status/', views.update_order_status,
         name='update_order_status'),
    path('seller/category/create/', views.create_category, name='create_category'),
    path('seller/tag/create/', views.create_tag, name='create_tag'),
    
    # Pages statiques
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
