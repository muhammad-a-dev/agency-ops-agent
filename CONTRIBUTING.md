# Contributing

Thanks for your interest in improving **agency-ops-agent**.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Checks before opening a PR

```bash
ruff check src tests
ruff format --check src tests
pytest -q
```

## Guidelines

- Keep the **default offline path** working without API keys.
- Prefer typed Pydantic models for new tool arguments.
- Never add tools that can escape the workspace sandbox, scrape with evasion,
  or handle credentials/tokens.
- Add or update tests for behavior changes.
- Keep commits focused and messages imperative.

## Security reports

Please follow [SECURITY.md](SECURITY.md) for vulnerability disclosures.
