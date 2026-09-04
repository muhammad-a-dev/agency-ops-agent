#!/usr/bin/env bash
# Offline-safe demo: summarize text + list workspace (no network required).
set -euo pipefail
export AGENCY_OPS_AGENT_LLM_ENABLED=false
export AGENCY_OPS_WORKSPACE_DIR="${AGENCY_OPS_WORKSPACE_DIR:-./workspace}"

agency-ops-agent \
  "Summarize this ops brief and list workspace files" \
  --text "Queue depth is low. Three campaigns finished. No escalations today." \
  --json
