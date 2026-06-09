# IncidentIQ — Hackathon Project

## Project
Django + LangGraph agent that analyzes error logs, finds similar 
past incidents via MongoDB Atlas Vector Search, and generates 
post-mortems using Gemini 2.5 Flash via google-genai SDK.

## Stack
- Python 3.11, Django 5, Django REST Framework
- MongoDB Atlas via pymongo (NOT Django ORM — raw documents only)
- LangGraph for agent orchestration
- Gemini 2.5 Flash via google-genai SDK
- Google ADK 2.1.0 for agent orchestration wrapper
- AutoCaptureMiddleware for automatic exception capture
- Deployment: Railway
- Frontend: Single index.html, vanilla JS, dark theme

## Rules — NEVER break these
- NEVER use Django ORM or SQLite. MongoDB only.
- NEVER commit .env or any file containing API keys
- NEVER use print() for debugging — use Python logging module
- NEVER install packages not in requirements.txt without telling me
- Always use environment variables for: MONGODB_URI, GEMINI_API_KEY, 
  GOOGLE_CLOUD_PROJECT, INCIDENTIQ_URL

## Code Style
- Type hints on all function signatures
- Every function needs a one-line docstring
- Error handling on all external calls (MongoDB, Gemini API)
- No bare except clauses — always catch specific exceptions

## Project Structure
incidentiq/
  manage.py
  incidentiq/settings.py
  incidents/
    models.py       # MongoDB document helpers only
    agent.py        # LangGraph agent
    adk_agent.py    # Google ADK wrapper around run_agent()
    gemini.py       # Gemini embedding + postmortem generation
    middleware.py   # AutoCaptureMiddleware — fire-and-forget exception capture
    views.py        # DRF API views
    urls.py
  frontend/index.html
  requirements.txt
  Procfile
  .env.example

## API Endpoints
- POST /api/analyze/      — LangGraph direct
- POST /api/adk/analyze/  — Google ADK wrapped (primary)
- GET  /api/incidents/    — list all incidents
- GET  /api/health/       — health check

## ADK Behavior
- `incidents/adk_agent.py` exposes `analyze_incident` as the only ADK tool.
- The ADK Agent instruction must always require calling `analyze_incident` for any error log input, regardless of length.
- Never allow the ADK Agent to answer directly without calling the tool first.

## Agent Behavior
- `extract_error()` must derive titles from lines containing `Error:`, `Exception:`, `Warning:`, or `Failed` before using fallback lines.
- If no marker line exists, use the last non-empty traceback line; use the first line only as the final fallback.
- Do not use `Traceback (most recent call last):` as the incident title when a specific error line is present.

## Commands
- Run server: python manage.py runserver
- Test MongoDB: python test_mongo.py  
- Deploy check: python manage.py check --deploy

## When compacting
Always preserve: list of modified files, current agent node 
structure, any open errors, MongoDB collection schema.
