"""
Tags de template pour les avis produits.
"""
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def show_stars(rating):
    """Génère l'affichage des étoiles pour la notation."""
    html = ''
    for i in range(1, 6):
        if i <= rating:
            html += '<i class="bi bi-star-fill text-warning"></i>'
        else:
            html += '<i class="bi bi-star text-secondary"></i>'
    return mark_safe(html)

