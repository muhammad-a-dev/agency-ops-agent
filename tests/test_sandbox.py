"""Path sandbox safety tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from agency_ops_agent.sandbox import SandboxError, resolve_in_workspace


def test_resolve_relative_ok(workspace: Path) -> None:
    target = resolve_in_workspace(workspace, "reports/out.json")
    assert target.parent == (workspace / "reports").resolve() or str(target).endswith(
        "reports/out.json"
    )
    assert str(workspace.resolve()) in str(target)


def test_reject_parent_traversal(workspace: Path) -> None:
    with pytest.raises(SandboxError):
        resolve_in_workspace(workspace, "../secrets.txt")


def test_reject_absolute_path(workspace: Path) -> None:
    with pytest.raises(SandboxError):
        resolve_in_workspace(workspace, "/etc/passwd")


def test_nested_dotdot_rejected(workspace: Path) -> None:
    with pytest.raises(SandboxError):
        resolve_in_workspace(workspace, "ok/../../outside.txt")
