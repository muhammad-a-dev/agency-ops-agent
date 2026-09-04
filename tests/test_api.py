"""FastAPI TestClient integration tests."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from agency_ops_agent.api import create_app
from agency_ops_agent.settings import Settings, get_settings


@pytest.fixture
def client(workspace: Path) -> TestClient:
    get_settings.cache_clear()
    settings = Settings(
        workspace_dir=workspace,
        max_steps=6,
        agent_llm_enabled=False,
        openai_api_key=None,
        log_level="WARNING",
    )
    app = create_app(settings)
    with TestClient(app) as tc:
        yield tc


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["llm_enabled"] is False
    assert "version" in data


def test_list_tools(client: TestClient) -> None:
    resp = client.get("/tools")
    assert resp.status_code == 200
    names = {t["name"] for t in resp.json()["tools"]}
    assert "http_get" in names


def test_create_and_run_job_summarize(client: TestClient) -> None:
    resp = client.post(
        "/jobs",
        json={
            "task": "Summarize the weekly ops brief",
            "context": {"text": "Tickets closed: 12. Escalations: 1. CSAT: 94%."},
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "succeeded"
    assert body["result"]["steps_used"] >= 1
    assert body["result"]["answer"]


def test_create_then_run_then_get(client: TestClient) -> None:
    created = client.post(
        "/jobs/create",
        json={"task": "list workspace files please"},
    )
    assert created.status_code == 201
    job_id = created.json()["id"]
    assert created.json()["status"] == "pending"

    ran = client.post(f"/jobs/{job_id}/run")
    assert ran.status_code == 200
    assert ran.json()["status"] == "succeeded"

    got = client.get(f"/jobs/{job_id}")
    assert got.status_code == 200
    assert got.json()["id"] == job_id


def test_get_missing_job(client: TestClient) -> None:
    resp = client.get("/jobs/does-not-exist")
    assert resp.status_code == 404


def test_run_missing_job(client: TestClient) -> None:
    resp = client.post("/jobs/missing/run")
    assert resp.status_code == 404


@respx.mock
def test_job_with_http_get(client: TestClient) -> None:
    respx.get("https://example.com/a").mock(
        return_value=httpx.Response(200, text="Alpha content. Beta content.")
    )
    resp = client.post(
        "/jobs",
        json={
            "task": "Fetch https://example.com/a and summarize into a report",
            "context": {"report_filename": "reports/api.json"},
        },
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "succeeded"
    tools = [c["tool"] for c in resp.json()["result"]["tool_calls"]]
    assert "http_get" in tools


def test_list_jobs(client: TestClient) -> None:
    client.post("/jobs", json={"task": "summarize hello", "context": {"text": "Hi."}})
    resp = client.get("/jobs")
    assert resp.status_code == 200
    assert resp.json()["count"] >= 1


def test_validation_error_empty_task(client: TestClient) -> None:
    resp = client.post("/jobs", json={"task": ""})
    assert resp.status_code == 422
