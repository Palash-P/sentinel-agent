# IncidentIQ

An AI agent that helps developers resolve software incidents faster. Paste an
error log or traceback and the agent searches past incidents for similar
failures, drafts a structured post-mortem, and stores the new incident for
future retrieval.

Built for the **Google Cloud Rapid Agent Hackathon — MongoDB track**.

## Stack

- **Backend** — Django + Django REST Framework
- **Database** — MongoDB Atlas (vector search via `pymongo` / `motor`)
- **AI** — Gemini 1.5 Pro on Google Cloud Vertex AI
- **Agent** — LangGraph
- **Frontend** — single static HTML file (dark theme)
- **Deploy** — Railway

## Project layout

```
incidentiq/        Django project (settings, urls, wsgi, mongo client)
incidents/         App: models, views, LangGraph agent
manage.py
requirements.txt
.env.example
```

## Local setup

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env        # then fill in real values
python manage.py runserver
```

Verify the server is up:

```bash
curl http://127.0.0.1:8000/api/health/
# {"status": "ok"}
```

## Environment

See `.env.example`. The three groups of variables you need:

- **Django** — `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`
- **MongoDB Atlas** — `MONGODB_URI`, `MONGODB_DB_NAME`, `MONGODB_VECTOR_INDEX`
- **Gemini** — `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_EMBEDDING_MODEL`

## Endpoints

| Method | Path           | Purpose                |
| ------ | -------------- | ---------------------- |
| GET    | `/api/health/` | Liveness probe         |

More endpoints will be added as the agent is wired up.

## Deployment

Targets Railway. `gunicorn` and `whitenoise` are already in
`requirements.txt`; a `Procfile` / Railway config will be added later.

## Status

Scaffolding only — agent logic is not yet implemented.
