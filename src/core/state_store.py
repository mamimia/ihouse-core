from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol


@dataclass(frozen=True)
class BookingState:
    booking_id: str
    version: int
    data: Dict[str, Any]


class StateStore(Protocol):
    def ensure_schema(self) -> None:
        ...

    def commit(self, *, envelope_id: str, events: List[Dict[str, Any]]) -> None:
        ...

    def get_booking(self, *, booking_id: str) -> Optional[BookingState]:
        ...

    def list_bookings(self, *, limit: int = 50) -> List[BookingState]:
        ...
