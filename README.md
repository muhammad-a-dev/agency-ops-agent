# agency-ops-agent

[![CI](https://github.com/muhammad-a-dev/agency-ops-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/muhammad-a-dev/agency-ops-agent/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Tool-using agent API for agency operations automation demos.**

A small but serious FastAPI service that accepts a task, runs a bounded
plan/act tool loop, and returns a structured result with an audit trail.
Built as a public portfolio project for
[muhammad-a-dev](https://github.com/muhammad-a-dev).

> **Offline-first by design.** The default agent path needs **zero LLM API
> keys**. Heuristic planning + deterministic `summarize_text` keep local demos,
> tests, and CI green without network or paid models. An optional OpenAI-
> compatible path is gated behind an explicit env flag and never required.

See [CHANGELOG.md](CHANGELOG.md) for released changes.

---

## Problem

Agency ops teams repeatedly:

- pull a status page or brief,
- summarize it for clients,
- write a structured report,
- inspect what landed in a shared workspace.

Gluing those steps by hand (or with an unbounded "agent" that needs paid APIs
just to run demos) is noisy. This project shows a **clean, testable pattern**:
typed tools, sandboxing, job lifecycle, and audit logging — without pretending
to be a general autonomous agent.

## Solution

`agency-ops-agent` exposes a FastAPI job API plus an optional CLI:

1. **Create / run a job** with a natural-language task + optional context.
2. The **agent loop** plans tool calls (heuristic by default), validates
   arguments with Pydantic, executes real Python callables, and stops at
   `max_steps`.
3. You get a **structured final answer**, per-tool audit records, and files
   written only inside a sandbox workspace.

## Architecture

```
Client (HTTP / CLI)
        │
        ▼
   FastAPI routes  ──►  JobStore (create → run → get)
                              │
                              ▼
                           Agent loop
                     (plan → act → finalize)
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
         ToolRegistry     AuditLog        Settings
         (typed tools)   (memory/JSONL)  (pydantic-settings)
              │
    ┌─────────┼──────────┬──────────────┐
    ▼         ▼          ▼              ▼
 http_get  summarize  write_json    list_workspace
 (httpx)   (heuristic)  report      (sandbox FS)
```

| Module | Role |
|--------|------|
| `api.py` | Health, tools catalog, job create/run/get |
| `agent.py` | Bounded plan/act loop + structured answer |
| `tools.py` | Real callables + Pydantic argument schemas |
| `sandbox.py` | Path traversal rejection outside workspace |
| `audit.py` | In-memory + optional JSONL tool audit |
| `jobs.py` | In-memory job lifecycle |
| `settings.py` | Env-driven config (`AGENCY_OPS_*`) |
| `cli.py` | Offline single-task runner |

## Stack

- Python 3.11+
- FastAPI + Uvicorn
- httpx (HTTP tool)
- Pydantic v2 + pydantic-settings
- pytest, pytest-asyncio, respx (mocked network)
- ruff (lint + format)
- GitHub Actions CI

## Install

```bash
git clone https://github.com/muhammad-a-dev/agency-ops-agent.git
cd agency-ops-agent
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

## Configuration

All settings use the `AGENCY_OPS_` prefix (see `.env.example`):

| Variable | Default | Meaning |
|----------|---------|--------|
| `WORKSPACE_DIR` | `./workspace` | Sandbox root for file tools |
| `MAX_STEPS` | `8` | Agent loop cap |
| `HTTP_TIMEOUT_SECONDS` | `10` | httpx timeout |
| `HTTP_MAX_BYTES` | `1048576` | Max response body bytes |
| `AUDIT_LOG_PATH` | _(empty)_ | Optional JSONL audit file |
| `AGENT_LLM_ENABLED` | `false` | Opt-in LLM summarize path |
| `OPENAI_API_KEY` | _(empty)_ | Only used if LLM enabled |
| `OPENAI_MODEL` | `gpt-4o-mini` | Chat model id |
| `OPENAI_BASE_URL` | OpenAI API | Compatible base URL |
| `LOG_LEVEL` | `INFO` | Logging level |

### Optional LLM path

```bash
export AGENCY_OPS_AGENT_LLM_ENABLED=true
export AGENCY_OPS_OPENAI_API_KEY=sk-...
```

When the flag is off (default), `summarize_text` uses a **deterministic
sentence heuristic**. When the flag is on and a key is present, summarize may
call an OpenAI-compatible chat endpoint, with automatic fallback to the
heuristic on failure. **CI never requires keys.**

## Usage

### API server

```bash
uvicorn agency_ops_agent.api:app --reload --port 8000
```

Health check:

```bash
curl -s http://127.0.0.1:8000/health | jq
```

Create + run a job:

```bash
curl -s -X POST http://127.0.0.1:8000/jobs \
  -H 'Content-Type: application/json' \
  -d '{
    "task": "Summarize this ops brief and list workspace files",
    "context": {"text": "Queue depth is low. Three campaigns finished."}
  }' | jq
```

Job lifecycle (create → run → get):

```bash
# create pending
curl -s -X POST http://127.0.0.1:8000/jobs/create \
  -H 'Content-Type: application/json' \
  -d '{"task":"list workspace files"}' | jq

# run
curl -s -X POST http://127.0.0.1:8000/jobs/<id>/run | jq

# status / result
curl -s http://127.0.0.1:8000/jobs/<id> | jq
```

See `examples/sample_task.json` and `examples/curl_job.sh`.

### CLI (offline)

```bash
agency-ops-agent "Summarize this ops brief" \
  --text "Tickets closed: 12. Escalations: 1." \
  --json

# or
python -m agency_ops_agent "list workspace files"
```

### Built-in tools

| Tool | Description |
|------|-------------|
| `http_get` | Fetch http/https URL (timeout + size limit) |
| `summarize_text` | Deterministic summarizer (optional LLM) |
| `write_json_report` | Write JSON under the sandbox workspace |
| `list_workspace` | List files/dirs inside the sandbox |

## Ethics & security

This is a **demo automation API**, not a scraper, credential harvester, or
unbounded remote-code runner. The offline agent loop only invokes allowlisted,
typed tools.

Hard limits baked in:

- **Allowlisted schemes**: `http` / `https` only for `http_get` (rejects
  `file:`, `ftp:`, `data:`, etc.).
- **Timeouts + max bytes** on outbound HTTP.
- **Workspace sandbox**: relative paths only; `..` traversal and absolute paths
  are rejected before any file I/O.
- **Bounded steps**: agent loop stops at `max_steps` (default 8).
- **No** credential theft, Discord/session tokens, destructive system tools,
  or scraping-evasion features.

Prefer targeting systems you own or have explicit permission to access.
See [SECURITY.md](SECURITY.md) for reporting.

## Testing

```bash
ruff check src tests
ruff format --check src tests
pytest -q
```

Tests use **respx** to mock HTTP — no live network, no API keys.

CI (`.github/workflows/ci.yml`) runs ruff + pytest on Python 3.11 and 3.12.

## Project layout

```
src/agency_ops_agent/
  api.py agent.py tools.py sandbox.py audit.py
  jobs.py models.py settings.py cli.py logging_config.py
tests/
examples/
.github/workflows/ci.yml
```

## License

MIT — see [LICENSE](LICENSE).

## Suggested GitHub topics

`python` · `fastapi` · `ai-agent` · `tool-calling` · `automation` ·
`agency-ops` · `pydantic` · `portfolio` · `httpx` · `offline-first`
