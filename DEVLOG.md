# IncidentIQ Development Log

**Last Updated:** May 23, 2026  
**Project State:** ~80% complete — core agent pipeline and API endpoints built, frontend/deployment files incomplete

---

## Completed Features

### Core Infrastructure
- ✅ **Django 5.1.4 + DRF 3.15.2** — Web framework and REST API layer
- ✅ **MongoDB Atlas via pymongo 4.10.1** — No Django ORM; raw document operations only
- ✅ **Environment-based config** — All secrets via `.env` (MONGODB_URI, GEMINI_API_KEY, etc.)
- ✅ **CORS + WhiteNoise** — django-cors-headers and whitenoise for static serving on Railway

### Agent Pipeline (LangGraph)
- ✅ **Linear 4-node graph** in `incidents/agent.py`:
  1. `extract_error()` — Clean error log, derive title from first line
  2. `search_memory()` — Generate embedding, vector search for similar incidents (top 3)
  3. `generate_postmortem()` — Prompt Gemini with context, return structured JSON
  4. `store_incident()` — Persist full document to MongoDB with embedding
- ✅ **Graph caching** — `_compiled_graph` singleton, lazily compiled on first `run_agent()` call
- ✅ **JSON serialization** — `_serialize_incidents()` handles BSON ObjectId → string, datetime → ISO format

### Gemini Integration (`incidents/gemini.py`)
- ✅ **Embedding generation** — `generate_embedding()` via `models/text-embedding-004`
- ✅ **Structured post-mortem** — `generate_postmortem()` returns `{root_cause, fix_applied, prevention_steps[]}`
- ✅ **JSON schema validation** — Enforces response format; raises on malformed JSON
- ✅ **Lazy SDK init** — `_configure()` ensures API key is set before first call
- ✅ **Error handling** — Catches `google_exceptions.GoogleAPIError`, logs context

### MongoDB Layer (`incidents/models.py` & `incidentiq/mongo.py`)
- ✅ **Incident dataclass** — Type hints, defaults, `to_document()` serializer
- ✅ **Client singleton** — `get_client()` w/ LRU cache, auto-reused per process
- ✅ **Collection helpers**:
  - `get_incidents_collection()` — Primary collection handle
  - `ensure_incidents_collection()` — Idempotent create + baseline indexes
  - `save_incident()` — Insert with validation, return `ObjectId`
  - `get_all_incidents()` — All documents, newest first (sort by `created_at`)
  - `find_similar_incidents()` — Vector search via `$vectorSearch` aggregation pipeline
- ✅ **Ping test** — `ping()` for connection diagnostics
- ✅ **Error handling** — All PyMongoError caught, logged, re-raised

### Settings & Config (`incidentiq/settings.py`)
- ✅ **Required environment variables** (with sensible defaults):
  - `MONGODB_URI` (required for production)
  - `GEMINI_API_KEY` (required for production)
  - `GEMINI_MODEL` → default `gemini-2.5-flash`
  - `GEMINI_EMBEDDING_MODEL` → default `models/text-embedding-004`
  - `MONGODB_DB_NAME` → default `incidentiq`
  - `MONGODB_INCIDENTS_COLLECTION` → default `incidents`
  - `MONGODB_VECTOR_INDEX` → default `incidents_vector_index`
  - `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`
- ✅ **Database** — SQLite in-memory only (Django requires it; no ORM used)
- ✅ **REST Framework** — JSON-only (no form data), no auth required for MVP

### Testing & Validation
- ✅ **`test_mongo.py`** — End-to-end round-trip test:
  - Boots Django + loads settings
  - Creates sample incident document via `Incident` dataclass
  - Inserts into MongoDB
  - Reads back and verifies round-trip
  - Cleans up test document

### Dependencies (`requirements.txt`)
All locked versions, production-ready:
```
Django==5.1.4
djangorestframework==3.15.2
django-cors-headers==4.6.0
gunicorn==23.0.0
whitenoise==6.8.2
python-dotenv==1.0.1
pymongo==4.10.1
motor==3.6.0
google-generativeai==0.8.3
langgraph==0.2.60
langchain==0.3.13
```

### Endpoints Implemented
- ✅ `GET /api/health/` — Returns `{"status": "ok"}`
- ✅ `POST /api/analyze/` — Accepts `{"error_log": "..."}`, runs `run_agent()`, returns postmortem JSON
- ✅ `GET /api/incidents/` — Lists stored incidents with JSON-safe `_id` and `created_at` fields

---

## Current State

### Working Code
- **Core agent graph** — Ready to invoke; accepts error log string, returns full post-mortem
- **API interface** — Analyze and incident-list endpoints are implemented with DRF APIView
- **MongoDB integration** — Functional; tested with test_mongo.py
- **Gemini connectivity** — Tested in isolation; requires valid API key
- **Type hints & logging** — All functions follow CLAUDE.md rules

### Code Quality
- ✅ Type hints on all signatures (Python 3.11+)
- ✅ Docstrings on all functions (one-line + full docstring modules)
- ✅ Error handling on all external calls (MongoDB, Gemini)
- ✅ No bare `except`, no print() statements
- ✅ No Django ORM usage

### Known Environment Setup
- GCP service account JSON exists (`gcp-service-account.json`) — for future GCP integrations
- `.env` file exists in editor but not committed (correct per CLAUDE.md)
- No `.env.example` created yet

---

## Open Issues & Missing Work

