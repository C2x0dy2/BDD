"""
DRF serializers for the PostgreSQL write endpoints under /api/ (products,
order status). Separate from the HTML forms in forms.py: this is the
JSON-facing surface the subject's "API connected to every database, with
read AND write endpoints for each" requirement is about.
"""
from rest_framework import serializers

from .models import Category, Order, Product, User


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True, default=None)
    seller_username = serializers.CharField(source="seller.username", read_only=True)

    class Meta:
        model = Product
        fields = [
            "id", "name", "slug", "description", "price",
            "category", "category_name", "seller", "seller_username",
            "stock", "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["slug", "created_at", "updated_at"]
        extra_kwargs = {
            "price": {"min_value": 0},
            "stock": {"min_value": 0},
        }

    def validate_category(self, category):
        if category is None:
            raise serializers.ValidationError("Category is required.")
        return category


class OrderStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ["id", "order_number", "status", "payment_status", "total_amount"]
        read_only_fields = ["id", "order_number", "total_amount"]
