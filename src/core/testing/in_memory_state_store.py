from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence


@dataclass
class _Row:
    version: int
    last_envelope_id: str
    state_json: Dict[str, Any]


class InMemoryStateStorePort:
    """
    Minimal StateStorePort for unit tests.

    Semantics:
    Only commit via explicit upserts.
    Idempotent by last_envelope_id.
    Version increments only when an upsert is applied.
    """

    def __init__(self) -> None:
        self._rows: Dict[str, _Row] = {}

    def ensure_schema(self) -> None:
        return

    def commit_upserts(self, *, envelope_id: str, upserts: Sequence[Mapping[str, Any]]) -> None:
        for u in upserts:
            key = str(u.get("key") or u.get("booking_id") or "")
            value = u.get("value") or u.get("state_json") or u.get("data")
            expected = str(u.get("expected_last_envelope_id") or u.get("expected_last_envelope_id".upper()) or "")
            if not key or not isinstance(value, Mapping):
                continue

            row = self._rows.get(key)
            if row and row.last_envelope_id == envelope_id:
                continue
            if expected and row and row.last_envelope_id != expected:
                continue

            next_v = (row.version + 1) if row else 1
            self._rows[key] = _Row(
                version=next_v,
                last_envelope_id=envelope_id,
                state_json=dict(value),
            )

    def commit(self, *, envelope_id: str, events: Sequence[Mapping[str, Any]]) -> None:
        return

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        row = self._rows.get(str(key))
        if not row:
            return None
        return {
            "key": str(key),
            "version": row.version,
            "last_envelope_id": row.last_envelope_id,
            "state_json": json.loads(json.dumps(row.state_json)),
        }

    def all_keys(self) -> List[str]:
        return list(self._rows.keys())
