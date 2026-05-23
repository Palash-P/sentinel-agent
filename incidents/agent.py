"""LangGraph agent for incident resolution.

Linear graph::

    START → extract_error → search_memory → generate_postmortem → store_incident → END

State is threaded through each node and accumulates: the cleaned error log,
its embedding, retrieved similar past incidents, the generated post-mortem,
and finally the inserted incident's ``_id``. ``run_agent(error_log)`` compiles
the graph (cached) and returns a JSON-friendly dict for the API layer.
"""
from __future__ import annotations

import logging
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .gemini import generate_embedding
from .gemini import generate_postmortem as _gemini_postmortem
from .models import find_similar_incidents, save_incident

logger = logging.getLogger(__name__)

TITLE_MAX_LEN = 80
SIMILAR_TOP_K = 3


class AgentState(TypedDict, total=False):
    """Mutable state threaded through the LangGraph nodes."""

    raw_error_log: str
    cleaned_error_log: str
    title: str
    embedding: list[float]
    similar_incidents: list[dict[str, Any]]
    postmortem: dict[str, Any]
    incident_id: str


def extract_error(state: AgentState) -> dict[str, Any]:
    """Clean the raw error log and derive a short title."""
    raw = state.get("raw_error_log", "")
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("Agent received an empty error log.")

    lines = [line.rstrip() for line in raw.splitlines()]
    cleaned_lines: list[str] = []
    blank = False
    for line in lines:
        if line.strip():
            cleaned_lines.append(line)
            blank = False
        elif not blank:
            cleaned_lines.append("")
            blank = True
    cleaned = "\n".join(cleaned_lines).strip()

    first_meaningful = next((line for line in cleaned_lines if line.strip()), "incident")
    title = first_meaningful.strip()[:TITLE_MAX_LEN]

    logger.info("extract_error: title=%r length=%d", title, len(cleaned))
    return {"cleaned_error_log": cleaned, "title": title}


def search_memory(state: AgentState) -> dict[str, Any]:
    """Embed the cleaned log and retrieve similar past incidents."""
    text = state.get("cleaned_error_log", "")
    embedding = generate_embedding(text)
    similar = find_similar_incidents(embedding, top_k=SIMILAR_TOP_K)
    logger.info("search_memory: retrieved %d similar incidents", len(similar))
    return {"embedding": embedding, "similar_incidents": similar}


def generate_postmortem(state: AgentState) -> dict[str, Any]:
    """Ask Gemini to draft a structured post-mortem from log + retrieved context."""
    postmortem = _gemini_postmortem(
        state["cleaned_error_log"],
        state.get("similar_incidents", []),
    )
    logger.info(
        "generate_postmortem: root_cause_len=%d steps=%d",
        len(postmortem.get("root_cause", "")),
        len(postmortem.get("prevention_steps", [])),
    )
    return {"postmortem": postmortem}


def store_incident(state: AgentState) -> dict[str, Any]:
    """Persist the new incident document (with embedding and post-mortem) to MongoDB."""
    postmortem = state.get("postmortem", {})
    document = {
        "title": state.get("title", "incident"),
        "error_log": state.get("cleaned_error_log", ""),
        "root_cause": postmortem.get("root_cause", ""),
        "fix_applied": postmortem.get("fix_applied", ""),
        "prevention_steps": list(postmortem.get("prevention_steps", [])),
        "embedding": list(state.get("embedding", [])),
    }
    incident_id = save_incident(document)
    logger.info("store_incident: saved _id=%s", incident_id)
    return {"incident_id": str(incident_id)}


def _build_graph() -> Any:
    """Build and compile the linear agent graph."""
    graph = StateGraph(AgentState)
    graph.add_node("extract_error", extract_error)
    graph.add_node("search_memory", search_memory)
    graph.add_node("generate_postmortem", generate_postmortem)
    graph.add_node("store_incident", store_incident)
    graph.add_edge(START, "extract_error")
    graph.add_edge("extract_error", "search_memory")
    graph.add_edge("search_memory", "generate_postmortem")
    graph.add_edge("generate_postmortem", "store_incident")
    graph.add_edge("store_incident", END)
    return graph.compile()


_compiled_graph: Any = None


def _get_graph() -> Any:
    """Lazily compile and cache the LangGraph for process-wide reuse."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = _build_graph()
    return _compiled_graph


def run_agent(error_log: str) -> dict[str, Any]:
    """Run the full incident-resolution agent and return a JSON-friendly result."""
    if not isinstance(error_log, str) or not error_log.strip():
        raise ValueError("run_agent requires a non-empty error_log string.")

    initial: AgentState = {"raw_error_log": error_log}
    final = _get_graph().invoke(initial)

    postmortem = final.get("postmortem", {}) or {}
    return {
        "title": final.get("title", ""),
        "error_log": final.get("cleaned_error_log", ""),
        "root_cause": postmortem.get("root_cause", ""),
        "fix_applied": postmortem.get("fix_applied", ""),
        "prevention_steps": list(postmortem.get("prevention_steps", [])),
        "similar_incidents": _serialize_incidents(final.get("similar_incidents", []) or []),
        "incident_id": final.get("incident_id", ""),
    }


def _serialize_incidents(incidents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Make similar-incident dicts JSON-friendly (stringify ``_id`` and timestamps)."""
    serialized: list[dict[str, Any]] = []
    for incident in incidents:
        item = dict(incident)
        item.pop("embedding", None)
        if "_id" in item:
            item["_id"] = str(item["_id"])
        created = item.get("created_at")
        if created is not None and hasattr(created, "isoformat"):
            item["created_at"] = created.isoformat()
        serialized.append(item)
    return serialized
