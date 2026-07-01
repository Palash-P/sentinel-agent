# Sentinel — Agent System

## Project
Sentinel is an autonomous incident-resolution platform for engineering teams.
It triages production alerts, diagnoses root cause via RAG over past incidents,
proposes remediation steps, gates destructive actions behind human approval,
and writes self-improving postmortems back into its own memory after each resolution.

Built on Google ADK multi-agent orchestration, LangGraph utility nodes,
MongoDB Atlas Vector Search, Gemini 2.5 Flash, and GitHub MCP integration.

## Stack
- Python 3.13, Django 5, Django REST Framework
- MongoDB Atlas via pymongo (NOT Django ORM — raw documents only)
- Google ADK 2.x — multi-agent orchestration (primary)
- LangGraph — utility node functions (used as tools by ADK agents)
- Gemini 2.5 Flash via google-genai SDK
- GitHub MCP server — commit correlation in DiagnosisAgent
- Deployment: Railway
- Frontend: Single index.html, vanilla JS, dark theme

## Rules — NEVER break these
- NEVER use Django ORM or SQLite. MongoDB only.
- NEVER commit .env or any file containing API keys
- NEVER use print() for debugging — use Python logging module
- NEVER install packages not in requirements.txt without telling me
- NEVER let an agent answer without invoking its required tools first
- NEVER allow destructive actions (restart, delete, drop, rollback, flush, truncate)
  without explicit human approval from the Guardrail agent
- Always use environment variables for:
  MONGODB_URI, GEMINI_API_KEY, GOOGLE_CLOUD_PROJECT,
  SENTINEL_URL, GITHUB_TOKEN, GITHUB_MCP_URL

## Code Style
- Type hints on all function signatures
- Every function needs a one-line docstring
- Error handling on all external calls (MongoDB, Gemini API, MCP)
- No bare except clauses — always catch specific exceptions

## Agent System — 5 Agents

### 1. OrchestratorAgent (ADK root agent)
- Entry point for all incident analysis requests
- Delegates to sub-agents in sequence: Triage → Diagnosis → Remediation → Guardrail
- Uses ADK `sub_agents` parameter for real multi-agent delegation
- Returns final structured postmortem dict to the API layer
- Model: gemini-2.5-flash

### 2. TriageAgent (ADK sub-agent)
- Classifies incident severity: P1 (critical/production down), P2 (degraded), P3 (warning)
- Determines ownership category: infra, backend, frontend, database, external
- Tools: `classify_severity(error_log)` → severity + category + confidence
- Must always call classify_severity before returning
- Model: gemini-2.5-flash

### 3. DiagnosisAgent (ADK sub-agent)
- Embeds the error log and retrieves top-3 similar past incidents via Atlas Vector Search
- Calls GitHub MCP to fetch last 5 commits for deploy correlation
- Synthesizes root cause from log + similar incidents + recent commits
- Tools:
  - `search_similar_incidents(error_log)` — RAG over MongoDB Vector Search
  - GitHub MCP tool: `list_commits(repo, limit=5)` — recent deploy correlation
- Must always call both tools before generating root cause
- Model: gemini-2.5-flash

### 4. RemediationAgent (ADK sub-agent)
- Proposes concrete fix steps based on root cause and similar past fixes
- Flags any step containing destructive keywords:
  restart, delete, drop, rollback, flush, truncate, reset, purge
- Tools: `generate_remediation(root_cause, similar_incidents)` → steps + risk_flags
- Must always call generate_remediation before returning
- Model: gemini-2.5-flash

### 5. GuardrailAgent (ADK sub-agent)
- Reviews remediation steps for risk_flags
- If risk_flags is non-empty: sets `requires_approval: true`, surfaces approval_request
- If risk_flags is empty: sets `requires_approval: false`, passes through
- Tools: `evaluate_risk(steps, risk_flags)` → approval decision
- This is the safety layer — never bypass it
- Model: gemini-2.5-flash

### 6. ReflectionAgent (post-resolution, separate ADK agent)
- Runs after incident is stored in MongoDB
- Generates an enriched postmortem summary combining:
  root cause + fix applied + prevention steps + severity + similar incident count
- Re-embeds the summary and writes it back to MongoDB with `reflection: true` flag
- This creates a self-improving memory: future similar incidents get richer RAG context
- Tools: `generate_reflection(incident_doc)` → reflection_doc
- Model: gemini-2.5-flash

## Agent Files
incidents/
  adk_agent.py        # OrchestratorAgent — root ADK agent, sub_agents wiring
  agents/
    triage.py         # TriageAgent definition + classify_severity tool
    diagnosis.py      # DiagnosisAgent definition + search + MCP tools
    remediation.py    # RemediationAgent definition + generate_remediation tool
    guardrail.py      # GuardrailAgent definition + evaluate_risk tool
    reflection.py     # ReflectionAgent definition + generate_reflection tool

## Skills (Reusable ADK FunctionTools)
All tool functions are defined as standalone ADK FunctionTool skills:
- `classify_severity` — severity classification skill
- `search_similar_incidents` — RAG search skill (wraps existing find_similar_incidents)
- `list_commits` — GitHub MCP commit fetch skill
- `generate_remediation` — fix step generation skill
- `evaluate_risk` — guardrail risk evaluation skill
- `generate_reflection` — postmortem reflection skill

## API Endpoints
- POST /api/sentinel/analyze/    — primary; runs full multi-agent pipeline
- POST /api/sentinel/approve/    — approves a pending guardrail action
- GET  /api/incidents/           — list all incidents
- GET  /api/health/              — health check
- POST /api/analyze/             — legacy LangGraph path (keep, do not remove)
- POST /api/adk/analyze/         — legacy ADK path (keep, do not remove)

## Guardrail Approval Flow
1. RemediationAgent flags destructive steps → risk_flags non-empty
2. GuardrailAgent sets requires_approval: true
3. API returns 202 with approval_token + pending steps
4. Human reviews and POSTs to /api/sentinel/approve/ with approval_token
5. Pipeline resumes and stores the approved incident
6. If no approval within 10 minutes: incident stored with status: pending_approval

## MongoDB Collections (sentinel_agent database)
- incidents     — all incident documents (existing schema + new fields)
- reflections   — self-improving postmortem summaries (reflection: true)
- approvals     — pending guardrail approval requests

## Incident Document Schema (extended)
{
  _id: ObjectId,
  title: string,
  error_log: string,
  severity: "P1" | "P2" | "P3",
  ownership: "infra" | "backend" | "frontend" | "database" | "external",
  root_cause: string,
  fix_applied: string,
  prevention_steps: [string],
  remediation_steps: [string],
  risk_flags: [string],
  requires_approval: boolean,
  github_commits: [{ sha, message, author, date }],
  similar_incident_count: number,
  embedding: [float],
  created_at: ISODate,
  status: "resolved" | "pending_approval" | "reflected"
}

## Commands
- Run server: python manage.py runserver
- Test MongoDB: python test_mongo.py
- Run eval: python eval/run_eval.py
- Setup vector index: python setup_vector_index.py
- Seed incidents: python seed_incidents.py
- Deploy check: python manage.py check --deploy

## When compacting
Always preserve: list of modified files, current agent structure,
any open errors, MongoDB collection schema, which agents are complete.
EOF