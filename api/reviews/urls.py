from django.urls import path

from .views import (
    ProductDetailsView,
    ProductReviewDetailView,
    ProductReviewsView,
    ProductReviewStatsView,
    ProductSpecsSearchView,
    ProductSpecsView,
)

urlpatterns = [
    path("products/<int:product_id>/details/", ProductDetailsView.as_view(), name="product-details"),
    path("specs/search/", ProductSpecsSearchView.as_view(), name="product-specs-search"),
    path("products/<int:product_id>/specs/", ProductSpecsView.as_view(), name="product-specs"),
    path("products/<int:product_id>/reviews/", ProductReviewsView.as_view(), name="product-reviews"),
    path("products/<int:product_id>/reviews/<int:user_id>/", ProductReviewDetailView.as_view(), name="product-review-detail"),
    path("products/<int:product_id>/reviews/stats/", ProductReviewStatsView.as_view(), name="product-review-stats"),
]
