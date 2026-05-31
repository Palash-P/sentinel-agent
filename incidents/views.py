from __future__ import annotations

import logging
from typing import Any

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from .adk_agent import run_adk_agent
from .agent import run_agent
from .models import get_all_incidents

logger = logging.getLogger(__name__)


@api_view(["GET"])
def health(_request: Request) -> Response:
    """Return a simple API health check response."""
    return Response({"status": "ok"})


@api_view(["GET"])
def test_error(_request: Request) -> Response:
    """Raise a temporary exception for auto-capture testing."""
    raise RuntimeError("test auto-capture")


class AnalyzeView(APIView):
    """Run the incident agent for a submitted error log."""

    def post(self, request: Request) -> Response:
        """Analyze an error log and return a generated post-mortem."""
        error_log = request.data.get("error_log", "")
        if not isinstance(error_log, str) or not error_log.strip():
            return Response(
                {"error": "error_log is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = run_agent(error_log)
        except Exception as exc:
            logger.exception("Analyze endpoint failed: %s", exc)
            return Response(
                {"error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(result, status=status.HTTP_200_OK)


class AdkAnalyzeView(APIView):
    """Run the ADK-wrapped incident agent for a submitted error log."""

    def post(self, request: Request) -> Response:
        """Analyze an error log via the ADK agent and return a generated post-mortem."""
        error_log = request.data.get("error_log", "")
        if not isinstance(error_log, str) or not error_log.strip():
            return Response(
                {"error": "error_log is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = run_adk_agent(error_log)
        except Exception as exc:
            logger.exception("ADK analyze endpoint failed: %s", exc)
            return Response(
                {"error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(result, status=status.HTTP_200_OK)


class IncidentsView(APIView):
    """List stored incident documents."""

    def get(self, _request: Request) -> Response:
        """Return all incidents as JSON-friendly dictionaries."""
        try:
            incidents = get_all_incidents()
        except Exception as exc:
            logger.exception("Incidents endpoint failed: %s", exc)
            return Response([], status=status.HTTP_200_OK)

        return Response(
            [_serialize_incident(incident) for incident in incidents],
            status=status.HTTP_200_OK,
        )


def _serialize_incident(incident: dict[str, Any]) -> dict[str, Any]:
    """Convert MongoDB-only values into JSON-friendly fields."""
    item = dict(incident)
    if "_id" in item:
        item["_id"] = str(item["_id"])
    created_at = item.get("created_at")
    if created_at is not None and hasattr(created_at, "isoformat"):
        item["created_at"] = created_at.isoformat()
    return item
