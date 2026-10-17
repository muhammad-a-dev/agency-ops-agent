"""In-memory + optional JSONL audit log for tool calls."""

from __future__ import annotations

import json
import logging
from collections import deque
from pathlib import Path
from threading import Lock
from typing import Any

from agency_ops_agent.models import ToolCallRecord

logger = logging.getLogger(__name__)

# Default cap for in-memory records. The JSONL file (if set) keeps everything.
DEFAULT_MAX_RECORDS = 10_000


class AuditLog:
    """Thread-safe audit trail of tool invocations.

    In memory it keeps only the newest ``max_records`` entries, so a long
    running server does not grow forever (each ``http_get`` record can hold a
    response body of up to ``http_max_bytes``). The optional JSONL file is
    append-only and still receives every record.
    """

    def __init__(
        self,
        jsonl_path: Path | None = None,
        max_records: int = DEFAULT_MAX_RECORDS,
    ) -> None:
        if max_records < 1:
            raise ValueError("max_records must be at least 1")
        self.max_records = max_records
        self._records: deque[ToolCallRecord] = deque(maxlen=max_records)
        self._dropped = 0
        self._lock = Lock()
        self._jsonl_path = jsonl_path
        if jsonl_path is not None:
            jsonl_path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: ToolCallRecord) -> None:
        with self._lock:
            if len(self._records) == self.max_records:
                self._dropped += 1
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

    @property
    def dropped(self) -> int:
        """How many old records were evicted from memory to respect the cap."""
        with self._lock:
            return self._dropped

    def clear(self) -> None:
        with self._lock:
            self._records.clear()
            self._dropped = 0

    def as_dicts(self) -> list[dict[str, Any]]:
        return [r.model_dump(mode="json") for r in self.list_records()]

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)

    def __bool__(self) -> bool:
        return True

    def dump_pretty(self) -> str:
        return json.dumps(self.as_dicts(), indent=2)
