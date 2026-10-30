from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api_views import OrderStatusUpdateView, ProductViewSet

router = DefaultRouter()
router.register("products", ProductViewSet, basename="api-product")

urlpatterns = [
    path("", include(router.urls)),
    path("orders/<int:order_id>/status/", OrderStatusUpdateView.as_view(), name="api-order-status"),
]
