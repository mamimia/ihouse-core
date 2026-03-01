from __future__ import annotations

from typing import Any, Dict, List, Literal, Protocol


ApplyStatus = Literal["APPLIED", "ALREADY_APPLIED"]


class EventLog(Protocol):
    def ensure_schema(self) -> None:
        ...

    def append_envelope_result(
        self,
        *,
        envelope: Dict[str, Any],
        emitted_events: List[Dict[str, Any]],
    ) -> ApplyStatus:
        ...
