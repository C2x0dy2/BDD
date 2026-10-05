from rest_framework import viewsets

from .models import Customer, Order
from .serializers import CustomerSerializer, OrderSerializer


class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer

    def get_queryset(self):
        queryset = Order.objects.select_related("customer").prefetch_related("items__product")
        customer_id = self.request.query_params.get("customer")
        if customer_id is not None:
            queryset = queryset.filter(customer_id=customer_id)
        return queryset
