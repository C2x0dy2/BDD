from rest_framework import serializers


class ReplySerializer(serializers.Serializer):
    author = serializers.CharField(max_length=100)
    body = serializers.CharField()
    created_at = serializers.DateTimeField(read_only=True)


class ReviewSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    product_id = serializers.IntegerField(read_only=True)
    customer_id = serializers.IntegerField()
    rating = serializers.IntegerField(min_value=1, max_value=5)
    title = serializers.CharField(max_length=200)
    body = serializers.CharField()
    created_at = serializers.DateTimeField(read_only=True)
    replies = ReplySerializer(many=True, read_only=True)


class ProductSpecsSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(read_only=True)
    category = serializers.CharField(max_length=100)
    attributes = serializers.DictField()
    media = serializers.ListField(child=serializers.URLField(), required=False)
    tags = serializers.ListField(child=serializers.CharField(), required=False)
    updated_at = serializers.DateTimeField(read_only=True)
