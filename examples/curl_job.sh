#!/usr/bin/env bash
# Hit a running API server (uvicorn agency_ops_agent.api:app --reload)
set -euo pipefail
BASE="${BASE_URL:-http://127.0.0.1:8000}"

curl -sS "$BASE/health" | python -m json.tool

curl -sS -X POST "$BASE/jobs" \
  -H "Content-Type: application/json" \
  -d @examples/sample_task.json | python -m json.tool
