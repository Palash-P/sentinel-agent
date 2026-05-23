"""Create the MongoDB Atlas Vector Search index for IncidentIQ."""
from __future__ import annotations

import logging
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "incidentiq.settings")

import django
from django.conf import settings
from pymongo.errors import PyMongoError
from pymongo.operations import SearchIndexModel

from incidentiq.mongo import get_incidents_collection

logger = logging.getLogger(__name__)

EMBEDDING_DIMENSIONS = 3072


def setup_vector_index() -> str:
    """Create the incidents vector search index and return its name."""
    django.setup()
    collection = get_incidents_collection()
    search_index = SearchIndexModel(
        definition={
            "fields": [
                {
                    "type": "vector",
                    "path": "embedding",
                    "numDimensions": EMBEDDING_DIMENSIONS,
                    "similarity": "cosine",
                }
            ]
        },
        name=settings.MONGODB_VECTOR_INDEX,
        type="vectorSearch",
    )

    try:
        collection.create_search_index(search_index)
    except PyMongoError as exc:
        logger.exception("Failed to create vector search index: %s", exc)
        raise

    logger.info("Created vector search index %s", settings.MONGODB_VECTOR_INDEX)
    return settings.MONGODB_VECTOR_INDEX


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    setup_vector_index()
