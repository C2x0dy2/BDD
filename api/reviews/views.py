from datetime import datetime, timezone

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Product
from catalog.serializers import ProductSerializer

from .mongo_client import product_specs_collection, reviews_collection
from .serializers import ProductSpecsSerializer, ReviewSerializer


def _require_product(product_id):
    """Postgres is the source of truth for product identity: any Mongo
    read/write keyed by product_id must first confirm the product exists
    there, so a review can never reference a product that doesn't exist."""
    return Product.objects.filter(id=product_id).exists()


def _serialize_doc(doc):
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return doc


def product_rating_stats(product_id):
    pipeline = [
        {"$match": {"product_id": product_id}},
        {"$group": {"_id": None, "average_rating": {"$avg": "$rating"}, "review_count": {"$sum": 1}}},
    ]
    result = list(reviews_collection().aggregate(pipeline))
    if not result:
        return {"average_rating": None, "review_count": 0}
    return {
        "average_rating": round(result[0]["average_rating"], 2),
        "review_count": result[0]["review_count"],
    }


class ProductSpecsView(APIView):
    def get(self, request, product_id):
        doc = product_specs_collection().find_one({"product_id": product_id})
        if doc is None:
            return Response({"detail": "No specs for this product."}, status=status.HTTP_404_NOT_FOUND)
        return Response(_serialize_doc(doc))

    def put(self, request, product_id):
        if not _require_product(product_id):
            return Response({"detail": "Product not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = ProductSpecsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        update = {**serializer.validated_data, "updated_at": datetime.now(timezone.utc)}
        product_specs_collection().update_one(
            {"product_id": product_id}, {"$set": update, "$setOnInsert": {"product_id": product_id}}, upsert=True
        )
        doc = product_specs_collection().find_one({"product_id": product_id})
        return Response(_serialize_doc(doc))


class ProductReviewsView(APIView):
    def get(self, request, product_id):
        query = {"product_id": product_id}

        min_rating = request.query_params.get("min_rating")
        if min_rating is not None:
            query["rating"] = {"$gte": int(min_rating)}

        has_replies = request.query_params.get("has_replies")
        if has_replies is not None:
            # "replies.0" exists <=> the embedded replies array is non-empty.
            query["replies.0"] = {"$exists": has_replies.lower() == "true"}

        docs = reviews_collection().find(query).sort("created_at", -1).limit(50)
        return Response([_serialize_doc(d) for d in docs])

    def post(self, request, product_id):
        if not _require_product(product_id):
            return Response({"detail": "Product not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        doc = {
            **serializer.validated_data,
            "product_id": product_id,
            "created_at": datetime.now(timezone.utc),
            "replies": [],
        }
        result = reviews_collection().insert_one(doc)
        doc["_id"] = result.inserted_id
        return Response(_serialize_doc(doc), status=status.HTTP_201_CREATED)


class ProductReviewStatsView(APIView):
    def get(self, request, product_id):
        if not _require_product(product_id):
            return Response({"detail": "Product not found."}, status=status.HTTP_404_NOT_FOUND)

        stats = product_rating_stats(product_id)

        distribution_pipeline = [
            {"$match": {"product_id": product_id}},
            {"$group": {"_id": "$rating", "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}},
        ]
        distribution = {
            row["_id"]: row["count"]
            for row in reviews_collection().aggregate(distribution_pipeline)
        }

        return Response({**stats, "rating_distribution": distribution})


class ProductSpecsSearchView(APIView):
    """Cross-catalog search over the embedded, category-dependent
    attributes -- demonstrates filtering on nested fields with operators
    ($gte/$lte for a range, exact match on a nested field), which a plain
    lookup by product_id does not."""

    def get(self, request):
        query = {}

        category = request.query_params.get("category")
        if category is not None:
            query["category"] = category

        color = request.query_params.get("color")
        if color is not None:
            query["attributes.color"] = color

        weight_range = {}
        min_weight = request.query_params.get("min_weight")
        if min_weight is not None:
            weight_range["$gte"] = float(min_weight)
        max_weight = request.query_params.get("max_weight")
        if max_weight is not None:
            weight_range["$lte"] = float(max_weight)
        if weight_range:
            query["attributes.weight_kg"] = weight_range

        docs = product_specs_collection().find(query).limit(50)
        return Response([_serialize_doc(d) for d in docs])


class ProductDetailsView(APIView):
    """Cross-database endpoint: identity/price/stock come from PostgreSQL
    (source of truth for the product itself); descriptive specs and review
    stats come from MongoDB (source of truth for flexible content)."""

    def get(self, request, product_id):
        try:
            product = Product.objects.select_related("category").get(id=product_id)
        except Product.DoesNotExist:
            return Response({"detail": "Product not found."}, status=status.HTTP_404_NOT_FOUND)

        specs_doc = product_specs_collection().find_one({"product_id": product_id})

        return Response({
            "product": ProductSerializer(product).data,
            "specs": _serialize_doc(specs_doc) if specs_doc else None,
            "rating": product_rating_stats(product_id),
        })
