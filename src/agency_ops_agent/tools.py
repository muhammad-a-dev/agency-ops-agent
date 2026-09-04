"""Real Python callables with typed Pydantic schemas for the agent."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field, field_validator

from agency_ops_agent.sandbox import SandboxError, resolve_in_workspace
from agency_ops_agent.settings import Settings

logger = logging.getLogger(__name__)

ALLOWED_SCHEMES = frozenset({"http", "https"})


# ---------------------------------------------------------------------------
# Tool argument schemas
# ---------------------------------------------------------------------------


class HttpGetArgs(BaseModel):
    """Fetch a URL with timeouts and size limits."""

    url: str = Field(..., description="HTTP(S) URL to fetch.")
    max_bytes: int | None = Field(
        default=None,
        ge=1024,
        le=10_485_760,
        description="Override max response body bytes.",
    )

    @field_validator("url")
    @classmethod
    def _scheme_ok(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme.lower() not in ALLOWED_SCHEMES:
            raise ValueError(f"URL scheme must be http or https, got {parsed.scheme!r}")
        if not parsed.netloc:
            raise ValueError("URL must include a host")
        return value


class WriteJsonReportArgs(BaseModel):
    """Write a structured JSON report into the sandbox workspace."""

    filename: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Relative filename under the workspace (e.g. reports/out.json).",
    )
    data: dict[str, Any] = Field(..., description="JSON-serializable report payload.")
    indent: int = Field(default=2, ge=0, le=8)

    @field_validator("filename")
    @classmethod
    def _safe_name(cls, value: str) -> str:
        if value.endswith("/") or value.endswith("\\"):
            raise ValueError("filename must be a file path, not a directory")
        return value


class SummarizeTextArgs(BaseModel):
    """Summarize text with a deterministic heuristic (or optional LLM)."""

    text: str = Field(..., min_length=1, max_length=100_000)
    max_sentences: int = Field(default=3, ge=1, le=10)


class ListWorkspaceArgs(BaseModel):
    """List files under a relative path inside the workspace."""

    path: str = Field(
        default=".",
        description="Relative directory under the workspace.",
    )


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------


class ToolSpec(BaseModel):
    """Metadata for a registered tool."""

    name: str
    description: str
    args_model: type[BaseModel]
    handler: Callable[..., Any]

    model_config = {"arbitrary_types_allowed": True}


def deterministic_summarize(text: str, max_sentences: int = 3) -> str:
    """Offline-safe heuristic summarizer: first N non-empty sentences."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    sentences = [p.strip() for p in parts if p.strip()]
    if not sentences:
        return cleaned[:500]
    selected = sentences[:max_sentences]
    summary = " ".join(selected)
    if len(sentences) > max_sentences:
        summary += " …"
    return summary


