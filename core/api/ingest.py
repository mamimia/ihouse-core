from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class IngestResult:
    event_id: str


class IngestAPI:
    """
    PHASE 8.1 – Formal Ingest Boundary

    Rules:
    - Delegates strictly to core append
    - No projections
    - No outbox triggering
    - No side effects
    - Deterministic only
    """

    def __init__(self, *, db: Any) -> None:
        self._db = db

    def append_event(
        self,
        envelope: Mapping[str, Any],
        *,
        idempotency_key: Optional[str] = None,
    ) -> IngestResult:
        event_id = self._db.append_event(
            envelope=envelope,
            idempotency_key=idempotency_key,
        )

        return IngestResult(event_id=event_id)
