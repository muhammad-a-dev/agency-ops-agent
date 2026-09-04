# Contributing

Thanks for your interest in improving **agency-ops-agent**.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

## Checks before opening a PR

```bash
ruff check src tests
ruff format --check src tests
pytest -q
```

CI runs the same checks on Python 3.11 and 3.12 — keep the **default offline
path** green without API keys.

## Optional Docker smoke

```bash
docker build -t agency-ops-agent .
docker run --rm -p 8000:8000 agency-ops-agent
curl -s http://127.0.0.1:8000/health
```

## Guidelines

- Keep the **default offline path** working without API keys.
- Prefer typed Pydantic models for new tool arguments.
- Never add tools that can escape the workspace sandbox, scrape with evasion,
  or handle credentials/tokens.
- Add or update tests for behavior changes.
- Keep commits focused and messages imperative.
- Use the [bug report](.github/ISSUE_TEMPLATE/bug_report.md) template when
  filing issues.

## Security reports

Please follow [SECURITY.md](SECURITY.md) for vulnerability disclosures.
