"""Application settings via pydantic-settings / environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Prefix: ``AGENCY_OPS_``."""

    model_config = SettingsConfigDict(
        env_prefix="AGENCY_OPS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    workspace_dir: Path = Field(
        default=Path("./workspace"),
        description="Sandbox directory for tool file I/O.",
    )
    max_steps: int = Field(default=8, ge=1, le=50)
    http_timeout_seconds: float = Field(default=10.0, gt=0, le=120)
    http_max_bytes: int = Field(default=1_048_576, ge=1024, le=10_485_760)
    audit_log_path: Path | None = Field(
        default=None,
        description="Optional JSONL audit log path. None = in-memory only.",
    )
    agent_llm_enabled: bool = Field(
        default=False,
        description="If true and API key present, use optional LLM path.",
    )
    openai_api_key: str | None = Field(default=None)
    openai_model: str = Field(default="gpt-4o-mini")
    openai_base_url: str = Field(default="https://api.openai.com/v1")
    log_level: str = Field(default="INFO")

    @field_validator("workspace_dir", mode="before")
    @classmethod
    def _coerce_workspace(cls, value: object) -> Path:
        return Path(str(value)) if value is not None else Path("./workspace")

    @field_validator("audit_log_path", mode="before")
    @classmethod
    def _coerce_audit(cls, value: object) -> Path | None:
        if value is None or value == "":
            return None
        return Path(str(value))

    def ensure_workspace(self) -> Path:
        """Create workspace directory if missing; return resolved path."""
        path = self.workspace_dir.expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton (clear via ``get_settings.cache_clear()``)."""
    return Settings()
