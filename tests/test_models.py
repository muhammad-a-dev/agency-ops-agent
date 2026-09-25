"""TaskRequest / context payload bound tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agency_ops_agent.models import (
    MAX_CONTEXT_JSON_BYTES,
    MAX_CONTEXT_KEYS,
    TaskRequest,
)


def test_task_request_accepts_small_context() -> None:
    req = TaskRequest(
        task="summarize ops",
        context={"text": "Tickets closed: 3.", "max_sentences": 2},
    )
    assert req.context["text"].startswith("Tickets")
    assert req.max_steps is None


def test_task_request_rejects_too_many_context_keys() -> None:
    huge = {f"k{i}": i for i in range(MAX_CONTEXT_KEYS + 1)}
    with pytest.raises(ValidationError, match="too many keys"):
        TaskRequest(task="do something useful", context=huge)


def test_task_request_rejects_oversized_context_json() -> None:
    # One key whose value alone exceeds the serialized byte budget.
    blob = "x" * (MAX_CONTEXT_JSON_BYTES + 1)
    with pytest.raises(ValidationError, match="bytes"):
        TaskRequest(task="do something useful", context={"text": blob})


def test_task_request_allows_context_at_key_limit() -> None:
    ctx = {f"k{i}": i for i in range(MAX_CONTEXT_KEYS)}
    req = TaskRequest(task="list workspace files", context=ctx)
    assert len(req.context) == MAX_CONTEXT_KEYS


def test_task_request_empty_context_ok() -> None:
    req = TaskRequest(task="summarize this brief note")
    assert req.context == {}
