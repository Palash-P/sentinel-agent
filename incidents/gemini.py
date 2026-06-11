"""Gemini integration for embeddings and post-mortem generation.

Wraps the ``google-genai`` SDK behind two narrow helpers:

    * :func:`generate_embedding` — vector representation for Atlas Vector Search.
    * :func:`generate_postmortem` — structured post-mortem from an error log
      and a list of similar past incidents.

The SDK clients are created from configured Gemini API keys in priority order
so 429 quota errors can fall through to backup keys during demos.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import google.genai as genai
from django.conf import settings
from google.genai import errors as genai_errors

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "gemini-embedding-001"
GENERATION_MODEL = "gemini-2.5-flash"

POSTMORTEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "root_cause": {"type": "string"},
        "fix_applied": {"type": "string"},
        "prevention_steps": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["root_cause", "fix_applied", "prevention_steps"],
}

def _configure() -> list[genai.Client]:
    """Create Gemini clients from configured API keys in rotation order."""
    keys = [
        getattr(settings, "GEMINI_API_KEY", ""),
        getattr(settings, "GEMINI_API_KEY_2", ""),
        getattr(settings, "GEMINI_API_KEY_3", ""),
    ]
    configured_keys = [key for key in keys if isinstance(key, str) and key.strip()]
    if not configured_keys:
        raise RuntimeError("GEMINI_API_KEY is not configured.")
    return [genai.Client(api_key=key) for key in configured_keys]


def _is_rate_limit_error(exc: genai_errors.APIError) -> bool:
    """Return True when a Gemini APIError represents HTTP 429 quota exhaustion."""
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    return status == 429 or "429" in str(exc)


def generate_embedding(text: str) -> list[float]:
    """Return an embedding vector for ``text`` using Gemini's embedding model."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("generate_embedding requires a non-empty string.")
    clients = _configure()

    for idx, client in enumerate(clients, start=1):
        try:
            result = client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=text,
            )
            break
        except genai_errors.APIError as exc:
            if _is_rate_limit_error(exc) and idx < len(clients):
                logger.warning("Embedding quota hit on Gemini API key %d; trying next key.", idx)
                continue
            logger.exception("Embedding request failed: %s", exc)
            raise

    if not result.embeddings or not result.embeddings[0].values:
        raise RuntimeError("Gemini embedding response was empty.")
    return [float(value) for value in result.embeddings[0].values]


def generate_postmortem(
    error_log: str,
    similar_incidents: list[dict[str, Any]],
) -> dict[str, Any]:
    """Generate a structured post-mortem with root_cause, fix_applied, prevention_steps."""
    if not isinstance(error_log, str) or not error_log.strip():
        raise ValueError("generate_postmortem requires a non-empty error_log.")
    if not isinstance(similar_incidents, list):
        raise TypeError("similar_incidents must be a list of incident documents.")
    clients = _configure()

    prompt = _build_postmortem_prompt(error_log, _format_similar_incidents(similar_incidents))

    for idx, client in enumerate(clients, start=1):
        try:
            response = client.models.generate_content(
                model=GENERATION_MODEL,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": POSTMORTEM_SCHEMA,
                    "temperature": 0.2,
                },
            )
            break
        except genai_errors.APIError as exc:
            if _is_rate_limit_error(exc) and idx < len(clients):
                logger.warning("Generation quota hit on Gemini API key %d; trying next key.", idx)
                continue
            logger.exception("Gemini generation failed: %s", exc)
            raise

    raw = (response.text or "").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("Gemini returned non-JSON output: %s", raw[:500])
        raise ValueError("Gemini returned non-JSON output.") from exc

    return {
        "root_cause": str(data.get("root_cause", "")).strip(),
        "fix_applied": str(data.get("fix_applied", "")).strip(),
        "prevention_steps": [str(step).strip() for step in data.get("prevention_steps", []) if str(step).strip()],
    }


def _extract_embedding_values(response: Any) -> list[float]:
    """Pull the first embedding vector from a google-genai embedding response."""
    embeddings = getattr(response, "embeddings", None)
    if embeddings:
        values = getattr(embeddings[0], "values", None)
        if values:
            return list(values)

    embedding = getattr(response, "embedding", None)
    if embedding:
        values = getattr(embedding, "values", embedding)
        return list(values)

    if isinstance(response, dict):
        value = response.get("embedding")
        if value:
            return list(value)
    return []


def _format_similar_incidents(incidents: list[dict[str, Any]]) -> str:
    """Render past incidents as a numbered context block for the prompt."""
    if not incidents:
        return "No similar past incidents were found."
    blocks: list[str] = []
    for idx, item in enumerate(incidents, start=1):
        blocks.append(
            f"[{idx}] {item.get('title', 'untitled')}\n"
            f"    error: {str(item.get('error_log', ''))[:500]}\n"
            f"    root cause: {item.get('root_cause', '')}\n"
            f"    fix: {item.get('fix_applied', '')}"
        )
    return "\n\n".join(blocks)


def _build_postmortem_prompt(error_log: str, similar_block: str) -> str:
    """Compose the prompt sent to Gemini for structured post-mortem generation."""
    return (
        "You are an SRE assistant helping draft a software incident post-mortem.\n"
        "Given a new error log and similar past incidents, return a concise JSON "
        "post-mortem with exactly three fields:\n"
        "  - root_cause: one short paragraph explaining the underlying cause.\n"
        "  - fix_applied: one short paragraph describing the remediation.\n"
        "  - prevention_steps: an array of short imperative bullet strings.\n"
        "Lean on the past incidents when they are clearly relevant; otherwise "
        "reason from the error log alone. Do not invent facts.\n\n"
        f"NEW ERROR LOG:\n{error_log}\n\n"
        f"SIMILAR PAST INCIDENTS:\n{similar_block}\n"
    )
