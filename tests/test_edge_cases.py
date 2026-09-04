"""Meaningful edge-case coverage for sandbox, HTTP schemes, API, and audit."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from agency_ops_agent.api import create_app
from agency_ops_agent.audit import AuditLog
from agency_ops_agent.models import ToolCallRecord
from agency_ops_agent.sandbox import SandboxError, resolve_in_workspace
from agency_ops_agent.settings import Settings, get_settings
from agency_ops_agent.tools import HttpGetArgs

# ---------------------------------------------------------------------------
# Sandbox path traversal / absolute-path edges
# ---------------------------------------------------------------------------


def test_sandbox_rejects_dotdot_alone(workspace: Path) -> None:
    with pytest.raises(SandboxError):
        resolve_in_workspace(workspace, "..")


def test_sandbox_rejects_encoded_style_traversal(workspace: Path) -> None:
    # Nested escapes that resolve outside the workspace root.
    with pytest.raises(SandboxError):
        resolve_in_workspace(workspace, "a/b/../../../etc/passwd")


def test_sandbox_allows_dot_current(workspace: Path) -> None:
    target = resolve_in_workspace(workspace, ".")
    assert target == workspace.resolve()


# ---------------------------------------------------------------------------
# http_get scheme rejection edges
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_url",
    [
        "ftp://files.example.com/report.txt",
        "data:text/plain,hello",
        "javascript:alert(1)",
        "file:///etc/hosts",
    ],
)
def test_http_get_rejects_disallowed_schemes(bad_url: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        HttpGetArgs(url=bad_url)
    assert "scheme" in str(exc_info.value).lower() or "http" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Job-not-found API edges
# ---------------------------------------------------------------------------


@pytest.fixture
def api_client(workspace: Path) -> TestClient:
    get_settings.cache_clear()
    settings = Settings(
        workspace_dir=workspace,
        max_steps=4,
        agent_llm_enabled=False,
        openai_api_key=None,
        log_level="WARNING",
    )
    app = create_app(settings)
    with TestClient(app) as tc:
        yield tc


def test_get_job_not_found_includes_id_in_detail(api_client: TestClient) -> None:
    missing = "00000000-0000-0000-0000-000000000099"
    resp = api_client.get(f"/jobs/{missing}")
    assert resp.status_code == 404
    detail = resp.json()["detail"]
    assert missing in detail
    assert "not found" in detail.lower()


def test_run_job_not_found_includes_id_in_detail(api_client: TestClient) -> None:
    missing = "deadbeef-not-a-real-job"
    resp = api_client.post(f"/jobs/{missing}/run")
    assert resp.status_code == 404
    detail = resp.json()["detail"]
    assert missing in detail


# ---------------------------------------------------------------------------
# Audit log append edges
# ---------------------------------------------------------------------------


def test_audit_append_multiple_jsonl_lines(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "audit.jsonl"
    audit = AuditLog(jsonl_path=path)
    audit.append(ToolCallRecord(tool="http_get", arguments={"url": "https://a.test"}))
    audit.append(
        ToolCallRecord(
            tool="summarize_text",
            arguments={"text": "x"},
            error="boom",
            duration_ms=1.5,
        )
    )
    assert len(audit) == 2
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    second = json.loads(lines[1])
    assert second["tool"] == "summarize_text"
    assert second["error"] == "boom"
    assert second["duration_ms"] == 1.5


def test_audit_append_memory_only_no_file() -> None:
    audit = AuditLog(jsonl_path=None)
    audit.append(ToolCallRecord(tool="list_workspace", arguments={"path": "."}, result={"n": 0}))
    assert len(audit) == 1
    dicts = audit.as_dicts()
    assert dicts[0]["tool"] == "list_workspace"
    assert dicts[0]["result"] == {"n": 0}
