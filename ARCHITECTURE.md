# IncidentIQ Architecture

## Agent Flow
Input → extract_error → search_memory → generate_postmortem → store_incident → Output

## MongoDB Collections
- incidents: {title, error_log, root_cause, fix_applied, prevention_steps, embedding[], created_at}

## API Endpoints
- POST /api/analyze/     → runs agent, returns postmortem
- GET  /api/incidents/   → lists all past incidents
- GET  /api/health/      → returns {"status": "ok"}

## Key Decisions & Why
- Used pymongo raw documents (not Django ORM) → MongoDB doesn't need relational model
- LangGraph over simple chain → need visible reasoning steps for demo
- Cloudinary for file storage → Railway containers are ephemeral (learned from Nexus)