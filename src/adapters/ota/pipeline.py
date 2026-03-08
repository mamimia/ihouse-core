from __future__ import annotations

from typing import Any, Dict

from .schemas import NormalizedBookingEvent, ClassifiedBookingEvent, CanonicalEnvelope
from .validator import (
    validate_normalized_event,
    validate_classified_event,
    validate_canonical_envelope,
)
from .semantics import classify_normalized_event
from .registry import get_adapter
from .payload_validator import validate_ota_payload


def process_ota_event(
    provider: str,
    payload: Dict[str, Any],
    tenant_id: str,
) -> CanonicalEnvelope:
    """
    Shared OTA ingestion pipeline.

    Flow:

        boundary payload validation        <- Phase 47
        -> normalize provider payload
        -> structural validation
        -> semantic classification
        -> semantic validation
        -> canonical envelope creation
        -> canonical envelope validation
    """
    # Phase 47: boundary validation — before any canonical processing
    merged_payload = dict(payload)
    merged_payload.setdefault("tenant_id", tenant_id)

    validation = validate_ota_payload(provider, merged_payload)
    if not validation.valid:
        raise ValueError(
            f"OTA payload validation failed: {', '.join(validation.errors)}"
        )

    adapter = get_adapter(provider)

    normalized_payload = dict(payload)
    normalized_payload["tenant_id"] = tenant_id

    normalized: NormalizedBookingEvent = adapter.normalize(normalized_payload)

    validate_normalized_event(normalized)

    classified: ClassifiedBookingEvent = classify_normalized_event(normalized)

    validate_classified_event(classified)

    envelope: CanonicalEnvelope = adapter.to_canonical_envelope(classified)

    validate_canonical_envelope(envelope)

    return envelope
