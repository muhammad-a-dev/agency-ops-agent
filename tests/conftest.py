"""Shared fixtures for offline-safe tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from agency_ops_agent.audit import AuditLog
from agency_ops_agent.settings import Settings, get_settings
from agency_ops_agent.tools import ToolRegistry


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ws


@pytest.fixture
def settings(workspace: Path) -> Settings:
    get_settings.cache_clear()
    cfg = Settings(
        workspace_dir=workspace,
        max_steps=6,
        http_timeout_seconds=5.0,
        http_max_bytes=65_536,
        audit_log_path=None,
        agent_llm_enabled=False,
        openai_api_key=None,
        log_level="WARNING",
    )
    return cfg


@pytest.fixture
def tools(settings: Settings) -> ToolRegistry:
    return ToolRegistry(settings)


@pytest.fixture
def audit(tmp_path: Path) -> AuditLog:
    return AuditLog(jsonl_path=tmp_path / "audit.jsonl")
