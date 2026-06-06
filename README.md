# IncidentIQ

**AI-powered institutional memory for engineering teams**

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Django](https://img.shields.io/badge/Django-5.1-green)
![Google ADK](https://img.shields.io/badge/Google_ADK-2.1.0-orange)
![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-green)
![Railway](https://img.shields.io/badge/Deployed-Railway-purple)

**Live Demo:** [https://web-production-4435e.up.railway.app](https://web-production-4435e.up.railway.app)

**Hackathon:** Google Cloud Rapid Agent Hackathon — MongoDB Track

## The Problem

Engineers lose institutional knowledge every time an incident is resolved informally. The same errors get debugged from scratch repeatedly. Senior developer knowledge walks out the door when they leave.

## The Solution

IncidentIQ is an autonomous AI agent that captures every incident, generates structured postmortems using Gemini 2.5 Flash, and stores them with semantic embeddings in MongoDB Atlas. When a new error occurs, the agent searches 32+ past incidents using vector similarity to find what your team already knows. Two lines of code integrate it into any Django application automatically.

## Demo GIF

<!-- Demo GIF here -->

> Try it live: https://web-production-4435e.up.railway.app

## How It Works

```text
Input -> extract_error -> search_memory -> generate_postmortem -> store_incident -> Output
```

1. `extract_error` cleans the raw error log and derives a short incident title.
2. `search_memory` embeds the cleaned log with `gemini-embedding-001` and searches MongoDB Atlas Vector Search for similar incidents.
3. `generate_postmortem` prompts Gemini 2.5 Flash with the current log and retrieved incident context.
4. `store_incident` persists the structured postmortem, source log, embedding, and timestamp in MongoDB Atlas.

## Tech Stack

| Layer | Technology |
| --- | --- |
| Agent Orchestration | Google ADK 2.1.0 + LangGraph |
| LLM | Gemini 2.5 Flash (google-genai SDK) |
| Embeddings | gemini-embedding-001 (3072 dimensions) |
| Vector Search | MongoDB Atlas Vector Search (cosine similarity) |
| Backend | Django 5 + Django REST Framework |
| Database | MongoDB Atlas (pymongo, no ORM) |
| Deployment | Railway |
| Partner Track | MongoDB Atlas |

## Key Features

- Autonomous incident capture via AutoCaptureMiddleware
- Semantic similarity search across 32+ past incidents
- Structured postmortem generation (root cause, fix, prevention)
- Google ADK agent orchestration with LangGraph pipeline
- Self-hostable — incident data stays in your MongoDB cluster
- Zero-config integration (2 lines of code)

## API Endpoints

| Method | Path | Description |
| --- | --- | --- |
| POST | `/api/analyze/` | Runs the LangGraph incident agent directly |
| POST | `/api/adk/analyze/` | Runs the Google ADK-wrapped agent; primary frontend path |
| GET | `/api/incidents/` | Lists all stored incidents with JSON-safe fields |
| GET | `/api/health/` | Returns `{"status": "ok"}` for health checks |

## Quick Start

```bash
git clone <repo-url> && cd incidentiq
cp .env.example .env
# Fill MONGODB_URI, GEMINI_API_KEY, GOOGLE_CLOUD_PROJECT, INCIDENTIQ_URL, DJANGO_SECRET_KEY
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py runserver
```

## Auto-Capture Integration

Add IncidentIQ to any Django app and unhandled exceptions become searchable incident memory:

```python
MIDDLEWARE.insert(1, "incidents.middleware.AutoCaptureMiddleware")
INCIDENTIQ_URL = os.getenv("INCIDENTIQ_URL", "http://localhost:8000")
```

`AutoCaptureMiddleware` listens only on `process_exception()`, skips `/api/` and `/static/` to prevent loops, and posts tracebacks to `/api/adk/analyze/` in a daemon thread with a 30-second timeout. The request still fails normally for the user, while IncidentIQ captures the stack trace, generates the postmortem, and stores the lesson for the next engineer.

## Architecture

```text
Browser
  -> GET /
  -> Django TemplateView
  -> frontend/index.html

Browser
  -> POST /api/adk/analyze/          (frontend default)
  -> AutoCaptureMiddleware (pass-through — /api/ prefix skipped)
  -> AdkAnalyzeView
  -> run_adk_agent(error_log)
  -> ADK Runner + FunctionTool (must call analyze_incident)
  -> run_agent(error_log)
  -> LangGraph pipeline
  -> MongoDB + Gemini
  -> JSON response

Browser
  -> POST /api/analyze/              (legacy, untouched)
  -> AutoCaptureMiddleware (pass-through — /api/ prefix skipped)
  -> AnalyzeView
  -> run_agent(error_log)
  -> LangGraph pipeline
  -> MongoDB + Gemini
  -> JSON response

Unhandled exception on any non-/api/ non-/static/ route
  -> AutoCaptureMiddleware.process_exception()
  -> daemon thread
  -> POST /api/adk/analyze/ (fire-and-forget, 30 s timeout)
  -> ADK pipeline stores the incident automatically
```

## Hackathon Notes

- Track: MongoDB
- Google Cloud tools used: Gemini 2.5 Flash, Google ADK 2.1.0
- Partner integration: MongoDB Atlas Vector Search
- Agent type: Autonomous incident resolution agent
