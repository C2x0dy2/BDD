from functools import lru_cache

from django.conf import settings
from pymongo import MongoClient


@lru_cache(maxsize=1)
def get_database():
    client = MongoClient(settings.MONGO_URI)
    return client[settings.MONGO_DB_NAME]


def product_specs_collection():
    return get_database().product_specs


def reviews_collection():
    return get_database().reviews
