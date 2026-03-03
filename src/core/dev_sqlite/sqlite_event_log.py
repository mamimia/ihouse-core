from __future__ import annotations

import sqlite3
from typing import Any, Dict, List

from .event_log import ApplyStatus, EventLog
from .effects.sqlite_event_log import apply_result


class SqliteEventLog(EventLog):
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path

    def ensure_schema(self) -> None:
        conn = sqlite3.connect(self._db_path, timeout=30)
        try:
            # event_log schema is owned by migrations; this is a lightweight check
            conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='event_log'")
        finally:
            conn.close()

    def append_envelope_result(
        self,
        *,
        envelope: Dict[str, Any],
        emitted_events: List[Dict[str, Any]],
    ) -> ApplyStatus:
        conn = sqlite3.connect(self._db_path, timeout=30)
        try:
            return apply_result(conn, envelope, {"emitted_events": emitted_events})
        finally:
            conn.close()
