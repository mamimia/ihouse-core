from __future__ import annotations
from . import _dev_guard

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, List

from core.dev_sqlite.config import db_path


@dataclass
class SqliteEventLogAdapter:
    """
    Phase 14:

    This adapter is now strictly a port implementation.

    It does NOT:
    - execute skills
    - write to event_log
    - commit state
    - call apply_result

    All deterministic execution and commit policy
    live inside CoreExecutor only.
    """

    _db_path: str = ""

    def __post_init__(self) -> None:
        if not self._db_path:
            self._db_path = db_path()

    def append_event(
        self,
        envelope: Mapping[str, Any],
        *,
        idempotency_key: Optional[str] = None,
    ) -> str:
        env: Dict[str, Any] = dict(envelope)

        if idempotency_key and not env.get("envelope_id"):
            env["envelope_id"] = str(idempotency_key)

        if not env.get("envelope_id"):
            raise ValueError("envelope_id is required")

        if not env.get("occurred_at"):
            raise ValueError("occurred_at is required")

        return str(env["envelope_id"])

    def fetch_projection(
        self,
        *,
        query_name: str,
        params: Mapping[str, Any],
    ) -> List[Mapping[str, Any]]:
        return []
