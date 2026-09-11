"""Settings env coercion and workspace bootstrap tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from agency_ops_agent.settings import Settings, get_settings


def test_empty_audit_log_path_coerces_to_none() -> None:
    cfg = Settings(audit_log_path="")
    assert cfg.audit_log_path is None


def test_workspace_dir_string_coerces_to_path(tmp_path: Path) -> None:
    cfg = Settings(workspace_dir=str(tmp_path / "ws"))
    assert isinstance(cfg.workspace_dir, Path)
    assert cfg.workspace_dir == Path(str(tmp_path / "ws"))


def test_ensure_workspace_creates_missing_dir(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "workspace"
    assert not target.exists()
    cfg = Settings(workspace_dir=target)
    resolved = cfg.ensure_workspace()
    assert resolved.is_dir()
    assert resolved == target.resolve()


def test_agent_llm_enabled_false_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENCY_OPS_AGENT_LLM_ENABLED", raising=False)
    cfg = Settings(_env_file=None)
    assert cfg.agent_llm_enabled is False


def test_max_steps_rejects_out_of_bounds() -> None:
    with pytest.raises(ValidationError):
        Settings(max_steps=0)
    with pytest.raises(ValidationError):
        Settings(max_steps=51)


def test_get_settings_cache_clear(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("AGENCY_OPS_MAX_STEPS", "3")
    monkeypatch.setenv("AGENCY_OPS_AGENT_LLM_ENABLED", "false")
    first = get_settings()
    assert first.max_steps == 3
    monkeypatch.setenv("AGENCY_OPS_MAX_STEPS", "9")
    # Cached until clear
    assert get_settings().max_steps == 3
    get_settings.cache_clear()
    assert get_settings().max_steps == 9
    get_settings.cache_clear()
