"""FastAPI application: health, create/run job, get job."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status

from agency_ops_agent import __version__
from agency_ops_agent.jobs import JobStore
from agency_ops_agent.logging_config import configure_logging
from agency_ops_agent.models import (
    HealthResponse,
    JobCreateResponse,
    JobResponse,
    TaskRequest,
)
from agency_ops_agent.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory (handy for tests)."""
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    store = JobStore(settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        settings.ensure_workspace()
        yield

    app = FastAPI(
        title="Agency Ops Agent",
        description=(
            "Tool-using agent API for agency operations automation demos. "
            "Default mode is offline-safe (no LLM API keys required)."
        ),
        version=__version__,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.store = store

    def _store() -> JobStore:
        return app.state.store

    def _settings() -> Settings:
        return app.state.settings

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    def health(cfg: Settings = Depends(_settings)) -> HealthResponse:
        return HealthResponse(
            status="ok",
            version=__version__,
            llm_enabled=bool(cfg.agent_llm_enabled and cfg.openai_api_key),
        )

    @app.get("/tools", tags=["system"])
    def list_tools(job_store: JobStore = Depends(_store)) -> dict:
        return {"tools": job_store.tools.schemas()}

    @app.post(
        "/jobs",
        response_model=JobResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["jobs"],
        summary="Create and run a job synchronously",
    )
    def create_and_run_job(
        body: TaskRequest,
        job_store: JobStore = Depends(_store),
    ) -> JobResponse:
        job = job_store.create_and_run(body)
        return JobResponse.from_job(job)

    @app.post(
        "/jobs/create",
        response_model=JobCreateResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["jobs"],
        summary="Create a pending job without running it",
    )
    def create_job(
        body: TaskRequest,
        job_store: JobStore = Depends(_store),
    ) -> JobCreateResponse:
        job = job_store.create(body)
        return JobCreateResponse(id=job.id, status=job.status)

    @app.post(
        "/jobs/{job_id}/run",
        response_model=JobResponse,
        tags=["jobs"],
        summary="Run a previously created job",
    )
    def run_job(
        job_id: str,
        job_store: JobStore = Depends(_store),
    ) -> JobResponse:
        try:
            job = job_store.run(job_id)
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job not found: {job_id}",
            ) from None
        return JobResponse.from_job(job)

    @app.get(
        "/jobs/{job_id}",
        response_model=JobResponse,
        tags=["jobs"],
        summary="Get job status and result",
    )
    def get_job(
        job_id: str,
        job_store: JobStore = Depends(_store),
    ) -> JobResponse:
        job = job_store.get(job_id)
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job not found: {job_id}",
            )
        return JobResponse.from_job(job)

    @app.get("/jobs", tags=["jobs"], summary="List jobs")
    def list_jobs(job_store: JobStore = Depends(_store)) -> dict:
        jobs = [JobResponse.from_job(j) for j in job_store.list_jobs()]
        return {"jobs": jobs, "count": len(jobs)}

    return app


app = create_app()
