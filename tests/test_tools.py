"""Tool validation and behavior tests (network mocked)."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx
from pydantic import ValidationError

from agency_ops_agent.sandbox import SandboxError
from agency_ops_agent.tools import (
    HttpGetArgs,
    SummarizeTextArgs,
    ToolRegistry,
    WriteJsonReportArgs,
    deterministic_summarize,
)


def test_http_get_args_rejects_file_scheme() -> None:
    with pytest.raises(ValidationError):
        HttpGetArgs(url="file:///etc/passwd")


def test_http_get_args_rejects_missing_host() -> None:
    with pytest.raises(ValidationError):
        HttpGetArgs(url="https://")


def test_write_json_report_args_rejects_dir_trailing() -> None:
    with pytest.raises(ValidationError):
        WriteJsonReportArgs(filename="reports/", data={"a": 1})


def test_summarize_text_args_bounds() -> None:
    with pytest.raises(ValidationError):
        SummarizeTextArgs(text="hi", max_sentences=0)


def test_deterministic_summarize_basic() -> None:
    text = "First sentence. Second sentence. Third sentence. Fourth."
    out = deterministic_summarize(text, max_sentences=2)
    assert "First sentence." in out
    assert "Second sentence." in out
    assert "…" in out


def test_deterministic_summarize_emptyish() -> None:
    assert deterministic_summarize("   ") == ""


@respx.mock
def test_http_get_success(tools: ToolRegistry) -> None:
    route = respx.get("https://example.com/page").mock(
        return_value=httpx.Response(
            200, text="Hello agency ops", headers={"content-type": "text/plain"}
        )
    )
    result = tools.invoke("http_get", {"url": "https://example.com/page"})
    assert route.called
    assert result["status_code"] == 200
    assert "Hello agency ops" in result["body"]
    assert result["truncated"] is False


@respx.mock
def test_http_get_truncates(tools: ToolRegistry, settings) -> None:
    settings.http_max_bytes = 20
    big = "A" * 500
    respx.get("https://example.com/big").mock(return_value=httpx.Response(200, text=big))
    reg = ToolRegistry(settings)
    result = reg.invoke("http_get", {"url": "https://example.com/big"})
    assert result["truncated"] is True
    assert result["bytes_read"] <= 20


def test_http_get_unknown_tool(tools: ToolRegistry) -> None:
    with pytest.raises(KeyError):
        tools.invoke("not_a_tool", {})


def test_write_and_list_workspace(tools: ToolRegistry, workspace: Path) -> None:
    written = tools.invoke(
        "write_json_report",
        {"filename": "reports/demo.json", "data": {"ok": True, "n": 1}},
    )
    assert written["path"] == "reports/demo.json"
    assert (workspace / "reports" / "demo.json").is_file()

    listing = tools.invoke("list_workspace", {"path": "reports"})
    assert listing["exists"] is True
    names = {e["name"] for e in listing["entries"]}
    assert "demo.json" in names


def test_write_rejects_traversal(tools: ToolRegistry) -> None:
    with pytest.raises(SandboxError):
        tools.invoke(
            "write_json_report",
            {"filename": "../escape.json", "data": {"x": 1}},
        )


def test_list_rejects_traversal(tools: ToolRegistry) -> None:
    with pytest.raises(SandboxError):
        tools.invoke("list_workspace", {"path": "../"})


def test_summarize_default_deterministic(tools: ToolRegistry) -> None:
    result = tools.invoke(
        "summarize_text",
        {"text": "Alpha. Bravo. Charlie.", "max_sentences": 2},
    )
    assert result["mode"] == "deterministic"
    assert "Alpha." in result["summary"]


def test_tool_schemas_present(tools: ToolRegistry) -> None:
    names = {s["name"] for s in tools.schemas()}
    assert names == {"http_get", "write_json_report", "summarize_text", "list_workspace"}
