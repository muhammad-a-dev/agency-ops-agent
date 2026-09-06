# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
