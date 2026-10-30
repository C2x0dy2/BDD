"""
Management command to send a test email for verification.
"""
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings


class Command(BaseCommand):
    help = 'Send a test email to verify email configuration'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='Email address to send test email to')
        parser.add_argument('--user-id', type=int, default=1, help='User ID for verification link')

    def handle(self, *args, **options):
        email = options['email']
        user_id = options['user_id']
        
        # Generate a test verification link
        verification_link = f"http://127.0.0.1:8000/verify-email/{user_id}/test123token456/"
        
        subject = 'Test Email - SÎKÂ'
        message = f"""Bonjour,

Ceci est un email de test de SÎKÂ.

Lien de vérification: {verification_link}

Si vous recevez cet email, la configuration email fonctionne correctement.
"""
        
        try:
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)
            self.stdout.write(
                self.style.SUCCESS(f'✅ Email de test envoyé à {email}!')
            )
            self.stdout.write(
                self.style.WARNING('Note: En développement, vérifiez votre terminal pour voir l\'email.')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Erreur lors de l\'envoi: {e}')
            )






