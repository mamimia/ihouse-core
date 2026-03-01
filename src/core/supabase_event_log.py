from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional


class SupabaseEventLog:
    def __init__(self, *, client: Any) -> None:
        self._client = client

    def append_event(
        self,
        envelope: Mapping[str, Any],
        *,
        idempotency_key: str,
    ) -> str:
        envelope_id = str(idempotency_key or "")
        if not envelope_id:
            envelope_id = f"anon_{uuid.uuid4().hex}"

        occurred_at = envelope.get("occurred_at")
        if not isinstance(occurred_at, str) or not occurred_at:
            occurred_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        row: Dict[str, Any] = {
            "event_id": envelope_id,
            "envelope_id": envelope_id,
            "kind": "envelope_received",
            "occurred_at": occurred_at,
            "payload_json": dict(envelope),
        }

        self._client.table("event_log").upsert(row, on_conflict="event_id").execute()
        return envelope_id

    def fetch_projection(self, *, query_name: str, params: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        return []
