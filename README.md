# IncidentIQ

**AI incident-resolution agent that turns raw production error logs into searchable post-mortems.**

Live demo: [https://web-production-4435e.up.railway.app](https://web-production-4435e.up.railway.app)

Hackathon track: **Google Cloud Rapid Agent — MongoDB track**

## Problem Statement

Incident response is still too manual: engineers dig through noisy logs, search old Slack threads, guess whether a failure has happened before, and write post-mortems after the pressure has already peaked. The context that would make the next outage easier to solve is usually scattered or forgotten.

IncidentIQ closes that loop. It analyzes a fresh error log, retrieves similar past incidents from vector memory, generates a concise post-mortem, and stores the result so every incident improves the next response.

## How It Works

```text
extract_error -> search_memory -> generate_postmortem -> store_incident
```

1. `extract_error` cleans the submitted log and derives a useful incident title.
2. `search_memory` embeds the log with Gemini and searches MongoDB Atlas Vector Search for similar incidents.
3. `generate_postmortem` prompts Gemini with the new log and retrieved incident context.
4. `store_incident` saves the structured post-mortem and embedding back to MongoDB for future retrieval.

## Tech Stack

| Layer | Technology |
| --- | --- |
| Backend | Django 5, Django REST Framework |
| Agent orchestration | LangGraph |
| LLM | Gemini via `google-genai` |
| Embeddings | `gemini-embedding-001` |
| Vector memory | MongoDB Atlas Vector Search |
| Database access | PyMongo raw documents |
| Frontend | Single-file vanilla HTML/CSS/JS |
| Static serving | WhiteNoise |
| Deployment | Railway via Nixpacks + Gunicorn |

## Architecture

```text
                 +-----------------------------+
                 | Browser / Demo Frontend     |
                 | frontend/index.html         |
                 +--------------+--------------+
                                |
                                | POST /api/analyze/
                                v
                 +--------------+--------------+
                 | Django REST Framework API   |
                 | AnalyzeView / IncidentsView |
                 +--------------+--------------+
                                |
                                v
                 +--------------+--------------+
                 | LangGraph Agent             |
                 | extract -> search -> write  |
                 +------+---------------+------+
                        |               |
                        |               |
                        v               v
        +---------------+----+     +----+----------------+
        | MongoDB Atlas      |     | Gemini              |
        | Vector Search      |     | post-mortem JSON    |
        +---------------+----+     +----+----------------+
                        |               |
                        +-------+-------+
                                |
                                v
                 +--------------+--------------+
                 | Stored Incident Memory      |
                 | root cause, fix, embedding  |
                 +-----------------------------+
```

## Key Features

- Paste any Python, Django, Redis, PostgreSQL, MongoDB, or deployment error log and get a structured incident report.
- Retrieves similar historical incidents using MongoDB Atlas Vector Search.
- Generates post-mortems with root cause, fix applied, and prevention steps.
- Stores every analyzed incident as future memory.
- Clean dark-theme frontend for live demos.
- JSON API designed for easy integration into dashboards, CI/CD tools, or alerting workflows.
- Railway-ready deployment with Gunicorn, WhiteNoise, and environment-based configuration.
- No Django ORM for incident data; MongoDB raw documents are the system of record.

## Setup

Clone the repository:

```bash
git clone <your-repo-url>
cd incidentiq
```

Create and activate a virtual environment:

```bash
python -m venv venv
venv\Scripts\activate
```

Create your environment file:

```bash
copy .env.example .env
```

Fill in the required values:

```env
MONGODB_URI=your-mongodb-atlas-uri
GEMINI_API_KEY=your-google-ai-studio-key
GOOGLE_CLOUD_PROJECT=your-google-cloud-project
DJANGO_SECRET_KEY=your-django-secret
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the development server:

```bash
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

Optional MongoDB checks:

```bash
python test_mongo.py
python setup_vector_index.py
```

## API Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/` | Serves the demo frontend |
| `GET` | `/api/health/` | Health check, returns `{"status": "ok"}` |
| `POST` | `/api/analyze/` | Accepts `{"error_log": "..."}` and returns a generated post-mortem |
| `GET` | `/api/incidents/` | Lists stored incident memories |

Example analyze request:

```bash
curl -X POST https://web-production-4435e.up.railway.app/api/analyze/ \
  -H "Content-Type: application/json" \
  -d "{\"error_log\":\"django.db.utils.OperationalError: connection refused\"}"
```

## Why It Matters

IncidentIQ makes incident response cumulative. Instead of treating every outage as a blank page, the agent builds an operational memory that gets stronger with every failure analyzed.
