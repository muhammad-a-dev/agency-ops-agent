"""In-memory + optional JSONL audit log for tool calls."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from threading import Lock
from typing import Any

from agency_ops_agent.models import ToolCallRecord

logger = logging.getLogger(__name__)


class AuditLog:
    """Thread-safe audit trail of tool invocations."""

    def __init__(self, jsonl_path: Path | None = None) -> None:
        self._records: list[ToolCallRecord] = []
        self._lock = Lock()
        self._jsonl_path = jsonl_path
        if jsonl_path is not None:
            jsonl_path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: ToolCallRecord) -> None:
        with self._lock:
            self._records.append(record)
            if self._jsonl_path is not None:
                self._write_jsonl(record)

    def _write_jsonl(self, record: ToolCallRecord) -> None:
        assert self._jsonl_path is not None
        line = record.model_dump_json() + "\n"
        try:
            with self._jsonl_path.open("a", encoding="utf-8") as fh:
                fh.write(line)
        except OSError:
            logger.exception("Failed to write audit JSONL to %s", self._jsonl_path)

    def list_records(self) -> list[ToolCallRecord]:
        with self._lock:
            return list(self._records)

    def clear(self) -> None:
        with self._lock:
            self._records.clear()

    def as_dicts(self) -> list[dict[str, Any]]:
        return [r.model_dump(mode="json") for r in self.list_records()]

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)

    def __bool__(self) -> bool:
        return True

    def dump_pretty(self) -> str:
        return json.dumps(self.as_dicts(), indent=2)
