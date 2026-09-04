"""CLI smoke test."""

from __future__ import annotations

from agency_ops_agent.cli import main


def test_cli_summarize(capsys, monkeypatch, workspace, settings) -> None:
    monkeypatch.setenv("AGENCY_OPS_WORKSPACE_DIR", str(workspace))
    monkeypatch.setenv("AGENCY_OPS_AGENT_LLM_ENABLED", "false")
    from agency_ops_agent.settings import get_settings

    get_settings.cache_clear()
    code = main(["Summarize this", "--text", "One. Two. Three.", "--json"])
    assert code == 0
    out = capsys.readouterr().out
    assert "answer" in out or "summary" in out.lower() or "successful" in out.lower()
    assert "steps_used" in out or '"answer"' in out
