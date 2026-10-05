from rest_framework import serializers

from catalog.models import Product

from .models import Customer, Order, OrderItem


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ["id", "email", "first_name", "last_name", "created_at"]


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = OrderItem
        fields = ["id", "product", "product_name", "quantity", "unit_price"]


class OrderItemInputSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    quantity = serializers.IntegerField(min_value=1)


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    customer_email = serializers.CharField(source="customer.email", read_only=True)
    # Write-only: list of {product, quantity} used to create the order items.
    items_input = OrderItemInputSerializer(many=True, write_only=True, required=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "customer",
            "customer_email",
            "status",
            "total_amount",
            "created_at",
            "items",
            "items_input",
        ]
        read_only_fields = ["total_amount"]

    def create(self, validated_data):
        items_data = validated_data.pop("items_input")
        order = Order.objects.create(**validated_data)
        for item in items_data:
            OrderItem.objects.create(
                order=order,
                product=item["product"],
                quantity=item["quantity"],
                unit_price=item["product"].price,
            )
        # total_amount is recalculated server-side by the trg_recalc_order_total
        # trigger (docker/init-sql/01_schema.sql), not by application code.
        order.refresh_from_db()
        return order
