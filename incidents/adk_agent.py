"""ADK wrapper around the existing LangGraph incident pipeline.

Minimal integration: exposes ``analyze_incident`` as a single ADK
FunctionTool that delegates all work to ``run_agent()``.  The ADK
Runner handles the Gemini reasoning loop; the tool result is captured
via a closure and returned directly so the API gets the same structured
dict as the existing ``/api/analyze/`` endpoint.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from django.conf import settings
from google.adk import Agent, Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool
from google.genai import types

from .agent import run_agent

logger = logging.getLogger(__name__)

_APP_NAME = "incidentiq"
_USER_ID = "api_user"
_MODEL = "gemini-2.5-flash"


def _ensure_api_key() -> None:
    """Map GEMINI_API_KEY → GOOGLE_API_KEY if the latter is absent."""
    if not os.environ.get("GOOGLE_API_KEY"):
        key = getattr(settings, "GEMINI_API_KEY", None)
        if key:
            os.environ["GOOGLE_API_KEY"] = key


def run_adk_agent(error_log: str) -> dict[str, Any]:
    """Run the ADK agent for the given error log and return the post-mortem dict."""
    if not isinstance(error_log, str) or not error_log.strip():
        raise ValueError("run_adk_agent requires a non-empty error_log string.")

    _ensure_api_key()

    # Mutable container so the tool closure can capture the pipeline result.
    captured: list[dict[str, Any]] = []

    def analyze_incident(error_log: str) -> dict[str, Any]:
        """Analyze an error log using the LangGraph pipeline and return a post-mortem."""
        result = run_agent(error_log)
        captured.append(result)
        return result

    tool = FunctionTool(func=analyze_incident)
    agent = Agent(
        name="incidentiq_agent",
        model=_MODEL,
        instruction=(
            "You are an incident analysis agent. "
            "When given an error log, you MUST call the analyze_incident tool "
            "and return its result. Do not respond without calling the tool first."
        ),
        tools=[tool],
    )

    session_service = InMemorySessionService()
    runner = Runner(
        agent=agent,
        app_name=_APP_NAME,
        session_service=session_service,
    )
    session = session_service.create_session_sync(
        app_name=_APP_NAME,
        user_id=_USER_ID,
    )

    message = types.Content(
        role="user",
        parts=[types.Part(text=error_log)],
    )

    for _event in runner.run(
        user_id=_USER_ID,
        session_id=session.id,
        new_message=message,
    ):
        pass  # drain the event stream; result is captured in the closure above

    if not captured:
        raise RuntimeError("ADK agent did not invoke the analyze_incident tool.")

    logger.info("run_adk_agent: completed incident_id=%s", captured[0].get("incident_id"))
    return captured[0]
