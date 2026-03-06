from __future__ import annotations

from .schemas import (
    NormalizedBookingEvent,
    ClassifiedBookingEvent,
    CanonicalEnvelope,
)


SUPPORTED_CANONICAL_TYPES = {
    "BOOKING_CREATED",
    "BOOKING_CANCELED",
}


def validate_normalized_event(event: NormalizedBookingEvent) -> None:
    """
    Structural validation for normalized provider events.
    """

    if not event.tenant_id:
        raise ValueError("tenant_id is required")

    if not event.provider:
        raise ValueError("provider is required")

    if not event.external_event_id:
        raise ValueError("external_event_id is required")

    if not event.reservation_id:
        raise ValueError("reservation_id is required")

    if not event.property_id:
        raise ValueError("property_id is required")

    if not event.occurred_at:
        raise ValueError("occurred_at is required")

    if not isinstance(event.payload, dict):
        raise ValueError("payload must be a dictionary")


def validate_classified_event(event: ClassifiedBookingEvent) -> None:
    """
    Ensure semantic classification is supported.
    """

    if event.semantic_kind not in {"CREATE", "CANCEL", "MODIFY"}:
        raise ValueError(f"unsupported semantic kind: {event.semantic_kind}")

    if event.semantic_kind == "MODIFY":
        raise ValueError("MODIFY events are deterministically rejected")


def validate_canonical_envelope(envelope: CanonicalEnvelope) -> None:
    """
    Validate canonical envelope before entering the core ingestion system.
    """

    if not envelope.tenant_id:
        raise ValueError("tenant_id is required")

    if envelope.type not in SUPPORTED_CANONICAL_TYPES:
        raise ValueError(f"unsupported canonical type: {envelope.type}")

    if not envelope.occurred_at:
        raise ValueError("occurred_at is required")

    if not isinstance(envelope.payload, dict):
        raise ValueError("payload must be a dictionary")
