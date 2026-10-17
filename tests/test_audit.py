"""Audit log tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from agency_ops_agent.audit import AuditLog
from agency_ops_agent.jobs import JobStore
from agency_ops_agent.models import ToolCallRecord
from agency_ops_agent.settings import Settings


def test_audit_memory_and_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    audit = AuditLog(jsonl_path=path)
    audit.append(
        ToolCallRecord(tool="list_workspace", arguments={"path": "."}, result={"ok": True})
    )
    assert len(audit) == 1
    assert path.is_file()
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert "list_workspace" in lines[0]


def test_audit_clear() -> None:
    audit = AuditLog()
    audit.append(ToolCallRecord(tool="x", arguments={}))
    audit.clear()
    assert len(audit) == 0


def _rec(n: int) -> ToolCallRecord:
    return ToolCallRecord(tool="list_workspace", arguments={"n": n})


def test_audit_memory_cap_drops_oldest_first() -> None:
    audit = AuditLog(max_records=3)
    for n in range(5):
        audit.append(_rec(n))
    assert len(audit) == 3
    assert [r.arguments["n"] for r in audit.list_records()] == [2, 3, 4]
    assert audit.dropped == 2
    audit.clear()
    assert len(audit) == 0
    assert audit.dropped == 0


def test_audit_memory_cap_keeps_every_record_in_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    audit = AuditLog(jsonl_path=path, max_records=2)
    for n in range(4):
        audit.append(_rec(n))
    assert len(audit) == 2
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 4


@pytest.mark.parametrize("bad", [0, -1])
def test_audit_rejects_non_positive_cap(bad: int) -> None:
    with pytest.raises(ValueError, match="max_records"):
        AuditLog(max_records=bad)


def test_job_store_audit_uses_settings_cap(settings: Settings) -> None:
    capped = settings.model_copy(update={"audit_max_records": 7})
    store = JobStore(capped)
    assert store.audit.max_records == 7


def test_settings_audit_max_records_bounds(workspace: Path) -> None:
    with pytest.raises(ValidationError):
        Settings(workspace_dir=workspace, audit_max_records=0)
