"""
Fonctions utilitaires pour la plateforme e-commerce SÎKÂ.
"""
from django.core.mail import send_mail
from django.core import signing
from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site
from django.utils.crypto import get_random_string
from django.utils import timezone
from datetime import timedelta


def send_email_verification(user, request):
    """
    Envoie un lien de vérification d'email à l'utilisateur avec un token simple.
    """
    # Créer un token signé et horodaté qui encode l'ID utilisateur
    token = signing.dumps({'uid': user.id}, salt='email-verify')
    
    from django.urls import reverse
    # Construire l'URL absolue à partir d'une route nommée pour éviter les chemins codés en dur
    verification_link = request.build_absolute_uri(
        reverse('e_commerce:verify_email', args=[user.id, token])
    )
    
    subject = 'Confirmez votre compte SÎKÂ'
    message = f"""Bonjour {user.first_name},

Bienvenue sur SÎKÂ !

Merci de vous être inscrit. Pour activer votre compte et accéder à la plateforme,
veuillez cliquer sur le lien ci-dessous :

{verification_link}

Ce lien est valide pendant 24 heures.

Si vous n'avez pas créé de compte, vous pouvez ignorer cet email.

Cordialement,
L'équipe SÎKÂ
"""
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [user.email]
    
    try:
        send_mail(subject, message, from_email, recipient_list,
                  fail_silently=False)
        return True
    except Exception as e:
        print(f"Erreur lors de l'envoi de l'email: {e}")
        return False


def send_order_confirmation(user, order):
    """
    Envoie un email de confirmation de commande au client.
    """
    subject = f'Confirmation de commande #{order.order_number}'
    message = f"""
    Bonjour {user.first_name},
    
    Votre commande a été enregistrée avec succès !
    
    Détails de la commande :
    - Numéro : {order.order_number}
    - Date : {order.created_at.strftime('%d/%m/%Y à %H:%M')}
    - Montant total : {order.total_amount:.0f} FCFA
    - Méthode de paiement : {order.get_payment_method_display()}
    
    Nous vous contacterons bientôt pour confirmer votre commande.
    
    Merci pour votre confiance !
    L'équipe SÎKÂ
    """
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [user.email]
    
    try:
        send_mail(subject, message, from_email, recipient_list,
                  fail_silently=False)
        return True
    except Exception as e:
        print(f"Erreur lors de l'envoi de l'email: {e}")
        return False


def send_seller_request_to_admin(user, seller_request, request):
    """
    Envoie un email à l'administrateur pour notifier qu'un utilisateur veut devenir vendeur.
    """
    from .models import User
    
    # Récupérer tous les administrateurs
    admins = User.objects.filter(is_staff=True, is_active=True)
    admin_emails = [admin.email for admin in admins if admin.email]
    
    if not admin_emails:
        # Si aucun admin n'a d'email, utiliser l'email par défaut
        admin_emails = [settings.DEFAULT_FROM_EMAIL]
    
    subject = f'[SÎKÂ] Nouvelle demande de vendeur - {user.username}'
    message = f"""
    Nouvelle demande de vendeur reçue
    
    Détails de la demande :
    - Utilisateur : {user.username} (ID: {user.id})
    - Nom complet : {user.get_full_name() or user.username}
    - Email : {user.email}
    - Téléphone : {user.phone or 'Non renseigné'}
    
    Informations de la boutique :
    - Nom de la boutique : {seller_request.store_name}
    - Description : {seller_request.description[:200]}...
    - Téléphone boutique : {seller_request.phone}
    - Adresse : {seller_request.address}
    
    Date de soumission : {seller_request.created_at.strftime('%d/%m/%Y à %H:%M')}
    
    Veuillez examiner cette demande dans l'interface d'administration.
    """
    
    from_email = settings.DEFAULT_FROM_EMAIL
    
    try:
        send_mail(subject, message, from_email, admin_emails,
                  fail_silently=False)
        return True
    except Exception as e:
        print(f"Erreur lors de l'envoi de l'email à l'admin: {e}")
        return False


def send_seller_request_confirmation(user, seller_request):
    """
    Envoie un email de confirmation au client indiquant que sa demande est en cours de traitement.
    """
    subject = 'Votre demande de vendeur est en cours de traitement'
    message = f"""
    Bonjour {user.first_name or user.username},
    
    Nous avons bien reçu votre demande pour devenir vendeur sur SÎKÂ.
    
    Détails de votre demande :
    - Nom de la boutique : {seller_request.store_name}
    - Date de soumission : {seller_request.created_at.strftime('%d/%m/%Y à %H:%M')}
    
    Votre demande est actuellement en cours d'examen par notre équipe.
    Vous recevrez un email de notification une fois la décision prise.
    
    En attendant, vous pouvez suivre le statut de votre demande depuis votre espace personnel.
    
    Cordialement,
    L'équipe SÎKÂ
    """
    
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [user.email]
    
    try:
        send_mail(subject, message, from_email, recipient_list,
                  fail_silently=False)
        return True
    except Exception as e:
        print(f"Erreur lors de l'envoi de l'email de confirmation: {e}")
        return False


def send_seller_status_notification(user, status, request=None):
    """
    Envoie une notification à l'utilisateur concernant le statut de sa demande vendeur.
    """
    from django.urls import reverse
    
    if status == 'approved':
        subject = 'Félicitations ! Votre demande de vendeur a été approuvée'
        
        # Construire le lien de connexion
        login_link = ''
        if request:
            login_link = request.build_absolute_uri(reverse('e_commerce:login'))
        else:
            # Solution de secours si request n'est pas disponible
            login_link = f"{settings.DEFAULT_FROM_EMAIL.split('@')[0] if '@' in settings.DEFAULT_FROM_EMAIL else 'https://votre-domaine.com'}/login/"
        
        message = f"""
        Félicitations {user.first_name or user.username} !
        
        Votre demande pour devenir vendeur sur SÎKÂ a été approuvée.
        
        Vous pouvez maintenant accéder à votre tableau de bord vendeur
        et commencer à ajouter vos produits.
        
        Pour vous connecter, cliquez sur le lien suivant :
        {login_link}
        
        Une fois connecté, vous accéderez automatiquement à votre tableau de bord vendeur
        où vous pourrez gérer vos produits, vos commandes et vos statistiques.
        
        Bienvenue dans l'équipe SÎKÂ !
        
        Cordialement,
        L'équipe SÎKÂ
        """
    else:
        subject = 'Statut de votre demande de vendeur'
        message = f"""
        Bonjour {user.first_name or user.username},
        
        Malheureusement, votre demande pour devenir vendeur n'a pas
        été approuvée pour le moment.
        
        Vous pouvez nous contacter pour plus d'informations ou soumettre
        une nouvelle demande avec des informations complémentaires.
        
        Cordialement,
        L'équipe SÎKÂ
        """
    
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [user.email]
    
    try:
        send_mail(subject, message, from_email, recipient_list,
                  fail_silently=False)
        return True
    except Exception as e:
        print(f"Erreur lors de l'envoi de l'email: {e}")
        return False
