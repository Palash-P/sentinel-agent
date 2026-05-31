# IncidentIQ Development Log

**Last Updated:** June 1, 2026  
**Project State:** Submission-ready MVP with Google ADK integration and auto-capture middleware. Deployed, documented, seeded, and pushed to GitHub on `main`.

---

## Completed June 1, 2026

### Google ADK Integration
- Installed `google-adk==2.1.0`; pinned in `requirements.txt`.
- Created `incidents/adk_agent.py`: wraps `run_agent()` as an ADK `FunctionTool`, builds an `Agent` + `InMemorySessionService` + `Runner` per request, and returns the tool result via closure capture.
- Added `AdkAnalyzeView` to `incidents/views.py` — mirrors `AnalyzeView` but routes through `run_adk_agent()`.
- Added `POST /api/adk/analyze/` route to `incidents/urls.py`.
- Updated `frontend/index.html` fetch target from `/api/analyze/` to `/api/adk/analyze/`.
- `GOOGLE_API_KEY` is mapped from `GEMINI_API_KEY` at runtime if absent so ADK picks it up without a separate env var.

### AutoCaptureMiddleware
- Created `incidents/middleware.py` with `AutoCaptureMiddleware`.
- Fires on `process_exception()` only — zero overhead on normal requests.
- Ignores `/api/` and `/static/` paths (prevents infinite loop), `KeyboardInterrupt`, and `SystemExit`.
- Posts the formatted traceback to `POST /api/adk/analyze/` in a `daemon=True` background thread — never blocks the response.
- Uses `requests.post()` with a 30-second timeout; all errors swallowed and logged as `logger.warning()`.
- Inserted into `MIDDLEWARE` immediately after `SecurityMiddleware` in `settings.py`.
- Added `INCIDENTIQ_URL` setting (env var `INCIDENTIQ_URL`, default `http://localhost:8000`).
- Production test confirmed the middleware captures non-`/api/` exceptions and submits them through the ADK pipeline.
- `python manage.py check` passes with 0 issues.

---

## Completed May 27, 2026

### Submission Readiness
- Rewrote `README.md` as the hackathon-facing project brief for judges.
- Added the live demo URL: `https://web-production-4435e.up.railway.app`.
- Documented the problem statement, agent flow, tech stack, ASCII architecture, key features, setup steps, and API endpoints.
- Marked the hackathon track as **Google Cloud Rapid Agent - MongoDB track**.

### Demo Data Seeding
- Created `seed_incidents.py` with 15 realistic error logs covering Django, Python, Redis, PostgreSQL, MongoDB, Gemini, and Railway deployment failures.
- Added `requests==2.32.3` to `requirements.txt`.
- Added a 3-second `time.sleep(3)` delay between requests to reduce Gemini rate-limit pressure.
- Added `--indices` support for rerunning selected seed cases.
- Reran previously failed seed indices `7`, `8`, `10`, and `11`; all four succeeded.

### Security Cleanup
- Removed a GitHub personal access token from `.codex/config.toml`.
- Removed `.codex/config.toml` from Git tracking.
- Added `.codex/` to `.gitignore` so local Codex/MCP config is not committed again.
- Important: the exposed token appeared in earlier Git history and should be treated as compromised. It must remain revoked/rotated in GitHub.

### Documentation + Git
- Updated `DEVLOG.md` and `ARCHITECTURE.md` to reflect the deployed architecture.
- Committed the submission docs and seed script:
  `5426830 docs: README complete, 15 incidents seeded, project submission ready`
- Renamed the local branch from `master` to `main`.
- Pushed `main` to GitHub: `origin/main`.

---

## Current Architecture

### Agent Node Structure
The LangGraph flow is linear and stable:

`START -> extract_error -> search_memory -> generate_postmortem -> store_incident -> END`

- `extract_error()` cleans the raw log and derives a title.
- `search_memory()` generates an embedding and queries MongoDB Atlas Vector Search.
- `generate_postmortem()` calls Gemini and expects structured JSON.
- `store_incident()` persists the incident document to MongoDB.

### API Surface
- `GET /` - serves `frontend/index.html`.
- `POST /api/analyze/` - runs the agent and returns the generated post-mortem.
- `GET /api/incidents/` - lists stored incidents.
- `GET /api/health/` - returns `{"status": "ok"}`.

