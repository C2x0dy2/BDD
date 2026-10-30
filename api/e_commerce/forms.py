"""
Formulaires pour la plateforme e-commerce SÎKÂ.
"""
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from .models import (
    User, Product, Category, Tag, SellerRequest, Order, CartItem, ProductImage
)


class CustomUserCreationForm(UserCreationForm):
    """Formulaire d'inscription personnalisé avec option vendeur."""
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Votre adresse email'
        })
    )
    first_name = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Prénom'
        })
    )
    last_name = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nom'
        })
    )
    phone = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Téléphone (optionnel)'
        })
    )
    password1 = forms.CharField(
        label='Mot de passe',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Mot de passe'
        })
    )
    password2 = forms.CharField(
        label='Confirmation mot de passe',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirmer le mot de passe'
        })
    )
    
    # Option vendeur
    become_seller = forms.BooleanField(
        required=False,
        label='Devenir vendeur',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'become_seller_checkbox'
        })
    )
    
    # Acceptation de la politique de confidentialité
    accept_privacy = forms.BooleanField(
        required=True,
        label='J\'accepte les conditions de confidentialité',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'accept_privacy_checkbox'
        })
    )
    
    # Champs spécifiques aux vendeurs (affichés uniquement si become_seller est coché)
    store_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nom de votre boutique',
            'style': 'display: none;'
        })
    )
    store_description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Description de votre boutique',
            'rows': 4,
            'style': 'display: none;'
        })
    )
    store_phone = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Numéro de téléphone de la boutique'
        })
    )
    store_address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Adresse complète de la boutique',
            'rows': 3,
            'style': 'display: none;'
        })
    )
    identity_photo = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*',
            'style': 'display: none;'
        })
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'phone',
                  'password1', 'password2', 'become_seller', 'store_name',
                  'store_description', 'store_phone', 'store_address', 'identity_photo')
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom d\'utilisateur'
            })
        }

    def clean(self):
        cleaned_data = super().clean()
        become_seller = cleaned_data.get('become_seller')
        accept_privacy = cleaned_data.get('accept_privacy')
        
        # Valider l'acceptation de la politique de confidentialité
        if not accept_privacy:
            raise ValidationError('Vous devez accepter les conditions de confidentialité pour créer un compte.')
        
        if become_seller:
            # Valider les champs spécifiques aux vendeurs lorsque become_seller est coché
            store_name = cleaned_data.get('store_name')
            store_description = cleaned_data.get('store_description')
            store_phone = cleaned_data.get('store_phone')
            store_address = cleaned_data.get('store_address')
            identity_photo = cleaned_data.get('identity_photo')
            
            if not store_name:
                raise ValidationError('Le nom de la boutique est requis pour devenir vendeur.')
            if not store_description:
                raise ValidationError('La description de la boutique est requise pour devenir vendeur.')
            if not store_phone:
                raise ValidationError('Le numéro de téléphone de la boutique est requis pour devenir vendeur.')
            if not store_address:
                raise ValidationError('L\'adresse de la boutique est requise pour devenir vendeur.')
            if not identity_photo:
                raise ValidationError('La photo d\'identité est requise pour devenir vendeur.')
        
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.is_email_verified = False
        
        # Définir le statut vendeur et les champs si become_seller est coché
        if self.cleaned_data.get('become_seller'):
            user.is_seller = True
            user.store_name = self.cleaned_data['store_name']
            user.store_description = self.cleaned_data['store_description']
            user.store_phone = self.cleaned_data['store_phone']
            user.store_address = self.cleaned_data['store_address']
            user.identity_photo = self.cleaned_data['identity_photo']
        
        if commit:
            user.save()
        return user


class LoginForm(forms.Form):
    """Formulaire de connexion."""
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nom d\'utilisateur ou Email'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Mot de passe'
        })
    )


class SellerRequestForm(forms.ModelForm):
    """Formulaire de demande d'inscription vendeur."""
    class Meta:
        model = SellerRequest
        fields = ['store_name', 'description', 'phone', 'address']
        widgets = {
            'store_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom de votre boutique'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Description de votre boutique',
                'rows': 4
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Numéro de téléphone'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Adresse complète',
                'rows': 3
            }),
        }


