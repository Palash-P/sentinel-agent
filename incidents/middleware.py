"""Django middleware that auto-captures unhandled exceptions to the ADK pipeline.

Fires a background thread (daemon, fire-and-forget) that POSTs the exception
traceback to POST /api/adk/analyze/ so it is stored and analysed automatically.
The middleware never blocks the main response — all errors are swallowed and
logged as warnings.
"""
from __future__ import annotations

import logging
import threading
import traceback
from typing import Any, Callable

import requests
from django.conf import settings
from django.http import HttpRequest, HttpResponse

logger = logging.getLogger(__name__)

_IGNORED_PREFIXES = ("/api/", "/static/")
_IGNORED_EXCEPTIONS = (KeyboardInterrupt, SystemExit)


def _get_base_url() -> str:
    """Return the base URL for the self-submission request."""
    return getattr(settings, "INCIDENTIQ_URL", "http://localhost:8000")


def _post_to_adk(error_log: str) -> None:
    """Send the error log to the ADK analyze endpoint; called from a background thread."""
    try:
        url = _get_base_url().rstrip("/") + "/api/adk/analyze/"
        requests.post(url, json={"error_log": error_log}, timeout=30)
    except Exception as exc:
        logger.warning("AutoCaptureMiddleware: background POST failed: %s", exc)


class AutoCaptureMiddleware:
    """Fire-and-forget middleware that ships unhandled exceptions to the ADK agent."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        """Store the next middleware/view callable."""
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Pass the request through; exception capture happens in process_exception."""
        return self.get_response(request)

    def process_exception(
        self, request: HttpRequest, exception: BaseException
    ) -> None:
        """Capture unhandled exceptions and forward them to the ADK endpoint."""
        try:
            if isinstance(exception, _IGNORED_EXCEPTIONS):
                return None

            path = request.path_info or ""
            if any(path.startswith(prefix) for prefix in _IGNORED_PREFIXES):
                return None

            error_log = "".join(
                traceback.format_exception(type(exception), exception, exception.__traceback__)
            )

            thread = threading.Thread(
                target=_post_to_adk,
                args=(error_log,),
                daemon=True,
            )
            thread.start()

        except Exception as exc:
            logger.warning("AutoCaptureMiddleware: process_exception failed: %s", exc)

        return None
