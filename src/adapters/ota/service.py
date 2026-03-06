from typing import Dict, Any

from .pipeline import process_ota_event
from .schemas import CanonicalEnvelope


def ingest_provider_event(
    provider: str,
    payload: Dict[str, Any],
    tenant_id: str,
) -> CanonicalEnvelope:
    """
    Entry point for OTA ingestion.

    The service layer acts only as a thin wrapper around the OTA pipeline.

    Responsibilities:
    - accept provider webhook payload
    - forward payload into the shared OTA ingestion pipeline
    - return canonical envelope ready for apply_envelope
    """

    envelope = process_ota_event(
        provider=provider,
        payload=payload,
        tenant_id=tenant_id,
    )

    return envelope
