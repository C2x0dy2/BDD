"""
Shared MongoDB read/write logic for product reviews and specs.

Used by both the SÎKÂ HTML views (e_commerce/views.py) and the JSON API
(reviews/views.py), so the two never duplicate the same Mongo queries.
"""
from datetime import datetime, timezone

from .mongo_client import product_specs_collection, reviews_collection


def _serialize(doc):
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return doc


def list_reviews_for_product(product_id, limit=50):
    docs = (
        reviews_collection()
        .find({"product_id": product_id})
        .sort("created_at", -1)
        .limit(limit)
    )
    return [_serialize(d) for d in docs]


def get_user_review(product_id, user_id):
    doc = reviews_collection().find_one({"product_id": product_id, "user_id": user_id})
    return _serialize(doc) if doc else None


def upsert_review(product_id, user_id, rating, comment):
    """One review per (product, user): re-submitting updates it in place,
    matching SIKA's original 'un avis par produit par utilisateur' rule."""
    now = datetime.now(timezone.utc)
    reviews_collection().update_one(
        {"product_id": product_id, "user_id": user_id},
        {
            "$set": {"rating": rating, "comment": comment, "updated_at": now},
            "$setOnInsert": {
                "product_id": product_id,
                "user_id": user_id,
                "created_at": now,
                "replies": [],
            },
        },
        upsert=True,
    )


def rating_stats(product_id):
    pipeline = [
        {"$match": {"product_id": product_id}},
        {"$group": {"_id": None, "average_rating": {"$avg": "$rating"}, "review_count": {"$sum": 1}}},
    ]
    result = list(reviews_collection().aggregate(pipeline))
    if not result:
        return {"average_rating": None, "review_count": 0}
    return {
        "average_rating": round(result[0]["average_rating"], 1),
        "review_count": result[0]["review_count"],
    }


def rating_distribution(product_id):
    pipeline = [
        {"$match": {"product_id": product_id}},
        {"$group": {"_id": "$rating", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    return {row["_id"]: row["count"] for row in reviews_collection().aggregate(pipeline)}


def get_product_specs(product_id):
    doc = product_specs_collection().find_one({"product_id": product_id})
    return _serialize(doc) if doc else None


def upsert_product_specs(product_id, category, attributes, media=None, tags=None):
    now = datetime.now(timezone.utc)
    product_specs_collection().update_one(
        {"product_id": product_id},
        {
            "$set": {
                "category": category,
                "attributes": attributes,
                "media": media or [],
                "tags": tags or [],
                "updated_at": now,
            },
            "$setOnInsert": {"product_id": product_id},
        },
        upsert=True,
    )


def search_specs(category=None, color=None, min_weight=None, max_weight=None, limit=50):
    """Filter product_specs on nested fields with operators ($gte/$lte on
    attributes.weight_kg, exact match on attributes.color)."""
    query = {}
    if category is not None:
        query["category"] = category
    if color is not None:
        query["attributes.color"] = color
    weight_range = {}
    if min_weight is not None:
        weight_range["$gte"] = float(min_weight)
    if max_weight is not None:
        weight_range["$lte"] = float(max_weight)
    if weight_range:
        query["attributes.weight_kg"] = weight_range
    docs = product_specs_collection().find(query).limit(limit)
    return [_serialize(d) for d in docs]
