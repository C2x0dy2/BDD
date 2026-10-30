from rest_framework import serializers


class ReplySerializer(serializers.Serializer):
    author = serializers.CharField(max_length=100)
    body = serializers.CharField()
    created_at = serializers.DateTimeField(read_only=True)


class ReviewSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    product_id = serializers.IntegerField(read_only=True)
    user_id = serializers.IntegerField()
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField()
    created_at = serializers.DateTimeField(read_only=True)
    replies = ReplySerializer(many=True, read_only=True)


class ProductSpecsSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(read_only=True)
    category = serializers.CharField(max_length=100)
    attributes = serializers.DictField()
    media = serializers.ListField(child=serializers.URLField(), required=False)
    tags = serializers.ListField(child=serializers.CharField(), required=False)
    updated_at = serializers.DateTimeField(read_only=True)


class ProductSerializer(serializers.Serializer):
    """Minimal read-only view of e_commerce.Product for the JSON API."""
    id = serializers.IntegerField()
    sku = serializers.CharField(source="slug")
    name = serializers.CharField()
    category_id = serializers.IntegerField(source="category.id", allow_null=True, default=None)
    category_name = serializers.CharField(source="category.name", allow_null=True, default=None)
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = serializers.IntegerField(source="stock")
    created_at = serializers.DateTimeField()
