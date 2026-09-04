"""Pydantic models for jobs, tool calls, and API payloads."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class TaskRequest(BaseModel):
    """Inbound task description for the agent."""

    task: str = Field(..., min_length=1, max_length=8000)
    context: dict[str, Any] = Field(default_factory=dict)
    max_steps: int | None = Field(default=None, ge=1, le=50)


class ToolCallRecord(BaseModel):
    """Single audited tool invocation."""

    tool: str
    arguments: dict[str, Any]
    result: Any = None
    error: str | None = None
    duration_ms: float = 0.0
    timestamp: datetime = Field(default_factory=utc_now)


class AgentResult(BaseModel):
    """Structured final answer from the agent loop."""

    answer: str
    steps_used: int
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Job(BaseModel):
    """In-memory job record."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    status: JobStatus = JobStatus.PENDING
    request: TaskRequest
    result: AgentResult | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None

    def touch(self) -> None:
        self.updated_at = utc_now()


class JobCreateResponse(BaseModel):
    id: str
    status: JobStatus


class JobResponse(BaseModel):
    id: str
    status: JobStatus
    request: TaskRequest
    result: AgentResult | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @classmethod
    def from_job(cls, job: Job) -> JobResponse:
        return cls(
            id=job.id,
            status=job.status,
            request=job.request,
            result=job.result,
            error=job.error,
            created_at=job.created_at,
            updated_at=job.updated_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
        )


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    llm_enabled: bool
