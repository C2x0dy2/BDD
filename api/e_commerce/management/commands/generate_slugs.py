"""
Management command to generate slugs for existing products that don't have them.
"""
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from e_commerce.models import Product
import random
import string


def ensure_directories():
    """Ensure management/commands directories exist."""
    import os
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    management_dir = os.path.join(base_dir, 'management')
    commands_dir = os.path.join(management_dir, 'commands')
    
    os.makedirs(management_dir, exist_ok=True)
    os.makedirs(commands_dir, exist_ok=True)
    
    # Create __init__.py files
    init_management = os.path.join(management_dir, '__init__.py')
    init_commands = os.path.join(commands_dir, '__init__.py')
    
    if not os.path.exists(init_management):
        with open(init_management, 'w') as f:
            f.write('# Management commands for e_commerce app\n')
    
    if not os.path.exists(init_commands):
        with open(init_commands, 'w') as f:
            f.write('# Management commands\n')


class Command(BaseCommand):
    help = 'Generate slugs for products that don\'t have them'

    def handle(self, *args, **options):
        products = Product.objects.filter(slug__isnull=True) | Product.objects.filter(slug='')
        
        count = products.count()
        self.stdout.write(f'Found {count} products without slugs')
        
        for product in products:
            base_slug = slugify(product.name)
            test_slug = base_slug
            
            # Find a unique slug
            counter = 1
            while Product.objects.filter(slug=test_slug).exists():
                random_suffix = ''.join(random.choices(
                    string.ascii_lowercase + string.digits, k=6
                ))
                test_slug = f"{base_slug}-{random_suffix}"
            
            product.slug = test_slug
            product.save()
            self.stdout.write(f'Generated slug for: {product.name} -> {test_slug}')
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully generated slugs for {count} products!')
        )
