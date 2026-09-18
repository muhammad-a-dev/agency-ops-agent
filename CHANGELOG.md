# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security

- Reject null bytes (`\\x00`) in sandbox relative paths so truncated-path
  tricks cannot bypass workspace confinement.

### Changed

- Clarified secrets handling in `SECURITY.md` and `.env.example` (never commit
  `.env` / keys; rotate exposed credentials).

### Tests

- Cover sandbox and tool rejection of null bytes in relative paths.
- Document empty relative path resolving to the workspace root in sandbox tests.
- Cover settings env coercion: empty `audit_log_path` → `None`, string
  `workspace_dir` → `Path`, `ensure_workspace` creates missing dirs, `max_steps`
  bounds, and `get_settings` cache clear.
- Cover tool arg bounds (`http_get` max_bytes, write indent, empty summarize
  text), `list_workspace` missing/file paths, registry `names`/`get`, and
  deterministic summarize without sentence terminators.

## [0.1.0] — 2026-09-06

### Added

- FastAPI job API: create, run, and fetch agent jobs with a structured result.
- Bounded plan/act tool loop with a hard `max_steps` stop (default 8).
- Typed tools: `http_get`, `summarize_text`, `write_json_report`, `list_workspace`.
- Workspace sandbox that rejects path traversal and absolute paths.
- Offline-first heuristic summarizer (no API keys required for demos or CI).
- Optional OpenAI-compatible summarize path gated behind `AGENCY_OPS_AGENT_LLM_ENABLED`.
- In-memory audit trail with optional JSONL persistence.
- CLI runner for single offline tasks.
- Docker image, GitHub Actions CI (ruff + pytest on Python 3.11/3.12), and docs.

### Security

- HTTP tool limited to `http`/`https`, with timeouts and max response bytes.
- Agent loop only invokes allowlisted, Pydantic-validated tools.
