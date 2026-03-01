from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .state_store import BookingState, StateStore


def _now_ms() -> int:
    return int(time.time() * 1000)


class SupabaseStateStore(StateStore):
    def __init__(self, *, client: Any) -> None:
        self._client = client

    def ensure_schema(self) -> None:
        return

    def commit(self, *, envelope_id: str, events: List[Dict[str, Any]]) -> None:
        for ev in events:
            if ev.get("kind") != "StateUpsert":
                continue
            payload = ev.get("payload", {})
            if not isinstance(payload, dict):
                continue

            booking_id = payload.get("booking_id")
            if not booking_id:
                continue

            existing = (
                self._client.table("booking_state")
                .select("version,last_envelope_id")
                .eq("booking_id", booking_id)
                .limit(1)
                .execute()
            )

            if existing.data:
                last_env = existing.data[0].get("last_envelope_id")
                if last_env == envelope_id:
                    continue
                cur_v = int(existing.data[0].get("version") or 0)
                new_v = cur_v + 1
            else:
                new_v = 1

            row = {
                "booking_id": str(booking_id),
                "version": int(new_v),
                "state_json": payload,
                "updated_at_ms": _now_ms(),
                "last_envelope_id": str(envelope_id),
            }

            self._client.table("booking_state").upsert(row, on_conflict="booking_id").execute()

    def get_booking(self, *, booking_id: str) -> Optional[BookingState]:
        r = (
            self._client.table("booking_state")
            .select("booking_id,version,state_json")
            .eq("booking_id", booking_id)
            .limit(1)
            .execute()
        )
        if not r.data:
            return None
        row = r.data[0]
        return BookingState(
            booking_id=str(row["booking_id"]),
            version=int(row["version"]),
            data=row["state_json"],
        )

    def list_bookings(self, *, limit: int = 50) -> List[BookingState]:
        r = (
            self._client.table("booking_state")
            .select("booking_id,version,state_json")
            .order("updated_at_ms", desc=True)
            .limit(int(limit))
            .execute()
        )
        out: List[BookingState] = []
        for row in (r.data or []):
            out.append(
                BookingState(
                    booking_id=str(row["booking_id"]),
                    version=int(row["version"]),
                    data=row["state_json"],
                )
            )
        return out
