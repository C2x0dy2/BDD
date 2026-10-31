from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from . import queries


def _positive_int(request, name, default):
    """Query-string integer >= 1, or a 400 instead of a 500 on bad input."""
    raw = request.query_params.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ValidationError({name: "Must be an integer."})
    if value < 1:
        raise ValidationError({name: "Must be >= 1."})
    return value


class SalesByCategoryView(APIView):
    def get(self, request):
        return Response(queries.sales_by_category())


class TopSellingProductsView(APIView):
    def get(self, request):
        limit = _positive_int(request, "limit", 10)
        return Response(queries.top_selling_products(limit=limit))


class CategoriesWithProductCountsView(APIView):
    def get(self, request):
        return Response(queries.categories_with_product_counts())


class FrequentCustomersView(APIView):
    # Lists customers' emails and names: personal data, staff only.
    permission_classes = [IsAdminUser]

    def get(self, request):
        min_orders = _positive_int(request, "min_orders", 3)
        return Response(queries.frequent_customers(min_orders=min_orders))


class CustomersWithoutOrdersView(APIView):
    # Lists customers' emails and names: personal data, staff only.
    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response(queries.customers_without_orders())


class MonthlyRevenueView(APIView):
    def get(self, request):
        return Response(queries.monthly_revenue())


class OrderStatusBreakdownView(APIView):
    def get(self, request):
        return Response(queries.order_status_breakdown())
