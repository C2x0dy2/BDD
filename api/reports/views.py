from rest_framework.response import Response
from rest_framework.views import APIView

from . import queries


class SalesByCategoryView(APIView):
    def get(self, request):
        return Response(queries.sales_by_category())


class TopSellingProductsView(APIView):
    def get(self, request):
        limit = int(request.query_params.get("limit", 10))
        return Response(queries.top_selling_products(limit=limit))


class CategoriesWithProductCountsView(APIView):
    def get(self, request):
        return Response(queries.categories_with_product_counts())


class FrequentCustomersView(APIView):
    def get(self, request):
        min_orders = int(request.query_params.get("min_orders", 3))
        return Response(queries.frequent_customers(min_orders=min_orders))


class CustomersWithoutOrdersView(APIView):
    def get(self, request):
        return Response(queries.customers_without_orders())


class MonthlyRevenueView(APIView):
    def get(self, request):
        return Response(queries.monthly_revenue())


class OrderStatusBreakdownView(APIView):
    def get(self, request):
        return Response(queries.order_status_breakdown())
