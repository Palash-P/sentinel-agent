# Sentinel — Dev Guide

## Environment Setup

```bash
# Clone and enter repo
git clone https://github.com/Palash-P/sentinel-agent.git
cd sentinel-agent

# Create virtualenv
python -m venv venv
source venv/Scripts/activate  # Windows Git Bash
# source venv/bin/activate    # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Copy env template and fill in values
cp .env.example .env
```

## Required Environment Variables

```env
# MongoDB
MONGODB_URI=mongodb+srv://...
MONGODB_DB_NAME=sentinel_agent
MONGODB_VECTOR_INDEX=incidents_vector_index
MONGODB_REFLECTIONS_INDEX=reflections_vector_index

# Gemini
GEMINI_API_KEY=...

# GitHub MCP
GITHUB_TOKEN=...
GITHUB_REPO_OWNER=Palash-P
GITHUB_REPO_NAME=sentinel-agent

# App
SENTINEL_URL=http://localhost:8000
DEBUG=True
```

## Running Locally

```bash
python manage.py runserver
```

## Common Commands

```bash
# Test MongoDB connection
python test_mongo.py

# Setup vector indexes (run once after new DB)
python setup_vector_index.py

# Seed demo incidents
python seed_incidents.py

# Run eval harness
python eval/run_eval.py

# Deploy check
python manage.py check --deploy
```

## Adding a New Agent

1. Create `incidents/agents/your_agent.py`
2. Define tool function with type hints + docstring
3. Wrap as `FunctionTool(func=your_tool)`
4. Define `Agent(name=..., tools=[...], instruction=...)`
5. Add to OrchestratorAgent `sub_agents` list in `adk_agent.py`
6. Add corresponding test case in `eval/synthetic_incidents.json`
7. Update `agents.md` and `architecture.md`

## Adding a New MCP Tool

1. Set MCP server URL in env var
2. In the relevant agent file, add MCP tool via ADK MCP integration
3. Add GITHUB_TOKEN (or relevant token) to `.env.example`
4. Test with `python -c "from incidents.agents.diagnosis import run_diagnosis; print(run_diagnosis('test'))"`
5. Document in `architecture.md` under MCP Integration

## Eval Harness

```bash
python eval/run_eval.py
# Outputs: eval/results/latest.json
# Prints: accuracy table per metric
```

Add new test cases to `eval/synthetic_incidents.json`:
```json
{
  "error_log": "...",
  "expected_severity": "P1",
  "expected_guardrail_triggered": true,
  "contains_destructive_action": true
}
```

## Git Workflow

```bash
# Feature branch per agent
git checkout -b feat/triage-agent
# ... build and test
git add .
git commit -m "feat: add TriageAgent with severity classification"
git push origin feat/triage-agent
# merge to master when working
git checkout master && git merge feat/triage-agent
```

## Never Do

- Never commit .env or .codex/config.toml
- Never use Django ORM — MongoDB only via pymongo
- Never use print() — use logging module
- Never bypass GuardrailAgent for destructive actions
- Never delete legacy /api/analyze/ or /api/adk/analyze/ endpoints
- Never hardcode API keys or tokens

## When Compacting Context

Always preserve:
- List of completed agents (triage/diagnosis/remediation/guardrail/reflection)
- List of modified files
- Current open errors or failing tests
- MongoDB collection schema version
- Which eval metrics are passing
EOF