"""MongoDB client singleton.

The PyMongo client is created lazily on first access and reused for the lifetime
of the process. Use ``get_db()`` to obtain a database handle and
``get_incidents_collection()`` for the primary collection.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from django.conf import settings
from pymongo import ASCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import CollectionInvalid, PyMongoError

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_client() -> MongoClient:
    """Return the process-wide MongoClient, building it on first call."""
    if not settings.MONGODB_URI:
        raise RuntimeError("MONGODB_URI is not configured.")
    return MongoClient(settings.MONGODB_URI, appname="incidentiq")


def get_db() -> Database:
    """Return the configured application database handle."""
    return get_client()[settings.MONGODB_DB_NAME]


def get_incidents_collection() -> Collection:
    """Return the incidents collection handle."""
    return get_db()[settings.MONGODB_INCIDENTS_COLLECTION]


def ensure_incidents_collection() -> Collection:
    """Create the incidents collection (idempotent) and ensure baseline indexes."""
    db = get_db()
    name = settings.MONGODB_INCIDENTS_COLLECTION
    try:
        db.create_collection(name)
        logger.info("Created MongoDB collection %s", name)
    except CollectionInvalid:
        logger.debug("MongoDB collection %s already exists", name)
    collection = db[name]
    collection.create_index([("created_at", ASCENDING)], name="created_at_idx")
    return collection


def ping() -> bool:
    """Return True if MongoDB responds to an admin ping, False otherwise."""
    try:
        get_client().admin.command("ping")
        return True
    except PyMongoError as exc:
        logger.warning("MongoDB ping failed: %s", exc)
        return False
