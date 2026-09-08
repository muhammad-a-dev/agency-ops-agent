# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Design intent

This project is a **portfolio / demo** tool-using agent API. It is intentionally
constrained:

- HTTP tools allow **http/https only**, with timeouts and max response bytes.
- File tools are confined to a **workspace sandbox** (path traversal rejected).
- Default agent mode requires **no LLM API keys**.
- Optional LLM mode is behind `AGENCY_OPS_AGENT_LLM_ENABLED` and still fails closed.

## Secrets & local configuration

- Copy `.env.example` to `.env` for local runs. **Never commit** `.env`, API keys,
  tokens, or private keys (see `.gitignore`).
- Leave `AGENCY_OPS_AGENT_LLM_ENABLED=false` unless you intentionally need the
  optional OpenAI-compatible path.
- If a key is ever pasted into chat, logs, or a public issue, **rotate it** in the
  provider console and treat the old value as compromised.
- Prefer environment variables or a local secrets manager over hard-coding
  credentials in source or examples.

## Reporting a vulnerability

Please open a **private security advisory** on GitHub, or email the maintainer
via the profile contact on [github.com/muhammad-a-dev](https://github.com/muhammad-a-dev).

Do not open a public issue for undisclosed vulnerabilities.

Include:

1. Affected version / commit
2. Reproduction steps
3. Impact assessment

## Out of scope

- Using this demo against systems you do not own or lack permission to test
- Requests to add credential theft, Discord tokens, destructive system tools,
  or scraping-evasion capabilities — these will be refused
