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


def test_empty_relative_resolves_to_workspace_root(workspace: Path) -> None:
    """Empty relative path is treated as the workspace root (not an escape)."""
    target = resolve_in_workspace(workspace, "")
    assert target == workspace.resolve()


def test_reject_null_byte_in_path(workspace: Path) -> None:
    """NUL bytes must not reach Path APIs (can truncate on some platforms)."""
    with pytest.raises(SandboxError, match="[Nn]ull"):
        resolve_in_workspace(workspace, "reports/out\x00.json")


def test_reject_null_byte_only(workspace: Path) -> None:
    with pytest.raises(SandboxError, match="[Nn]ull"):
        resolve_in_workspace(workspace, "\x00")
