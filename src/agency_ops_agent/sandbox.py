"""Path sandbox helpers — prevent traversal outside the workspace."""

from __future__ import annotations

from pathlib import Path


class SandboxError(ValueError):
    """Raised when a path escapes the configured workspace."""


def resolve_in_workspace(workspace: Path, relative: str) -> Path:
    """Resolve ``relative`` under ``workspace``; reject traversal escapes.

    Parameters
    ----------
    workspace:
        Absolute or relative workspace root (will be resolved).
    relative:
        User-supplied relative path (may contain ``..`` — will be rejected
        if the final path is outside the workspace).
    """
    root = workspace.expanduser().resolve()
    # Disallow absolute user paths — always treat as relative to root.
    candidate = Path(relative)
    if candidate.is_absolute():
        raise SandboxError(f"Absolute paths are not allowed: {relative!r}")

    target = (root / candidate).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise SandboxError(f"Path {relative!r} escapes workspace {root}") from exc
    return target
