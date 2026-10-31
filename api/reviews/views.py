from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from e_commerce.models import Product

from . import services
from .serializers import ProductSerializer, ProductSpecsSerializer, ReviewSerializer


def _number(request, name, cast):
    """Optional numeric query parameter; 400 instead of 500 on bad input."""
    raw = request.query_params.get(name)
    if raw is None:
        return None
    try:
        return cast(raw)
    except ValueError:
        raise ValidationError({name: "Must be a number."})


def _require_product(product_id):
    """Postgres is the source of truth for product identity: any Mongo
    read/write keyed by product_id must first confirm the product exists
    there, so a review can never reference a product that doesn't exist."""
    return Product.objects.filter(id=product_id).exists()


class ProductSpecsView(APIView):
    def get(self, request, product_id):
        doc = services.get_product_specs(product_id)
        if doc is None:
            return Response({"detail": "No specs for this product."}, status=status.HTTP_404_NOT_FOUND)
        return Response(doc)

    def put(self, request, product_id):
        if not _require_product(product_id):
            return Response({"detail": "Product not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = ProductSpecsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        services.upsert_product_specs(product_id, **serializer.validated_data)
        return Response(services.get_product_specs(product_id))


    def delete(self, request, product_id):
        if not services.delete_product_specs(product_id):
            return Response({"detail": "No specs for this product."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProductSpecsSearchView(APIView):
    """Cross-catalog search over the embedded, category-dependent
    attributes -- demonstrates filtering on nested fields with operators
    ($gte/$lte for a range, exact match on a nested field), which a plain
    lookup by product_id does not."""

    def get(self, request):
        return Response(services.search_specs(
            category=request.query_params.get("category"),
            color=request.query_params.get("color"),
            min_weight=_number(request, "min_weight", float),
            max_weight=_number(request, "max_weight", float),
        ))


class ProductReviewsView(APIView):
    def get(self, request, product_id):
        docs = services.list_reviews_for_product(product_id)

        min_rating = _number(request, "min_rating", int)
        if min_rating is not None:
            docs = [d for d in docs if d["rating"] >= min_rating]

        has_replies = request.query_params.get("has_replies")
        if has_replies is not None:
            want = has_replies.lower() == "true"
            docs = [d for d in docs if bool(d.get("replies")) == want]

        return Response(docs)

    def post(self, request, product_id):
        if not _require_product(product_id):
            return Response({"detail": "Product not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        services.upsert_review(
            product_id,
            serializer.validated_data["user_id"],
            serializer.validated_data["rating"],
            serializer.validated_data["comment"],
        )
        doc = services.get_user_review(product_id, serializer.validated_data["user_id"])
        return Response(doc, status=status.HTTP_201_CREATED)


class ProductReviewDetailView(APIView):
    """One review = one (product, user) pair, so it is addressed by both."""

    def get(self, request, product_id, user_id):
        doc = services.get_user_review(product_id, user_id)
        if doc is None:
            return Response({"detail": "Review not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(doc)

    def put(self, request, product_id, user_id):
        if services.get_user_review(product_id, user_id) is None:
            return Response({"detail": "Review not found."}, status=status.HTTP_404_NOT_FOUND)

        data = request.data.copy()
        data["user_id"] = user_id
        serializer = ReviewSerializer(data=data)
        serializer.is_valid(raise_exception=True)

        services.upsert_review(
            product_id,
            user_id,
            serializer.validated_data["rating"],
            serializer.validated_data["comment"],
        )
        return Response(services.get_user_review(product_id, user_id))

    def delete(self, request, product_id, user_id):
        if not services.delete_review(product_id, user_id):
            return Response({"detail": "Review not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProductReviewStatsView(APIView):
    def get(self, request, product_id):
        if not _require_product(product_id):
            return Response({"detail": "Product not found."}, status=status.HTTP_404_NOT_FOUND)

        stats = services.rating_stats(product_id)
        distribution = services.rating_distribution(product_id)
        return Response({**stats, "rating_distribution": distribution})


class ProductDetailsView(APIView):
    """Cross-database endpoint: identity/price/stock come from PostgreSQL
    (source of truth for the product itself); descriptive specs and review
    stats come from MongoDB (source of truth for flexible content)."""

    def get(self, request, product_id):
        try:
            product = Product.objects.select_related("category").get(id=product_id)
        except Product.DoesNotExist:
            return Response({"detail": "Product not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            "product": ProductSerializer(product).data,
            "specs": services.get_product_specs(product_id),
            "rating": services.rating_stats(product_id),
        })
