"""Object-level rules for the JSON API (who may change what)."""
from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import OrderItem


def is_staff(user):
    return bool(user and user.is_authenticated and user.is_staff)


class IsApprovedSellerOrReadOnly(BasePermission):
    """Creating a product needs an approved seller (or staff)."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        return bool(
            user.is_authenticated
            and (user.is_staff or (user.is_seller and user.is_seller_approved))
        )


class IsProductOwnerOrReadOnly(BasePermission):
    """A seller edits and deletes only their own products."""

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return is_staff(request.user) or obj.seller_id == request.user.id


def can_manage_order(user, order):
    """Staff, or a seller who has at least one item in this order."""
    if is_staff(user):
        return True
    return OrderItem.objects.filter(order=order, product__seller_id=user.id).exists()
