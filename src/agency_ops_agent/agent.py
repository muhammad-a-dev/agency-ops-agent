"""Deterministic tool-using agent loop (optional LLM behind env flag)."""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from agency_ops_agent.audit import AuditLog
from agency_ops_agent.models import AgentResult, ToolCallRecord
from agency_ops_agent.settings import Settings
from agency_ops_agent.tools import ToolRegistry

logger = logging.getLogger(__name__)

URL_RE = re.compile(r"https?://[^\s\]\)\"'<>]+", re.IGNORECASE)


class Agent:
    """Plan/act agent with max steps, validation, and structured final answer.

    Default mode uses deterministic heuristic routing so CI needs no API keys.
    When ``settings.agent_llm_enabled`` is true *and* a key is present, an
    optional LLM planner may be used (documented in README).
    """

    def __init__(
        self,
        settings: Settings,
        tools: ToolRegistry | None = None,
        audit: AuditLog | None = None,
    ) -> None:
        self.settings = settings
        self.tools = tools if tools is not None else ToolRegistry(settings)
        self.audit = audit if audit is not None else AuditLog(settings.audit_log_path)

    def run(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        max_steps: int | None = None,
    ) -> AgentResult:
        """Execute the agent loop and return a structured result."""
        context = context or {}
        limit = max_steps or self.settings.max_steps
        tool_calls: list[ToolCallRecord] = []
        observations: list[str] = []

        logger.info("agent.start task=%r max_steps=%s", task[:120], limit)

        plan = self._plan(task, context)
        steps_used = 0

        for step in plan[:limit]:
            steps_used += 1
            name = step["tool"]
            arguments = step.get("arguments", {})
            record = self._call_tool(name, arguments)
            tool_calls.append(record)
            self.audit.append(record)
            if record.error:
                observations.append(f"{name} error: {record.error}")
            else:
                observations.append(f"{name} ok: {self._brief(record.result)}")

        answer = self._finalize(task, context, tool_calls, observations)
        result = AgentResult(
            answer=answer,
            steps_used=steps_used,
            tool_calls=tool_calls,
            metadata={
                "mode": "llm" if self._llm_active() else "deterministic",
                "planned_steps": len(plan),
                "tools_available": self.tools.names(),
            },
        )
        logger.info("agent.done steps=%s calls=%s", steps_used, len(tool_calls))
        return result

    def _llm_active(self) -> bool:
        return bool(self.settings.agent_llm_enabled and self.settings.openai_api_key)

    def _plan(self, task: str, context: dict[str, Any]) -> list[dict[str, Any]]:
        """Build an ordered list of tool calls for the task."""
        if self._llm_active():
            llm_plan = self._llm_plan(task, context)
            if llm_plan:
                return llm_plan
        return self._heuristic_plan(task, context)

    def _heuristic_plan(self, task: str, context: dict[str, Any]) -> list[dict[str, Any]]:
        """Rule-based router: URL fetch -> summarize -> report -> list."""
        steps: list[dict[str, Any]] = []
        lower = task.lower()
        urls = URL_RE.findall(task)
        ctx_url = context.get("url")
        if isinstance(ctx_url, str) and ctx_url.strip():
            urls = [ctx_url.strip(), *urls]

        fetched_for_summary = False
        body_placeholder = False

        if urls:
            steps.append({"tool": "http_get", "arguments": {"url": urls[0]}})
            fetched_for_summary = True
            body_placeholder = True

        wants_summary = any(k in lower for k in ("summar", "digest", "brief", "tldr", "overview"))
        text_for_summary = context.get("text")
        if wants_summary or fetched_for_summary:
            if isinstance(text_for_summary, str) and text_for_summary.strip():
                steps.append(
                    {
                        "tool": "summarize_text",
                        "arguments": {
                            "text": text_for_summary,
                            "max_sentences": int(context.get("max_sentences", 3)),
                        },
                    }
                )
            elif body_placeholder:
                steps.append(
                    {
                        "tool": "summarize_text",
                        "arguments": {
                            "text": "__FROM_LAST_HTTP_BODY__",
                            "max_sentences": int(context.get("max_sentences", 3)),
                        },
                    }
                )
            elif not fetched_for_summary and "summar" in lower:
                steps.append(
                    {
                        "tool": "summarize_text",
                        "arguments": {"text": task, "max_sentences": 3},
                    }
                )

        wants_report = any(k in lower for k in ("report", "write json", "save", "persist", "json"))
        if wants_report or fetched_for_summary:
            filename = str(context.get("report_filename", "reports/agent_report.json"))
            steps.append(
                {
                    "tool": "write_json_report",
                    "arguments": {
                        "filename": filename,
                        "data": {
                            "task": task,
                            "status": "completed",
                            "notes": "Generated by deterministic agency-ops-agent",
                        },
                    },
                }
            )

        wants_list = any(k in lower for k in ("list", "workspace", "files", "ls "))
        if wants_list or wants_report or fetched_for_summary:
            steps.append({"tool": "list_workspace", "arguments": {"path": "."}})

        if not steps:
            steps.append(
                {
                    "tool": "summarize_text",
                    "arguments": {"text": task, "max_sentences": 2},
                }
            )
            steps.append({"tool": "list_workspace", "arguments": {"path": "."}})

        return steps

    def _call_tool(self, name: str, arguments: dict[str, Any]) -> ToolCallRecord:
        args = dict(arguments)
        if name == "summarize_text" and args.get("text") == "__FROM_LAST_HTTP_BODY__":
            body = self._last_http_body()
            args["text"] = body or "(empty response body)"

        if name == "write_json_report":
            data = dict(args.get("data") or {})
            last_summary = self._last_summary()
            if last_summary:
                data["summary"] = last_summary
            last_http = self._last_http_meta()
            if last_http:
                data["http"] = last_http
            args["data"] = data

        started = time.perf_counter()
        error: str | None = None
        result: Any = None
        try:
            result = self.tools.invoke(name, args)
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
            logger.warning("tool.error name=%s error=%s", name, error)
        duration_ms = (time.perf_counter() - started) * 1000
        return ToolCallRecord(
            tool=name,
            arguments=args,
            result=result,
            error=error,
            duration_ms=round(duration_ms, 2),
        )

    def _last_http_body(self) -> str | None:
        for rec in reversed(self.audit.list_records()):
            if rec.tool == "http_get" and isinstance(rec.result, dict):
                body = rec.result.get("body")
                return str(body) if body is not None else None
        return None

    def _last_http_meta(self) -> dict[str, Any] | None:
        for rec in reversed(self.audit.list_records()):
            if rec.tool == "http_get" and isinstance(rec.result, dict):
                return {
                    "url": rec.result.get("url"),
                    "status_code": rec.result.get("status_code"),
                    "truncated": rec.result.get("truncated"),
                    "bytes_read": rec.result.get("bytes_read"),
                }
        return None

    def _last_summary(self) -> str | None:
        for rec in reversed(self.audit.list_records()):
            if rec.tool == "summarize_text" and isinstance(rec.result, dict):
                s = rec.result.get("summary")
                return str(s) if s is not None else None
        return None

    def _brief(self, result: Any, limit: int = 160) -> str:
        text = repr(result)
        return text if len(text) <= limit else text[: limit - 1] + "..."

    def _finalize(
        self,
        task: str,
        context: dict[str, Any],
        tool_calls: list[ToolCallRecord],
        observations: list[str],
    ) -> str:
        errors = [c for c in tool_calls if c.error]
        ok = [c for c in tool_calls if not c.error]
        lines = [
            f"Completed task with {len(ok)} successful tool call(s) ({len(errors)} error(s)).",
        ]
        summary = self._last_summary()
        if summary:
            lines.append(f"Summary: {summary}")
        http_meta = self._last_http_meta()
        if http_meta:
            lines.append(
                f"Fetched {http_meta.get('url')} "
                f"(status={http_meta.get('status_code')}, "
                f"bytes={http_meta.get('bytes_read')})."
            )
        for obs in observations[-4:]:
            lines.append(f"- {obs}")
        if not tool_calls:
            lines.append("No tools were invoked.")
        return "\n".join(lines)

    def _llm_plan(self, task: str, context: dict[str, Any]) -> list[dict[str, Any]] | None:
        """Optional LLM planner. Returns None on failure -> heuristic fallback."""
        logger.info("LLM planner requested; falling back to heuristic for safety")
        _ = (task, context)
        return None