class ToolRegistry:
    """Holds callable tools and dispatches validated invocations."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.workspace = settings.ensure_workspace()
        self._tools: dict[str, ToolSpec] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register(
            ToolSpec(
                name="http_get",
                description="Fetch an HTTP(S) URL and return status + truncated body.",
                args_model=HttpGetArgs,
                handler=self.http_get,
            )
        )
        self.register(
            ToolSpec(
                name="write_json_report",
                description="Write a JSON report file into the sandbox workspace.",
                args_model=WriteJsonReportArgs,
                handler=self.write_json_report,
            )
        )
        self.register(
            ToolSpec(
                name="summarize_text",
                description=(
                    "Summarize text. Default: deterministic heuristic. "
                    "Optional LLM when AGENCY_OPS_AGENT_LLM_ENABLED=true."
                ),
                args_model=SummarizeTextArgs,
                handler=self.summarize_text,
            )
        )
        self.register(
            ToolSpec(
                name="list_workspace",
                description="List files and directories in the sandbox workspace.",
                args_model=ListWorkspaceArgs,
                handler=self.list_workspace,
            )
        )

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def names(self) -> list[str]:
        return sorted(self._tools)

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def schemas(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for spec in self._tools.values():
            out.append(
                {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.args_model.model_json_schema(),
                }
            )
        return out

    def invoke(self, name: str, arguments: dict[str, Any]) -> Any:
        """Validate arguments against the tool schema and call the handler."""
        spec = self._tools.get(name)
        if spec is None:
            raise KeyError(f"Unknown tool: {name!r}. Available: {self.names()}")
        validated = spec.args_model.model_validate(arguments)
        return spec.handler(**validated.model_dump())

    def http_get(self, url: str, max_bytes: int | None = None) -> dict[str, Any]:
        limit = max_bytes or self.settings.http_max_bytes
        timeout = self.settings.http_timeout_seconds
        parsed = urlparse(url)
        if parsed.scheme.lower() not in ALLOWED_SCHEMES:
            raise ValueError(f"Disallowed URL scheme: {parsed.scheme!r}")

        logger.info("http_get url=%s max_bytes=%s", url, limit)
        with (
            httpx.Client(
                timeout=timeout,
                follow_redirects=True,
                max_redirects=5,
            ) as client,
            client.stream("GET", url) as response,
        ):
            chunks: list[bytes] = []
            total = 0
            truncated = False
            for chunk in response.iter_bytes():
                if not chunk:
                    continue
                remaining = limit - total
                if remaining <= 0:
                    truncated = True
                    break
                if len(chunk) > remaining:
                    chunks.append(chunk[:remaining])
                    total += remaining
                    truncated = True
                    break
                chunks.append(chunk)
                total += len(chunk)

            body_bytes = b"".join(chunks)
            try:
                text_body = body_bytes.decode(response.encoding or "utf-8", errors="replace")
            except (LookupError, TypeError):
                text_body = body_bytes.decode("utf-8", errors="replace")

            return {
                "url": str(response.url),
                "status_code": response.status_code,
                "content_type": response.headers.get("content-type"),
                "bytes_read": total,
                "truncated": truncated,
                "body": text_body,
            }

    def write_json_report(
        self,
        filename: str,
        data: dict[str, Any],
        indent: int = 2,
    ) -> dict[str, Any]:
        target = resolve_in_workspace(self.workspace, filename)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(data, indent=indent, ensure_ascii=False, default=str)
        target.write_text(payload + "\n", encoding="utf-8")
        rel = str(target.relative_to(self.workspace.resolve()))
        logger.info("write_json_report path=%s bytes=%s", rel, len(payload))
        return {
            "path": rel,
            "bytes_written": len(payload.encode("utf-8")),
            "absolute_denied": True,
        }

    def summarize_text(self, text: str, max_sentences: int = 3) -> dict[str, Any]:
        if self.settings.agent_llm_enabled and self.settings.openai_api_key:
            summary = self._llm_summarize(text, max_sentences)
            mode = "llm"
        else:
            summary = deterministic_summarize(text, max_sentences=max_sentences)
            mode = "deterministic"
        return {
            "summary": summary,
            "mode": mode,
            "max_sentences": max_sentences,
            "char_count": len(text),
        }

    def _llm_summarize(self, text: str, max_sentences: int) -> str:
        """Optional OpenAI-compatible chat completion. Never used in default CI."""
        api_key = self.settings.openai_api_key
        if not api_key:
            return deterministic_summarize(text, max_sentences=max_sentences)

        prompt = (
            f"Summarize the following text in at most {max_sentences} sentences.\n\n{text[:50_000]}"
        )
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.settings.openai_model,
            "messages": [
                {"role": "system", "content": "You are a concise summarizer."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 400,
        }
        url = self.settings.openai_base_url.rstrip("/") + "/chat/completions"
        try:
            with httpx.Client(timeout=self.settings.http_timeout_seconds) as client:
                resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                return str(data["choices"][0]["message"]["content"]).strip()
        except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
            logger.warning("LLM summarize failed (%s); falling back to heuristic", exc)
            return deterministic_summarize(text, max_sentences=max_sentences)

    def list_workspace(self, path: str = ".") -> dict[str, Any]:
        target = resolve_in_workspace(self.workspace, path)
        if not target.exists():
            return {"path": path, "exists": False, "entries": []}
        if not target.is_dir():
            raise SandboxError(f"Not a directory: {path!r}")

        entries: list[dict[str, Any]] = []
        for child in sorted(target.iterdir(), key=lambda p: p.name):
            rel = str(child.relative_to(self.workspace.resolve()))
            entries.append(
                {
                    "name": child.name,
                    "path": rel,
                    "is_dir": child.is_dir(),
                    "size": child.stat().st_size if child.is_file() else None,
                }
            )
        return {"path": path, "exists": True, "entries": entries}
