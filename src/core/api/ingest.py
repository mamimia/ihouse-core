from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from core.executor import CoreExecutionError, CoreExecutor
from core.ports import EventLogPort


@dataclass(frozen=True)
class IngestResult:
    event_id: str


class IngestAPI:
    """
    Canonical ingest surface.

    Rule:
    - In production runtime, ingest MUST run via CoreExecutor.
    - No fallback writes are allowed (no SQLite / no direct event_log writes).
    """

    def __init__(
        self,
        *,
        db: EventLogPort,
        executor: Optional[CoreExecutor] = None,
    ) -> None:
        self._db = db
        self._executor = executor

    def append_event(
        self,
        envelope: Mapping[str, Any],
        *,
        idempotency_key: Optional[str] = None,
    ) -> IngestResult:
        if self._executor is None:
            raise RuntimeError("INGEST_EXECUTOR_REQUIRED (no fallback allowed)")

        try:
            res = self._executor.execute(
                envelope=envelope,
                idempotency_key=idempotency_key,
            )
            return IngestResult(event_id=res.envelope_id)
        except CoreExecutionError as e:
            raise ValueError(str(e)) from e
