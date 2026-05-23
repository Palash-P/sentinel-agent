"""Smoke test for the MongoDB Atlas connection.

Boots Django settings, ensures the incidents collection exists, inserts one
sample incident document, reads it back, verifies the round-trip, and cleans
up. Run with: ``python test_mongo.py``.
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Any

import django
from dotenv import load_dotenv
from pymongo.errors import PyMongoError

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("test_mongo")


def bootstrap_django() -> None:
    """Load .env and initialise Django so settings/imports work standalone."""
    load_dotenv()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "incidentiq.settings")
    django.setup()


def build_sample_document() -> dict[str, Any]:
    """Return a representative incident document for the round-trip test."""
    from incidents.models import Incident

    incident = Incident(
        title="test: NullPointerException in checkout",
        error_log="java.lang.NullPointerException at CheckoutService.charge(CheckoutService.java:42)",
        root_cause="Stripe client returned null when API key was missing.",
        fix_applied="Added a startup check that fails fast if STRIPE_API_KEY is unset.",
        prevention_steps=[
            "Add STRIPE_API_KEY to required-env validation",
            "Cover the missing-key path with a unit test",
        ],
    )
    return incident.to_document()


def run() -> int:
    """Execute the insert/read/delete cycle. Returns a process exit code."""
    bootstrap_django()

    from incidentiq.mongo import ensure_incidents_collection, ping

    if not ping():
        logger.error("Could not reach MongoDB — check MONGODB_URI in .env.")
        return 1

    try:
        collection = ensure_incidents_collection()
        logger.info("Using collection: %s.%s", collection.database.name, collection.name)

        document = build_sample_document()
        insert_result = collection.insert_one(document)
        inserted_id = insert_result.inserted_id
        logger.info("Inserted document _id=%s", inserted_id)

        fetched = collection.find_one({"_id": inserted_id})
        if fetched is None:
            logger.error("Insert succeeded but read-back returned nothing.")
            return 2

        if fetched.get("title") != document["title"]:
            logger.error("Round-trip mismatch: title differs.")
            return 3

        logger.info("Read-back OK — title=%r tags=%s", fetched["title"], fetched.get("tags"))

        delete_result = collection.delete_one({"_id": inserted_id})
        logger.info("Cleanup: deleted %d document(s)", delete_result.deleted_count)
        return 0
    except PyMongoError as exc:
        logger.exception("MongoDB operation failed: %s", exc)
        return 4


if __name__ == "__main__":
    sys.exit(run())
