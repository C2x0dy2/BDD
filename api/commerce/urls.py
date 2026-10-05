"""
URL configuration for commerce project.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from catalog.views import CategoryViewSet, ProductViewSet
from orders.views import CustomerViewSet, OrderViewSet

router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("products", ProductViewSet, basename="product")
router.register("customers", CustomerViewSet, basename="customer")
router.register("orders", OrderViewSet, basename="order")

urlpatterns = [
    path("api/", include(router.urls)),
    path("api/", include("reviews.urls")),
    path("api/reports/", include("reports.urls")),
]
