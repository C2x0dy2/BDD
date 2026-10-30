"""
JSON API views for PostgreSQL reads/writes (the e_commerce side of /api/).
Complements reviews/views.py (MongoDB) and reports/views.py (read-only SQL):
together they give every database both read and write endpoints under /api/,
not just through the HTML site.
"""
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .api_serializers import OrderStatusUpdateSerializer, ProductSerializer
from .models import Order, Product


class ProductViewSet(viewsets.ModelViewSet):
    """Full CRUD on products: GET/POST /api/products/, GET/PUT/PATCH/DELETE
    /api/products/{id}/. Lets a seller manage their catalog programmatically
    instead of only through the HTML dashboard."""
    queryset = Product.objects.select_related("category", "seller").all()
    serializer_class = ProductSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        seller_id = self.request.query_params.get("seller")
        if seller_id is not None:
            queryset = queryset.filter(seller_id=seller_id)
        return queryset


class OrderStatusUpdateView(APIView):
    """PATCH /api/orders/{id}/status/ -- a narrower write endpoint than full
    order CRUD (orders shouldn't be freely overwritten from outside the
    checkout flow), but still a real Postgres write through the API."""

    def patch(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return Response({"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = OrderStatusUpdateSerializer(order, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
