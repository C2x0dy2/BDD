from django.urls import path

from .views import (
    ProductDetailsView,
    ProductReviewsView,
    ProductReviewStatsView,
    ProductSpecsView,
)

urlpatterns = [
    path("products/<int:product_id>/details/", ProductDetailsView.as_view(), name="product-details"),
    path("products/<int:product_id>/specs/", ProductSpecsView.as_view(), name="product-specs"),
    path("products/<int:product_id>/reviews/", ProductReviewsView.as_view(), name="product-reviews"),
    path("products/<int:product_id>/reviews/stats/", ProductReviewStatsView.as_view(), name="product-review-stats"),
]
