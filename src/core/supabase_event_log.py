from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Mapping


class SupabaseEventLog:
    def __init__(self, *, client: Any) -> None:
        self._client = client

    # --- Step 1: envelope append (ingest only) ---
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

        kind = envelope.get("type")
        if not isinstance(kind, str) or not kind:
            raise ValueError("Missing event type")

        row: Dict[str, Any] = {
            "event_id": envelope_id,
            "envelope_id": envelope_id,
            "kind": kind,
            "occurred_at": occurred_at,
            "payload_json": dict(envelope),
        }

        self._client.table("event_log").upsert(row, on_conflict="event_id").execute()

        return envelope_id

    # --- Step 2: canonical atomic apply via RPC ---
    def append_envelope_result(
        self,
        envelope: Mapping[str, Any],
        result: Mapping[str, Any],
        emitted_events=None,
    ):
        emitted = emitted_events if emitted_events is not None else result.get("emitted_events", [])

        response = self._client.rpc(
            "apply_envelope",
            {
                "p_envelope": dict(envelope),
                "p_emitted": emitted,
            },
        ).execute()

        if not response.data:
            raise RuntimeError("apply_envelope RPC returned no result")

        return response.data

    def fetch_projection(
        self,
        *,
        query_name: str,
        params: Mapping[str, Any],
    ):
        return []
