"""Severity and ownership triage for Sentinel incidents."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from google.adk import Agent, Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool
from google.genai import errors as genai_errors, types

from ..gemini import GENERATION_MODEL, _configure, _is_rate_limit_error

logger = logging.getLogger(__name__)

_APP_NAME = "sentinel_agent"
_USER_ID = "sentinel_triage"
_MODEL = "gemini-2.5-flash"

_TRIAGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "severity": {"type": "string", "enum": ["P1", "P2", "P3"]},
        "ownership": {
            "type": "string",
            "enum": ["infra", "backend", "frontend", "database", "external"],
        },
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "reasoning": {"type": "string"},
    },
    "required": ["severity", "ownership", "confidence", "reasoning"],
}

_P1_SIGNALS = (
    "production down",
    "service down",
    "site down",
    "api down",
    "database down",
    "complete outage",
    "outage",
    "all users",
    "all requests",
    "100% error",
    "unavailable",
    "data loss",
    "security breach",
    "critical",
    "fatal",
)
_P2_SIGNALS = (
    "degraded",
    "partial outage",
    "elevated error",
    "high latency",
    "latency",
    "timeout",
    "intermittent",
    "connection pool",
    "5xx",
    "500 error",
    "exception",
)
_OWNERSHIP_SIGNALS: dict[str, tuple[str, ...]] = {
    "infra": (
        "kubernetes",
        "k8s",
        "pod",
        "container",
        "docker",
        "dns",
        "load balancer",
        "cpu",
        "memory",
        "disk",
        "network",
        "node",
    ),
    "backend": (
        "backend",
        "server",
        "django",
        "traceback",
        "exception",
        "endpoint",
        "http 500",
        "500 error",
        "worker",
    ),
    "frontend": (
        "frontend",
        "browser",
        "javascript",
        "typescript",
        "react",
        "css",
        "dom",
        "client-side",
        "ui",
    ),
    "database": (
        "database",
        "mongodb",
        "mongo",
        "postgres",
        "postgresql",
        "mysql",
        "sql",
        "query",
        "deadlock",
        "replication",
        "connection pool",
    ),
    "external": (
        "third-party",
        "third party",
        "vendor",
        "upstream",
        "external api",
        "stripe",
        "github",
        "twilio",
        "sendgrid",
        "cloudflare",
    ),
}


def _classify_with_gemini(error_log: str) -> dict[str, Any]:
    """Ask Gemini to classify an incident and return its structured decision."""
    if not isinstance(error_log, str) or not error_log.strip():
        raise ValueError("_classify_with_gemini requires a non-empty error_log string.")

    ownership_hints = "\n".join(
        f"- {ownership}: {', '.join(signals)}"
        for ownership, signals in _OWNERSHIP_SIGNALS.items()
    )
    prompt = (
        "You are Sentinel's SRE incident triage specialist. Classify the incident "
        "from the error log and return JSON with exactly these fields: severity "
        "(P1, P2, or P3), ownership (infra, backend, frontend, database, or "
        "external), confidence (a number from 0.0 to 1.0), and reasoning (a concise "
        "explanation grounded in the log). P1 means critical or production down, "
        "P2 means degraded service, and P3 means a warning or low-impact issue. "
        "The following signals are context hints only; use the full log and your "
        "judgment to make the final classification.\n"
        f"P1 hints: {', '.join(_P1_SIGNALS)}\n"
        f"P2 hints: {', '.join(_P2_SIGNALS)}\n"
        f"Ownership hints:\n{ownership_hints}\n\n"
        f"ERROR LOG:\n{error_log}"
    )
    clients = _configure()

    for idx, client in enumerate(clients, start=1):
        try:
            logger.info("Requesting Gemini incident classification with API key %d", idx)
            response = client.models.generate_content(
                model=GENERATION_MODEL,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": _TRIAGE_SCHEMA,
                    "temperature": 0.1,
                },
            )
            break
        except genai_errors.APIError as exc:
            if _is_rate_limit_error(exc) and idx < len(clients):
                logger.warning(
                    "Triage quota hit on Gemini API key %d; trying next key.",
                    idx,
                )
                continue
            logger.exception("Gemini triage classification failed: %s", exc)
            raise

    raw = (response.text or "").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("Gemini returned non-JSON triage output: %s", raw[:500])
        raise ValueError("Gemini returned non-JSON triage output.") from exc
    if not isinstance(data, dict):
        raise ValueError("Gemini returned non-object triage JSON.")

    severity = str(data.get("severity", "")).strip()
    ownership = str(data.get("ownership", "")).strip()
    reasoning = str(data.get("reasoning", "")).strip()
    try:
        confidence = float(data.get("confidence"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Gemini returned an invalid triage confidence.") from exc

    if severity not in {"P1", "P2", "P3"}:
        raise ValueError("Gemini returned an invalid triage severity.")
    if ownership not in {"infra", "backend", "frontend", "database", "external"}:
        raise ValueError("Gemini returned an invalid triage ownership.")
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("Gemini returned triage confidence outside 0.0-1.0.")
    if not reasoning:
        raise ValueError("Gemini returned empty triage reasoning.")

    return {
        "severity": severity,
        "ownership": ownership,
        "confidence": confidence,
        "reasoning": reasoning,
    }


def classify_severity(error_log: str) -> dict[str, Any]:
    """Classify an error log by incident severity and owning engineering area."""
    if not isinstance(error_log, str) or not error_log.strip():
        raise ValueError("classify_severity requires a non-empty error_log string.")
    return _classify_with_gemini(error_log)


def _ensure_api_key_alias() -> None:
    """Expose GEMINI_API_KEY under the ADK-compatible GOOGLE_API_KEY name."""
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    if gemini_api_key and not os.environ.get("GOOGLE_API_KEY"):
        os.environ["GOOGLE_API_KEY"] = gemini_api_key


def run_triage(error_log: str) -> dict[str, Any]:
    """Run TriageAgent for an error log and return its tool-produced classification."""
    if not isinstance(error_log, str) or not error_log.strip():
        raise ValueError("run_triage requires a non-empty error_log string.")

    _ensure_api_key_alias()
    logger.info("Starting ADK triage run")

    captured: list[dict[str, Any]] = []

    def classify_severity(error_log: str) -> dict[str, Any]:
        """Classify an error log and capture the tool result for the API caller."""
        result = _classify_with_gemini(error_log)
        captured.append(result)
        return result

    try:
        tool = FunctionTool(func=classify_severity)
        agent = Agent(
            name="triage_agent",
            model=_MODEL,
            tools=[tool],
            instruction=(
                "You are Sentinel's incident triage agent. For every incident, you "
                "MUST call classify_severity with the complete error log before "
                "returning. Never classify an incident yourself and never answer "
                "without invoking classify_severity first. Return the tool result "
                "without changing it."
            ),
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
            pass
    except Exception:
        logger.exception("ADK triage run failed")
        raise

    if not captured:
        logger.error("TriageAgent completed without invoking classify_severity")
        raise RuntimeError("TriageAgent did not invoke the classify_severity tool.")

    result = captured[0]
    logger.info(
        "Completed ADK triage run severity=%s ownership=%s",
        result.get("severity"),
        result.get("ownership"),
    )
    return result
