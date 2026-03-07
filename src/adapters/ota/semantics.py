from __future__ import annotations

from enum import Enum

from .schemas import NormalizedBookingEvent, ClassifiedBookingEvent


class BookingSemanticKind(str, Enum):
    CREATE = "CREATE"
    CANCEL = "CANCEL"
    MODIFY = "MODIFY"


def _extract_event_type(event: NormalizedBookingEvent) -> str:
    payload = event.payload

    candidates = (
        payload.get("event_type"),
        payload.get("type"),
        payload.get("action"),
        payload.get("event"),
        payload.get("status"),
    )

    for value in candidates:
        if isinstance(value, str) and value.strip():
            return value.strip().lower()

    raise ValueError("Unknown OTA event type: missing event_type in payload")


def classify_normalized_event(
    event: NormalizedBookingEvent,
) -> ClassifiedBookingEvent:
    """
    Convert a normalized OTA payload into a semantic classification.

    This layer decides the deterministic business meaning of the OTA event.

    It does NOT access booking_state.
    It does NOT perform reconciliation.
    """

    event_type = _extract_event_type(event)

    if event_type in {"reservation_created", "created", "new"}:
        semantic = BookingSemanticKind.CREATE
    elif event_type in {"reservation_cancelled", "cancelled", "canceled"}:
        semantic = BookingSemanticKind.CANCEL
    elif event_type in {"reservation_modified", "modified", "amended"}:
        semantic = BookingSemanticKind.MODIFY
    else:
        raise ValueError(f"Unknown OTA event type: {event_type}")

    return ClassifiedBookingEvent(
        normalized=event,
        semantic_kind=semantic.value,
    )


def classify_booking_event(
    event: NormalizedBookingEvent,
) -> ClassifiedBookingEvent:
    """
    Backward-compatible alias for older imports.
    """

    return classify_normalized_event(event)
