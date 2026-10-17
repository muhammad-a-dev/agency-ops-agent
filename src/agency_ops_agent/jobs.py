"""In-memory job store: create → run → get status/result."""

from __future__ import annotations

import logging
from threading import Lock

from agency_ops_agent.agent import Agent
from agency_ops_agent.audit import AuditLog
from agency_ops_agent.models import Job, JobStatus, TaskRequest, utc_now
from agency_ops_agent.settings import Settings
from agency_ops_agent.tools import ToolRegistry

logger = logging.getLogger(__name__)

_FINISHED = (JobStatus.SUCCEEDED, JobStatus.FAILED)


class JobStoreFullError(RuntimeError):
    """Raised when the store is at capacity and no finished job can be evicted."""


class JobStore:
    """Thread-safe in-memory job registry, bounded by ``settings.max_jobs``."""

    def __init__(
        self,
        settings: Settings,
        tools: ToolRegistry | None = None,
        audit: AuditLog | None = None,
    ) -> None:
        self.settings = settings
        self.tools = tools if tools is not None else ToolRegistry(settings)
        self.audit = (
            audit
            if audit is not None
            else AuditLog(settings.audit_log_path, max_records=settings.audit_max_records)
        )
        self._jobs: dict[str, Job] = {}
        self._lock = Lock()

    def create(self, request: TaskRequest) -> Job:
        job = Job(request=request)
        with self._lock:
            self._make_room_locked()
            self._jobs[job.id] = job
        logger.info("job.created id=%s", job.id)
        return job

    def _make_room_locked(self) -> None:
        """Evict the oldest finished jobs until one more job fits.

        Caller must hold ``self._lock``. Dict order is insertion order, so the
        scan visits the oldest jobs first. Pending and running jobs are kept.
        """
        limit = self.settings.max_jobs
        if len(self._jobs) < limit:
            return
        finished = [job_id for job_id, job in self._jobs.items() if job.status in _FINISHED]
        for job_id in finished:
            del self._jobs[job_id]
            logger.info("job.evicted id=%s", job_id)
            if len(self._jobs) < limit:
                return
        raise JobStoreFullError(f"job store is full: {limit} jobs are pending or running")

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())

    def run(self, job_id: str) -> Job:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(f"Job not found: {job_id}")
            if job.status == JobStatus.RUNNING:
                return job
            job.status = JobStatus.RUNNING
            job.started_at = utc_now()
            job.touch()

        logger.info("job.running id=%s", job_id)
        agent = Agent(self.settings, tools=self.tools, audit=self.audit)
        try:
            result = agent.run(
                task=job.request.task,
                context=job.request.context,
                max_steps=job.request.max_steps,
            )
            with self._lock:
                job.status = JobStatus.SUCCEEDED
                job.result = result
                job.finished_at = utc_now()
                job.touch()
        except Exception as exc:  # noqa: BLE001
            logger.exception("job.failed id=%s", job_id)
            with self._lock:
                job.status = JobStatus.FAILED
                job.error = f"{type(exc).__name__}: {exc}"
                job.finished_at = utc_now()
                job.touch()
        return job

    def create_and_run(self, request: TaskRequest) -> Job:
        job = self.create(request)
        return self.run(job.id)
