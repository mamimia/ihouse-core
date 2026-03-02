from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping


class SupabaseEventLog:
    def __init__(self, *, client: Any) -> None:
        self._client = client

    # --- Step 1: envelope id selection (NO DB write) ---
    def append_event(
        self,
        envelope: Mapping[str, Any],
        *,
        idempotency_key: str,
    ) -> str:
        envelope_id = str(idempotency_key or "").strip()
        if not envelope_id:
            raise ValueError("envelope_id is required (idempotency_key missing)")

        occurred_at = envelope.get("occurred_at")
        if not isinstance(occurred_at, str) or not occurred_at:
            _ = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

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