class ProductForm(forms.ModelForm):
    """Formulaire de création/édition de produits."""
    # Note : additional_images est géré dans le template comme un input HTML standard
    # avec l'attribut multiple, et non comme un champ de formulaire Django
    additional_images = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control'
        })
    )
    
    class Meta:
        model = Product
        fields = [
            'name', 'description', 'price', 'image', 'category',
            'tags', 'stock', 'is_active'
            # Note : le slug est auto-généré, pas dans le formulaire
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom du produit'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Description du produit',
                'rows': 4
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Prix en FCFA',
                'step': '0.01'
            }),
            'image': forms.FileInput(attrs={
                'class': 'form-control'
            }),
            'category': forms.Select(attrs={
                'class': 'form-control'
            }),
            'tags': forms.CheckboxSelectMultiple(),
            'stock': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Stock disponible'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }


class CategoryForm(forms.ModelForm):
    """Formulaire de création/édition de catégories."""
    class Meta:
        model = Category
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom de la catégorie'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Description',
                'rows': 3
            }),
        }


class CartItemForm(forms.ModelForm):
    """Formulaire de mise à jour de la quantité d'un article du panier."""
    class Meta:
        model = CartItem
        fields = ['quantity']
        widgets = {
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'style': 'width: 80px;'
            }),
        }

    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        if quantity < 1:
            raise ValidationError(
                'La quantité doit être supérieure à 0'
            )
        return quantity


class OrderForm(forms.ModelForm):
    """Formulaire de passage de commande."""
    mobile_money_provider = forms.ChoiceField(
        choices=[
            ('', 'Sélectionner un opérateur'),
            ('momo', 'MTN Mobile Money'),
            ('orange', 'Orange Money'),
            ('moov', 'Moov Money'),
        ],
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'mobile_money_provider'
        })
    )
    
    # Champs de carte de crédit
    card_number = forms.CharField(
        required=False,
        max_length=19,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '1234 5678 9012 3456',
            'id': 'card_number'
        })
    )
    card_expiry = forms.CharField(
        required=False,
        max_length=7,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'MM/YY',
            'id': 'card_expiry'
        })
    )
    card_cvv = forms.CharField(
        required=False,
        max_length=4,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '123',
            'id': 'card_cvv'
        })
    )
    card_holder_name = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nom du titulaire',
            'id': 'card_holder_name'
        })
    )
    
    # Numéro de téléphone Mobile Money
    mobile_money_phone = forms.CharField(
        required=False,
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Numéro de téléphone Mobile Money',
            'id': 'mobile_money_phone'
        })
    )
    
    class Meta:
        model = Order
        fields = ['payment_method', 'delivery_address', 'phone', 'notes']
        widgets = {
            'payment_method': forms.Select(attrs={
                'class': 'form-control',
                'id': 'payment_method'
            }),
            'delivery_address': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Adresse complète de livraison',
                'rows': 3
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Numéro de téléphone'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Notes supplémentaires (optionnel)',
                'rows': 2
            }),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        payment_method = cleaned_data.get('payment_method')
        
        if payment_method == 'mobile_money':
            mobile_money_provider = cleaned_data.get('mobile_money_provider')
            mobile_money_phone = cleaned_data.get('mobile_money_phone')
            
            if not mobile_money_provider:
                raise ValidationError('Veuillez sélectionner un opérateur Mobile Money.')
            if not mobile_money_phone:
                raise ValidationError('Veuillez saisir votre numéro Mobile Money.')
                
        elif payment_method == 'credit_card':
            card_number = cleaned_data.get('card_number')
            card_expiry = cleaned_data.get('card_expiry')
            card_cvv = cleaned_data.get('card_cvv')
            card_holder_name = cleaned_data.get('card_holder_name')
            
            if not all([card_number, card_expiry, card_cvv, card_holder_name]):
                raise ValidationError('Veuillez remplir tous les champs de la carte de crédit.')
        
        return cleaned_data


class ContactForm(forms.Form):
    """Formulaire de contact simple."""
    name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={
        'class': 'form-control', 'placeholder': 'Votre nom complet'
    }))
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        'class': 'form-control', 'placeholder': 'Votre email'
    }))
    subject = forms.CharField(max_length=200, widget=forms.TextInput(attrs={
        'class': 'form-control', 'placeholder': 'Sujet'
    }))
    message = forms.CharField(widget=forms.Textarea(attrs={
        'class': 'form-control', 'placeholder': 'Votre message', 'rows': 5
    }))


class ProductReviewForm(forms.Form):
    """Formulaire d'avis sur les produits (stocké dans MongoDB, pas d'ORM)."""
    RATING_CHOICES = [(i, f"{i} étoile" + ("s" if i > 1 else "")) for i in range(1, 6)]

    rating = forms.ChoiceField(
        choices=RATING_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        label='Notez ce produit',
    )
    comment = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Partagez votre expérience avec ce produit...',
            'rows': 4,
        }),
        label='Votre avis',
    )
