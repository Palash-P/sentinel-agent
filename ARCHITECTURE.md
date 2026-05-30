# IncidentIQ Architecture

## Overview

IncidentIQ is a Django + DRF application with a LangGraph-powered incident analysis agent, MongoDB Atlas document storage, Atlas Vector Search memory, Gemini generation, and a single-file vanilla JS frontend served by Django.

Live Railway deployment:
`https://web-production-4435e.up.railway.app`

## Request Flow

```text
Browser
  -> GET /
  -> Django TemplateView
  -> frontend/index.html

Browser
  -> POST /api/analyze/
  -> AnalyzeView
  -> run_agent(error_log)
  -> LangGraph pipeline
  -> MongoDB + Gemini
  -> JSON response
```

## Agent Flow

```text
START
  -> extract_error
  -> search_memory
  -> generate_postmortem
  -> store_incident
  -> END
```

Node responsibilities:
- `extract_error` cleans the raw error log and derives a short title.
- `search_memory` embeds the cleaned log with `gemini-embedding-001` and retrieves similar incidents from Atlas Vector Search.
- `generate_postmortem` prompts Gemini `gemini-2.5-flash` with the log and similar-incident context.
- `store_incident` stores the generated incident document in MongoDB.

## MongoDB Collections

`incidents` documents use raw PyMongo dictionaries only. Django ORM is not used for app data.

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

Atlas Vector Search:
- Index name: `MONGODB_VECTOR_INDEX`, default `incidents_vector_index`
- Field: `embedding`
- Dimensions: `3072`
- Similarity: `cosine`
- Setup helper: `setup_vector_index.py`

## API Endpoints

- `GET /` -> serves `frontend/index.html`
- `POST /api/analyze/` -> accepts `{"error_log": "..."}`, runs the agent, returns the postmortem.
- `GET /api/incidents/` -> lists past incidents with JSON-safe `_id` and `created_at`.
- `GET /api/health/` -> returns `{"status": "ok"}`.

## Deployment

Railway uses Nixpacks auto-detection. No `railway.json` is required.

`Procfile`:

```Procfile
web: gunicorn incidentiq.wsgi:application --bind 0.0.0.0:$PORT
```

Static/frontend serving:
- `frontend/index.html` is loaded through Django templates.
- `TEMPLATES["DIRS"]` includes `BASE_DIR / "frontend"`.
- `STATIC_ROOT = BASE_DIR / "staticfiles"`.
- WhiteNoise middleware is installed after `SecurityMiddleware`.

## Operational Utilities

- `setup_vector_index.py` creates the MongoDB Atlas Vector Search index for the `embedding` field.
- `seed_incidents.py` posts realistic demo error logs to `/api/analyze/` using `requests`.
- `seed_incidents.py` waits 3 seconds between requests to reduce Gemini rate-limit pressure.
- Selected seed incidents can be rerun with `python seed_incidents.py --indices 7 8 10 11`.

## Source Control Notes

- Active branch: `main`.
- Local `.codex/` configuration is ignored because it can contain machine-specific MCP settings or credentials.
- `.env`, service account files, and API keys must never be committed.

## Key Decisions

- MongoDB via PyMongo raw documents, not Django ORM.
- LangGraph over a simple chain so the demo has explicit, inspectable agent stages.
- Google Gen AI SDK (`google-genai`) for Gemini generation and embeddings.
- Single-file vanilla JS frontend for hackathon speed and Railway simplicity.
- Railway deployment through `Procfile` and Nixpacks auto-detection.