### 🔴 Critical — Blocking MVP
1. **MongoDB Vector Search Index not created**:
   - Agent tries to reference `settings.MONGODB_VECTOR_INDEX` in aggregation
   - Vector index must be created manually in MongoDB Atlas UI or via Atlas API
   - **Action needed:** Document setup steps or automate index creation

2. **No frontend** (`frontend/index.html`):
   - Currently no UI to test the API
   - Need single-page HTML with dark theme (per CLAUDE.md & ARCHITECTURE.md)

### 🟡 Important — Needed for Deployment
3. **No `Procfile`** for Railway deployment
   - Need entry point: `web: gunicorn incidentiq.wsgi`

4. **No seed data / bootstrap**:
   - When deployed fresh, incidents collection is empty
   - First query to vector search may fail or return no results
   - Consider: seed with synthetic incidents or handle gracefully

### 🟠 Nice-to-have
5. **Pagination for GET /api/incidents/**:
   - Large incident lists should be paginated or limited

6. **Error response standardization**:
   - What does the client see if Gemini times out? MongoDB fails? Agent validation fails?
   - Should standardize error schema in views

7. **Logging & observability**:
   - All functions log, but no centralized log aggregation setup for Railway
   - Consider: structured JSON logging for better cloud readability

8. **Docker support for local dev**:
    - No docker-compose.yml or Dockerfile for easier local setup

---

## Stopped At

**Last working checkpoint:** Agent pipeline complete, ready to invoke via `run_agent(error_log: str)`.

**What's ready to test:**
```python
from incidents.agent import run_agent

result = run_agent("""
java.lang.NullPointerException at CheckoutService.charge()
    at com.example.CheckoutService.charge(CheckoutService.java:42)
""")
print(result)
# → {title, error_log, root_cause, fix_applied, prevention_steps, similar_incidents, incident_id}
```

**Next immediate steps:**
1. Create `frontend/index.html`
   - Form to submit error logs
   - Display returned postmortem (root_cause, fix_applied, prevention_steps)
   - Show similar past incidents
   - Dark theme per CLAUDE.md

2. Set up MongoDB Vector Search index (manual or automated)
   - If manual: document in README
   - If automated: add utility function + call in Django startup

3. Create `Procfile`

---

## File Manifest

**Modified/Created:**
- `incidentiq/settings.py` — Django config + env var setup
- `incidentiq/mongo.py` — MongoDB client singleton
- `incidentiq/urls.py` — Root URL routing
- `incidentiq/asgi.py` — ASGI for Railway
- `incidentiq/wsgi.py` — WSGI for gunicorn
- `incidents/models.py` — Incident dataclass + MongoDB helpers
- `incidents/agent.py` — LangGraph 4-node pipeline
- `incidents/gemini.py` — Gemini embedding + post-mortem generation
- `incidents/views.py` — Health, analyze, and incident-list API views
- `incidents/urls.py` — Routes health, analyze, and incidents endpoints
- `incidents/apps.py` — Django app config
- `requirements.txt` — All dependencies locked
- `manage.py` — Django CLI
- `test_mongo.py` — Round-trip MongoDB test
- `.env.example` — Environment variable template

**Not yet created:**
- `frontend/index.html`
- `Procfile`

**Existing (for reference):**
- `CLAUDE.md` — Rules & project setup guide
- `ARCHITECTURE.md` — High-level design
- `.env` — Local secrets (never commit)
- `gcp-service-account.json` — GCP credentials (for future use)

---

## Notes for Next AI Session

### Key Invariants (Do NOT Break)
- Never use Django ORM; MongoDB only
- Type hints + docstrings on all functions
- No print(); use logging module
- No bare except clauses
- All external calls (MongoDB, Gemini) must have error handling

### Agent Node Structure (Stable)
The graph is linear and complete; adding nodes should be rare. If testing/debugging:
- Use `run_agent(error_log)` as the public API
- Each node receives and returns a `dict[str, Any]` (AgentState)
- State is **not** persisted between graph invocations; each call is independent

### MongoDB Schema (Current)
```javascript
{
  _id: ObjectId,
  title: string,           // Derived from error_log first line
  error_log: string,       // Cleaned version (no extra blanks)
  root_cause: string,
  fix_applied: string,
  prevention_steps: [string],
  embedding: [float],      // Vector for similarity search
  created_at: ISODate
}
```

### Vector Search Setup
Vector index **must** exist at `settings.MONGODB_VECTOR_INDEX` (`incidents_vector_index` by default) with:
- **Field:** `embedding` (array of floats)
- **Similarity metric:** cosine (standard)
- **Dimensions:** 768 (text-embedding-004 output size)

If index is missing, `find_similar_incidents()` will raise `PyMongoError`.

### Build/Deploy Commands
```bash
# Local dev
python manage.py runserver

# Test MongoDB
python test_mongo.py

# Production (Railway)
gunicorn incidentiq.wsgi
```

### Common Issues to Watch
1. **MONGODB_URI not set** → RuntimeError on first `run_agent()` call
2. **GEMINI_API_KEY invalid** → google_exceptions.GoogleAPIError
3. **Vector index missing** → PyMongoError on similar-incident search
4. **Gemini returns non-JSON** → ValueError in `generate_postmortem()`

---

## Session History

- **Session 1 (May 23, 2026):**
  - Set up project structure and read CLAUDE.md, ARCHITECTURE.md
  - Implemented core agent pipeline (4-node LangGraph)
  - Integrated Gemini for embeddings + post-mortem generation
  - Set up MongoDB layer with vector search support
  - Created test_mongo.py for validation
  - **Stopped:** views.py only has health endpoint; API endpoints and frontend incomplete

