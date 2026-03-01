from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from core.executor import CoreExecutor, CoreExecutionError
from core.ports import EventLogPort


@dataclass(frozen=True)
class IngestResult:
    event_id: str


class IngestAPI:
    """
    Phase 14:
    Canonical execution runs via CoreExecutor when wired.
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
        if self._executor is not None:
            try:
                res = self._executor.execute(
                    envelope=envelope,
                    idempotency_key=idempotency_key,
                )
                return IngestResult(event_id=res.envelope_id)
            except CoreExecutionError as e:
                raise ValueError(str(e)) from e

        event_id = self._db.append_event(
            envelope=envelope,
            idempotency_key=idempotency_key,
        )
        return IngestResult(event_id=event_id)
