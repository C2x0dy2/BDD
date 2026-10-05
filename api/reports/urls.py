from django.urls import path

from .views import (
    CategoriesWithProductCountsView,
    CustomersWithoutOrdersView,
    FrequentCustomersView,
    MonthlyRevenueView,
    OrderStatusBreakdownView,
    SalesByCategoryView,
    TopSellingProductsView,
)

urlpatterns = [
    path("sales-by-category/", SalesByCategoryView.as_view(), name="report-sales-by-category"),
    path("top-selling-products/", TopSellingProductsView.as_view(), name="report-top-selling-products"),
    path("categories-with-product-counts/", CategoriesWithProductCountsView.as_view(), name="report-categories-with-product-counts"),
    path("frequent-customers/", FrequentCustomersView.as_view(), name="report-frequent-customers"),
    path("customers-without-orders/", CustomersWithoutOrdersView.as_view(), name="report-customers-without-orders"),
    path("monthly-revenue/", MonthlyRevenueView.as_view(), name="report-monthly-revenue"),
    path("order-status-breakdown/", OrderStatusBreakdownView.as_view(), name="report-order-status-breakdown"),
]
