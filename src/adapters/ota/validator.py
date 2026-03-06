from .schemas import (
    NormalizedBookingEvent,
    CanonicalExternalEnvelopeInput,
)


SUPPORTED_TYPES = {
    "BOOKING_SYNC_INGEST",
}


def validate_normalized_event(event: NormalizedBookingEvent) -> None:
    if event.canonical_type not in SUPPORTED_TYPES:
        raise ValueError("unsupported_canonical_type")

    if not event.tenant_id:
        raise ValueError("missing_tenant_id")

    if not event.source:
        raise ValueError("missing_source")

    if not event.reservation_ref:
        raise ValueError("missing_reservation_ref")

    if not event.property_id:
        raise ValueError("missing_property_id")

    if not event.occurred_at:
        raise ValueError("missing_occurred_at")

    if not event.idempotency_request_id:
        raise ValueError("missing_idempotency_request_id")


def validate_canonical_envelope(
    envelope: CanonicalExternalEnvelopeInput,
) -> None:
    if envelope.type not in SUPPORTED_TYPES:
        raise ValueError("unsupported_envelope_type")

    if not envelope.payload:
        raise ValueError("missing_payload")

    if not envelope.occurred_at:
        raise ValueError("missing_occurred_at")

    if not envelope.idempotency_request_id:
        raise ValueError("missing_request_id")

    provider = envelope.payload.get("provider")
    external_booking_id = envelope.payload.get("external_booking_id")
    property_id = envelope.payload.get("property_id")
    provider_payload = envelope.payload.get("provider_payload")

    if not provider:
        raise ValueError("missing_provider")

    if not external_booking_id:
        raise ValueError("missing_external_booking_id")

    if not property_id:
        raise ValueError("missing_property_id")

    if not isinstance(provider_payload, dict):
        raise ValueError("missing_provider_payload")

    status = str(provider_payload.get("status") or "").strip().lower()
    if not status:
        raise ValueError("missing_provider_status")

    if status != "cancelled":
        start_date = provider_payload.get("start_date")
        end_date = provider_payload.get("end_date")
        if not start_date or not end_date:
            raise ValueError("missing_booking_dates")
