from typing import Dict, Any

from .registry import get_adapter
from .validator import (
    validate_normalized_event,
    validate_canonical_envelope,
)
from .semantics import (
    classify_normalized_event,
    validate_classified_event,
)


def process_provider_event(
    *,
    channel: str,
    raw_payload: Dict[str, Any],
    tenant_id: str,
    source: str,
):
    """
    Canonical OTA ingestion pipeline.

    provider payload
        ↓
    adapter.normalize
        ↓
    structural validation
        ↓
    semantic classification
        ↓
    semantic validation
        ↓
    canonical envelope creation
        ↓
    canonical envelope validation
    """

    adapter = get_adapter(channel)

    normalized = adapter.normalize(
        raw_payload,
        tenant_id=tenant_id,
        source=source,
    )

    validate_normalized_event(normalized)

    classified = classify_normalized_event(normalized)

    validate_classified_event(classified)

    envelope = adapter.to_canonical_envelope(normalized)

    validate_canonical_envelope(envelope)

    return envelope
