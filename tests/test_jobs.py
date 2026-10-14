"""JobStore capacity: bounded memory with oldest-finished eviction."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from agency_ops_agent.api import create_app
from agency_ops_agent.jobs import JobStore, JobStoreFullError
from agency_ops_agent.models import JobStatus, TaskRequest
from agency_ops_agent.settings import Settings

FINISHED = {JobStatus.SUCCEEDED, JobStatus.FAILED}


def _request() -> TaskRequest:
    return TaskRequest(task="summarize hello", context={"text": "Hi."})


def _store(settings: Settings, max_jobs: int) -> JobStore:
    return JobStore(settings.model_copy(update={"max_jobs": max_jobs}))


def test_evicts_oldest_finished_job_at_capacity(settings: Settings) -> None:
    store = _store(settings, max_jobs=2)
    first = store.create_and_run(_request())
    second = store.create_and_run(_request())
    assert first.status in FINISHED
    assert second.status in FINISHED

    third = store.create(_request())

    assert store.get(first.id) is None
    assert store.get(second.id) is not None
    assert store.get(third.id) is not None
    assert len(store.list_jobs()) == 2


def test_pending_jobs_are_never_evicted(settings: Settings) -> None:
    store = _store(settings, max_jobs=2)
    pending = store.create(_request())
    done = store.create_and_run(_request())
    assert done.status in FINISHED

    newest = store.create(_request())

    assert store.get(pending.id) is not None
    assert store.get(done.id) is None
    assert store.get(newest.id) is not None


def test_raises_when_full_of_unfinished_jobs(settings: Settings) -> None:
    store = _store(settings, max_jobs=2)
    first = store.create(_request())
    second = store.create(_request())

    with pytest.raises(JobStoreFullError):
        store.create(_request())

    assert {job.id for job in store.list_jobs()} == {first.id, second.id}


def test_max_jobs_must_be_positive(workspace: Path) -> None:
    with pytest.raises(ValidationError):
        Settings(workspace_dir=workspace, max_jobs=0)


def test_api_returns_503_when_job_store_is_full(workspace: Path) -> None:
    settings = Settings(
        workspace_dir=workspace,
        max_jobs=1,
        agent_llm_enabled=False,
        openai_api_key=None,
        log_level="WARNING",
    )
    with TestClient(create_app(settings)) as client:
        first = client.post("/jobs/create", json={"task": "list workspace files"})
        assert first.status_code == 201

        blocked = client.post("/jobs/create", json={"task": "list workspace files"})
        assert blocked.status_code == 503
        assert "full" in blocked.json()["detail"]

        payload = {"task": "summarize hello", "context": {"text": "Hi."}}
        assert client.post("/jobs", json=payload).status_code == 503
