from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Protocol, TypedDict


class AppendEventResult(TypedDict):
    event_id: str


class EventLogPort(Protocol):
    def append_event(self, envelope: Mapping[str, Any], *, idempotency_key: str) -> str: ...
    def fetch_projection(self, *, query_name: str, params: Mapping[str, Any]) -> list[Mapping[str, Any]]: ...


class BookingState(TypedDict):
    booking_id: str
    version: int
    data: Dict[str, Any]


class StateStorePort(Protocol):
    def ensure_schema(self) -> None: ...
    def commit(self, *, envelope_id: str, events: List[Dict[str, Any]]) -> None: ...
    def get_booking(self, *, booking_id: str) -> Optional[BookingState]: ...
    def list_bookings(self, *, limit: int = 50) -> List[BookingState]: ...
