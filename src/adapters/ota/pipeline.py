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


def process_ota_event(
    provider: str,
    payload: Dict[str, Any],
    tenant_id: str,
) -> CanonicalEnvelope:
    """
    Shared OTA ingestion pipeline.

    Flow:

        normalize provider payload
        -> structural validation
        -> semantic classification
        -> semantic validation
        -> canonical envelope creation
        -> canonical envelope validation
    """

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
