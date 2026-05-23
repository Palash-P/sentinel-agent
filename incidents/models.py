"""Incident document schema and persistence helpers.

Incidents live in MongoDB rather than Django's ORM. ``Incident`` describes the
document shape via a dataclass for type hints and IDE support; the helpers
below read and write raw documents through pymongo.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from django.conf import settings
from pymongo import DESCENDING
from pymongo.errors import PyMongoError

from incidentiq.mongo import get_incidents_collection

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = ("title", "error_log")


@dataclass
class Incident:
    """In-memory representation of an incident document."""

    title: str
    error_log: str
    root_cause: str = ""
    fix_applied: str = ""
    prevention_steps: list[str] = field(default_factory=list)
    embedding: list[float] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_document(self) -> dict[str, Any]:
        """Convert this incident into a plain dict suitable for MongoDB."""
        return asdict(self)


def save_incident(data: dict[str, Any]) -> ObjectId:
    """Insert an incident document into MongoDB and return the new ``_id``."""
    if not isinstance(data, dict):
        raise TypeError(f"save_incident expects a dict, got {type(data).__name__}")

    missing = [name for name in REQUIRED_FIELDS if not data.get(name)]
    if missing:
        raise ValueError(f"Incident is missing required field(s): {', '.join(missing)}")

    document = dict(data)
    document.setdefault("created_at", datetime.now(timezone.utc))

    try:
        result = get_incidents_collection().insert_one(document)
    except PyMongoError as exc:
        logger.exception("Failed to insert incident: %s", exc)
        raise

    logger.info("Saved incident _id=%s title=%r", result.inserted_id, document["title"])
    return result.inserted_id


def get_all_incidents() -> list[dict[str, Any]]:
    """Return all incident documents, newest first."""
    try:
        cursor = get_incidents_collection().find().sort("created_at", DESCENDING)
        return list(cursor)
    except PyMongoError as exc:
        logger.exception("Failed to fetch incidents: %s", exc)
        raise


def find_similar_incidents(
    embedding: list[float],
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """Return the ``top_k`` incidents most similar to ``embedding`` via Atlas Vector Search."""
    if not isinstance(embedding, list) or not embedding:
        raise ValueError("embedding must be a non-empty list of floats.")
    if not isinstance(top_k, int) or top_k <= 0:
        raise ValueError("top_k must be a positive integer.")

    pipeline: list[dict[str, Any]] = [
        {
            "$vectorSearch": {
                "index": settings.MONGODB_VECTOR_INDEX,
                "path": "embedding",
                "queryVector": embedding,
                "numCandidates": max(top_k * 10, 50),
                "limit": top_k,
            }
        },
        {
            "$project": {
                "_id": 1,
                "title": 1,
                "error_log": 1,
                "root_cause": 1,
                "fix_applied": 1,
                "prevention_steps": 1,
                "created_at": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]

    try:
        cursor = get_incidents_collection().aggregate(pipeline)
        results = list(cursor)
    except PyMongoError as exc:
        logger.exception("Vector search failed: %s", exc)
        raise

    logger.info("Vector search returned %d incident(s)", len(results))
    return results
