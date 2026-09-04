"""Audit log tests."""

from __future__ import annotations

from pathlib import Path

from agency_ops_agent.audit import AuditLog
from agency_ops_agent.models import ToolCallRecord


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
