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
