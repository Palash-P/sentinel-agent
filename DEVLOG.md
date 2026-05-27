# IncidentIQ Development Log

**Last Updated:** May 23, 2026  
**Project State:** Deployed MVP — core agent, API, frontend, and Railway deployment path are in place.

---

## Completed Today

### Full-Stack MVP
- Implemented `POST /api/analyze/` with DRF `APIView`; validates `error_log`, calls `run_agent()`, logs failures, and returns JSON.
- Implemented `GET /api/incidents/` with JSON-safe `_id` and `created_at` serialization; returns `[]` instead of 500 on list failures.
- Added `frontend/index.html` and served it at `/` via Django `TemplateView`.
- Added `BASE_DIR / "frontend"` to Django `TEMPLATES["DIRS"]`.

### Gemini + Embeddings
- Migrated from `google-generativeai` to the new `google-genai` package.
- Updated generation model usage to `GENERATION_MODEL = "gemini-2.5-flash"` in `incidents/gemini.py`.
- Updated embedding model usage to `EMBEDDING_MODEL = "gemini-embedding-001"`.
- Confirmed `generate_embedding()` uses `client.models.embed_content(...).embeddings[0].values`.
- Added `setup_vector_index.py` for MongoDB Atlas Vector Search setup with `EMBEDDING_DIMENSIONS = 3072`.

### Railway Deployment
- Added `Procfile`:
  `web: gunicorn incidentiq.wsgi:application --bind 0.0.0.0:$PORT`
- Updated `ALLOWED_HOSTS` fallback to `*` for Railway.
- Verified `STATIC_ROOT = BASE_DIR / "staticfiles"`.
- Verified WhiteNoise middleware is immediately after `SecurityMiddleware`.
- Marked live Railway deployment:
  `https://web-production-4435e.up.railway.app`

### Git Checkpoints
- `04e7f93` — `feat: core agent pipeline working end-to-end`
- `09fff9e` — `feat: frontend complete, full stack working locally`
- `e43a320` — `feat: ready for Railway deployment`
- `b864eb9` — `chore: live on Railway - https://web-production-4435e.up.railway.app`

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
- `GET /` — serves `frontend/index.html`
- `POST /api/analyze/` — runs the agent and returns the generated post-mortem.
- `GET /api/incidents/` — lists stored incidents.
- `GET /api/health/` — returns `{"status": "ok"}`.

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

- Railway deployment is live, but runtime verification should continue against the deployed URL.
- MongoDB Atlas Vector Search index setup is scripted in `setup_vector_index.py`; confirm the index exists in the target Atlas cluster.
- Frontend is present and served by Django; continue polishing UX/error states after live API testing.

---

## Open Issues

1. **Verify live Railway environment variables**
   - Required: `MONGODB_URI`, `GEMINI_API_KEY`, `GOOGLE_CLOUD_PROJECT`, `DJANGO_SECRET_KEY`.
   - Optional/current: `DJANGO_ALLOWED_HOSTS`, `DJANGO_DEBUG`, `MONGODB_DB_NAME`, `MONGODB_INCIDENTS_COLLECTION`, `MONGODB_VECTOR_INDEX`.

2. **Confirm Atlas Vector Search index**
   - `setup_vector_index.py` creates a 3072-dimension vector index.
   - If the index is missing, `find_similar_incidents()` can fail during `/api/analyze/`.

3. **Potential stale setting**
   - `incidentiq/settings.py` still defines `GEMINI_EMBEDDING_MODEL`, but `incidents/gemini.py` now uses the local `EMBEDDING_MODEL = "gemini-embedding-001"` constant.
   - Either remove the unused setting later or wire the constant back to config intentionally.

4. **Tests not fully run in this Codex shell**
   - `python` is not on PATH here.
   - Bundled Python lacks project dependencies such as `python-dotenv`.
   - Syntax parsing passed for edited Python files during the session.

5. **Nice-to-have backend hardening**
   - Pagination for `GET /api/incidents/`.
   - More standardized API error schema.
   - Better deployed logging/observability.
   - Seed incidents or graceful first-run behavior for empty Atlas collections.

---

## Current File Manifest

Modified/created project files:
- `incidentiq/settings.py` — env config, frontend templates dir, Railway settings.
- `incidentiq/urls.py` — root frontend route and API include.
- `incidentiq/mongo.py` — MongoDB client/collection helpers.
- `incidents/agent.py` — LangGraph pipeline.
- `incidents/gemini.py` — Google Gen AI Gemini generation and embeddings.
- `incidents/models.py` — MongoDB document helpers.
- `incidents/views.py` — API views for health, analyze, and incident list.
- `incidents/urls.py` — API URL routes.
- `frontend/index.html` — vanilla JS dark-theme frontend.
- `setup_vector_index.py` — Atlas Vector Search index helper.
- `requirements.txt` — Django, DRF, MongoDB, LangGraph, Google Gen AI dependencies.
- `Procfile` — Railway web process.
- `.env.example` — environment variable template.
- `test_mongo.py` — MongoDB round-trip diagnostic.

Never commit:
- `.env`
- API keys or service credentials
- `gcp-service-account.json`

---

## Commands

```bash
# Local server
python manage.py runserver

# MongoDB diagnostic
python test_mongo.py

# Create Atlas vector search index
python setup_vector_index.py

# Railway process command
gunicorn incidentiq.wsgi:application --bind 0.0.0.0:$PORT
```