### MongoDB Collection Schema
```javascript
{
  _id: ObjectId,
  title: string,
  error_log: string,
  root_cause: string,
  fix_applied: string,
  prevention_steps: [string],
  embedding: [float],
  created_at: ISODate
}
```

Vector Search index requirements:
- Collection: `incidents`
- Field: `embedding`
- Type: vector
- Similarity: cosine
- Dimensions: `3072` for `gemini-embedding-001`
- Index name: `MONGODB_VECTOR_INDEX`, default `incidents_vector_index`

---

## In Progress

- Final live-demo verification on Railway before submission recording.
- Confirm GitHub default branch behavior if the remote still points `origin/HEAD` at `master`.
- Continue monitoring Gemini rate limits during demos; `seed_incidents.py` now throttles requests.

---

## Open Issues

1. **Compromised GitHub token must remain revoked**
   - The token was removed from the working tree and `.codex/` is now ignored.
   - Because it existed in earlier Git history, it should be considered permanently burned.
   - If this repo is public or shared, consider history rewriting or repository secret scanning remediation.

2. **Confirm Atlas Vector Search index**
   - `setup_vector_index.py` creates a 3072-dimension vector index.
   - If the index is missing or dimension-mismatched, `/api/analyze/` can fail during `search_memory()`.

3. **Potential stale setting**
   - `incidentiq/settings.py` still defines `GEMINI_EMBEDDING_MODEL`.
   - `incidents/gemini.py` currently uses `EMBEDDING_MODEL = "gemini-embedding-001"` directly.
   - Later cleanup can remove the unused setting or intentionally wire it back in.

4. **Runtime environment checks**
   - Railway should have `MONGODB_URI`, `GEMINI_API_KEY`, `GOOGLE_CLOUD_PROJECT`, and `DJANGO_SECRET_KEY`.
   - Optional/current vars: `DJANGO_ALLOWED_HOSTS`, `DJANGO_DEBUG`, `MONGODB_DB_NAME`, `MONGODB_INCIDENTS_COLLECTION`, `MONGODB_VECTOR_INDEX`, `INCIDENTIQ_URL` (set to the Railway public URL for AutoCaptureMiddleware to self-POST correctly).

5. **Nice-to-have backend hardening**
   - Add pagination for `GET /api/incidents/`.
   - Standardize API error responses.
   - Improve deployed logging/observability.
   - Add automated tests for API views and agent node behavior.

---

## Current File Manifest

Modified/created project files:
- `README.md` - polished hackathon submission README.
- `incidentiq/settings.py` - env config, frontend templates dir, Railway settings, INCIDENTIQ_URL.
- `incidentiq/urls.py` - root frontend route and API include.
- `incidentiq/mongo.py` - MongoDB client/collection helpers.
- `incidents/agent.py` - LangGraph pipeline.
- `incidents/adk_agent.py` - Google ADK FunctionTool wrapper around run_agent().
- `incidents/gemini.py` - Google Gen AI Gemini generation and embeddings.
- `incidents/middleware.py` - AutoCaptureMiddleware (fire-and-forget exception capture).
- `incidents/models.py` - MongoDB document helpers.
- `incidents/views.py` - API views for health, analyze, ADK analyze, and incident list.
- `incidents/urls.py` - API URL routes including /api/adk/analyze/.
- `frontend/index.html` - vanilla JS dark-theme frontend (fetch target: /api/adk/analyze/).
- `setup_vector_index.py` - Atlas Vector Search index helper.
- `seed_incidents.py` - live API seed script with throttling and index selection.
- `requirements.txt` - Django, DRF, MongoDB, LangGraph, Google Gen AI, and requests dependencies.
- `Procfile` - Railway web process.
- `.env.example` - environment variable template.
- `.gitignore` - ignores local secrets and Codex config.
- `test_mongo.py` - MongoDB round-trip diagnostic.

Never commit:
- `.env`
- API keys or service credentials
- `gcp-service-account.json`
- `.codex/`

---

## Commands

```bash
# Local server
python manage.py runserver

# MongoDB diagnostic
python test_mongo.py

# Create Atlas vector search index
python setup_vector_index.py

# Seed all demo incidents
python seed_incidents.py

# Rerun selected seed incidents
python seed_incidents.py --indices 7 8 10 11

# Railway process command
gunicorn incidentiq.wsgi:application --bind 0.0.0.0:$PORT
```
