# Sentinel Architecture

## Overview
Sentinel is a Django + DRF application with a Google ADK multi-agent
incident-resolution system, MongoDB Atlas document storage, Atlas Vector
Search memory, GitHub MCP integration, Gemini generation, and a
single-file vanilla JS frontend.

Live Railway deployment: https://[new-sentinel-railway-url]

## Request Flow

```text
Browser
  -> POST /api/sentinel/analyze/
  -> SentinelAnalyzeView
  -> run_sentinel_agent(error_log)
  -> OrchestratorAgent (ADK root)
       -> TriageAgent          (severity + ownership classification)
       -> DiagnosisAgent       (RAG search + GitHub MCP commits + root cause)
       -> RemediationAgent     (fix steps + risk flag detection)
       -> GuardrailAgent       (approval gate for destructive actions)
  -> ReflectionAgent           (post-resolution self-improving memory write)
  -> MongoDB store
  -> JSON response (200 resolved | 202 pending_approval)
```

## Multi-Agent Flow

```text
START
  → OrchestratorAgent
      → TriageAgent
          tool: classify_severity(error_log)
          output: { severity, ownership, confidence }
      → DiagnosisAgent
          tool: search_similar_incidents(error_log)     [RAG]
          tool: list_commits(repo, limit=5)              [GitHub MCP]
          output: { root_cause, similar_incidents, commits }
      → RemediationAgent
          tool: generate_remediation(root_cause, similar_incidents)
          output: { remediation_steps, risk_flags }
      → GuardrailAgent
          tool: evaluate_risk(steps, risk_flags)
          if risk_flags empty:   { requires_approval: false } → continue
          if risk_flags present: { requires_approval: true  } → return 202
  → ReflectionAgent (always runs post-resolution)
          tool: generate_reflection(incident_doc)
          writes enriched postmortem back to MongoDB
          re-embeds and stores with reflection: true
  → store_incident (saves full document to MongoDB)
END
```

## ADK Agent Wiring

```python
# Conceptual structure — see incidents/adk_agent.py for implementation
triage_agent     = Agent(name="triage",     tools=[classify_severity])
diagnosis_agent  = Agent(name="diagnosis",  tools=[search_similar_incidents, list_commits])
remediation_agent= Agent(name="remediation",tools=[generate_remediation])
guardrail_agent  = Agent(name="guardrail",  tools=[evaluate_risk])

orchestrator = Agent(
    name="sentinel_orchestrator",
    sub_agents=[triage_agent, diagnosis_agent, remediation_agent, guardrail_agent],
    instruction="..."
)
```

## MCP Integration

GitHub MCP server provides commit history for deploy correlation:
- Tool: list_commits(owner, repo, limit=5)
- Called by DiagnosisAgent during root cause analysis
- Purpose: correlates "incident started at T" with "last deploy at T-5min"
- Config: GITHUB_TOKEN env var, GITHUB_MCP_URL env var

## Guardrail Approval Flow

```text
RemediationAgent flags: risk_flags = ["restart postgres", "drop table"]
GuardrailAgent: requires_approval = true
API returns 202:
{
  "status": "pending_approval",
  "approval_token": "uuid",
  "pending_steps": ["restart postgres", "drop table"],
  "safe_steps": ["check connection pool", "review logs"]
}
Human POSTs to /api/sentinel/approve/ with approval_token
Pipeline resumes → stores incident with status: resolved
```

## Reflection Loop (Self-Improving Memory)

```text
Incident resolved
  → ReflectionAgent generates enriched summary:
      "P1 database incident caused by connection pool exhaustion.
       Fixed by restarting connection pool. Prevention: add pool
       size monitoring. Similar to 3 past incidents."
  → generate_embedding(summary) → 3072-dim vector
  → store in MongoDB reflections collection with reflection: true
  → future DiagnosisAgent RAG searches include reflections
  → system gets measurably better at diagnosis over time
```

## MongoDB Collections

Database: sentinel_agent

incidents collection:
```javascript
{
  _id: ObjectId,
  title: string,
  error_log: string,
  severity: "P1" | "P2" | "P3",
  ownership: string,
  root_cause: string,
  fix_applied: string,
  prevention_steps: [string],
  remediation_steps: [string],
  risk_flags: [string],
  requires_approval: boolean,
  github_commits: [{ sha, message, author, date }],
  similar_incident_count: number,
  embedding: [float],          // 3072-dim gemini-embedding-001
  created_at: ISODate,
  status: "resolved" | "pending_approval" | "reflected"
}
```

reflections collection:
```javascript
{
  _id: ObjectId,
  incident_id: ObjectId,       // reference to source incident
  summary: string,             // enriched postmortem summary
  embedding: [float],          // 3072-dim embedding of summary
  reflection: true,            // always true — filter flag
  created_at: ISODate
}
```

approvals collection:
```javascript
{
  _id: ObjectId,
  approval_token: string,      // UUID
  incident_data: object,       // full incident snapshot
  pending_steps: [string],
  status: "pending" | "approved" | "rejected" | "expired",
  created_at: ISODate,
  expires_at: ISODate          // created_at + 10 minutes
}
```

Atlas Vector Search indexes:
- incidents_vector_index: field=embedding, dims=3072, similarity=cosine
- reflections_vector_index: field=embedding, dims=3072, similarity=cosine

## API Endpoints

- POST /api/sentinel/analyze/  → primary multi-agent pipeline
- POST /api/sentinel/approve/  → guardrail approval
- GET  /api/incidents/         → list incidents
- GET  /api/health/            → health check
- POST /api/analyze/           → legacy LangGraph (keep)
- POST /api/adk/analyze/       → legacy ADK (keep)

## Eval Harness

eval/
  run_eval.py           # runs 20 synthetic incidents, scores results
  synthetic_incidents.json  # 20 test cases with expected outputs
  results/              # eval output JSON (committed to repo)

Scoring dimensions:
- severity_accuracy:   did agent classify P1/P2/P3 correctly?
- root_cause_quality:  does root_cause mention the actual error type?
- guardrail_triggered: did destructive actions correctly trigger approval?
- reflection_stored:   was reflection written back to MongoDB?

## Project Structure

sentinel-agent/
  incidentiq/           # Django project package (name unchanged)
    settings.py
    urls.py
    mongo.py
    wsgi.py / asgi.py
  incidents/
    models.py           # MongoDB helpers (extended schema)
    agent.py            # LangGraph utility nodes (used as tool functions)
    adk_agent.py        # OrchestratorAgent — entry point
    agents/
      __init__.py
      triage.py         # TriageAgent
      diagnosis.py      # DiagnosisAgent + MCP
      remediation.py    # RemediationAgent
      guardrail.py      # GuardrailAgent
      reflection.py     # ReflectionAgent
    gemini.py           # Gemini embedding + generation
    middleware.py       # AutoCaptureMiddleware
    views.py            # DRF views (extended)
    urls.py
  eval/
    run_eval.py
    synthetic_incidents.json
    results/
  frontend/
    index.html          # updated for Sentinel branding + approval UI
  requirements.txt
  Procfile
  .env.example

## Deployment

Railway: single web service, Procfile unchanged.