from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

from core.event_log import ApplyStatus


@dataclass(frozen=True)
class StoredEnvelope:
    envelope_id: str
    envelope: Dict[str, Any]


class InMemoryEventLogPort:
    """
    Minimal EventLogPort for unit tests.
    Provides envelope_id selection + event persistence in memory.
    """

    def __init__(self) -> None:
        self._envelopes: List[StoredEnvelope] = []

    def append_event(self, *, envelope: Mapping[str, Any], idempotency_key: str) -> str:
        envelope_id = str(idempotency_key or "").strip()
        if not envelope_id:
            raise ValueError("envelope_id is required (idempotency_key missing)")
        self._envelopes.append(StoredEnvelope(envelope_id=envelope_id, envelope=dict(envelope)))
        return envelope_id

    def all_envelopes(self) -> List[StoredEnvelope]:
        return list(self._envelopes)


class InMemoryEventLogApplier:
    """
    Minimal EventLog applier for unit tests.
    Simulates atomic apply by always returning APPLIED and recording results.
    """

    def __init__(self) -> None:
        self._applied: List[Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]] = []
        self._projections: Dict[str, List[Dict[str, Any]]] = {}

    def append_envelope_result(
        self,
        *,
        envelope: Mapping[str, Any],
        result: Mapping[str, Any],
        emitted_events: Optional[List[Dict[str, Any]]] = None,
    ) -> ApplyStatus:
        emitted = emitted_events or []
        self._applied.append((dict(envelope), dict(result), list(emitted)))
        return "APPLIED"

    def fetch_projection(self, *, query_name: str, params: Mapping[str, Any]) -> List[Dict[str, Any]]:
        return list(self._projections.get(query_name, []))

    def set_projection(self, query_name: str, rows: List[Dict[str, Any]]) -> None:
        self._projections[query_name] = list(rows)

    def applied(self) -> List[Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]]:
        return list(self._applied)
