from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any

from .schemas import NormalizedBookingEvent, ClassifiedBookingEvent


class BookingSemanticKind(str, Enum):
    CREATE = "CREATE"
    CANCEL = "CANCEL"
    MODIFY = "MODIFY"


def classify_booking_event(event: NormalizedBookingEvent) -> ClassifiedBookingEvent:
    """
    Convert a normalized OTA payload into a semantic classification.

    This layer decides the deterministic business meaning of the OTA event.

    It does NOT access booking_state.
    It does NOT perform reconciliation.
    """

    event_type = event.event_type.lower()

    if event_type in ["reservation_created", "created", "new"]:
        semantic = BookingSemanticKind.CREATE

    elif event_type in ["reservation_cancelled", "cancelled", "canceled"]:
        semantic = BookingSemanticKind.CANCEL

    elif event_type in ["reservation_modified", "modified", "amended"]:
        semantic = BookingSemanticKind.MODIFY

    else:
        raise ValueError(f"Unknown OTA event type: {event.event_type}")

    return ClassifiedBookingEvent(
        provider=event.provider,
        reservation_id=event.reservation_id,
        event_type=event.event_type,
        semantic_kind=semantic,
        payload=event.payload,
    )
