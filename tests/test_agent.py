"""Agent loop tests (offline / mocked)."""

from __future__ import annotations

import httpx
import respx

from agency_ops_agent.agent import Agent
from agency_ops_agent.audit import AuditLog
from agency_ops_agent.settings import Settings
from agency_ops_agent.tools import ToolRegistry


def test_agent_summarize_only(settings: Settings, tools: ToolRegistry, audit: AuditLog) -> None:
    agent = Agent(settings, tools=tools, audit=audit)
    result = agent.run(
        task="Please summarize this briefing for the client",
        context={"text": "We closed three deals. Pipeline is healthy. Next quarter looks strong."},
    )
    assert result.steps_used >= 1
    assert any(c.tool == "summarize_text" and not c.error for c in result.tool_calls)
    assert "Summary:" in result.answer or "successful" in result.answer.lower()
    assert result.metadata["mode"] == "deterministic"
    assert len(audit) >= 1


@respx.mock
def test_agent_fetch_summarize_report(
    settings: Settings, tools: ToolRegistry, audit: AuditLog
) -> None:
    respx.get("https://example.com/ops").mock(
        return_value=httpx.Response(
            200,
            text="Agency ops status is green. All bots online. Queue depth is low.",
        )
    )
    agent = Agent(settings, tools=tools, audit=audit)
    result = agent.run(
        task="Fetch https://example.com/ops and summarize then write a JSON report",
        context={"report_filename": "reports/ops.json"},
    )
    tools_used = [c.tool for c in result.tool_calls if not c.error]
    assert "http_get" in tools_used
    assert "summarize_text" in tools_used
    assert "write_json_report" in tools_used
    assert result.steps_used <= settings.max_steps


def test_agent_respects_max_steps(settings: Settings, tools: ToolRegistry) -> None:
    agent = Agent(settings, tools=tools)
    result = agent.run(
        task="list workspace files and summarize hello world text forever",
        context={"text": "Hello. World. Again."},
        max_steps=1,
    )
    assert result.steps_used == 1


def test_agent_unknown_url_scheme_records_error(
    settings: Settings, tools: ToolRegistry, audit: AuditLog
) -> None:
    agent = Agent(settings, tools=tools, audit=audit)
    result = agent.run(
        task="fetch the url and summarize",
        context={"url": "ftp://evil.example/file"},
    )
    http_calls = [c for c in result.tool_calls if c.tool == "http_get"]
    assert http_calls
    assert http_calls[0].error is not None
