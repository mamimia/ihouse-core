from __future__ import annotations

from typing import Any, Dict

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
    - return canonical envelope ready for core ingest
    """

    envelope = process_ota_event(
        provider=provider,
        payload=payload,
        tenant_id=tenant_id,
    )

    return envelope


def ingest_provider_event_with_dlq(
    provider: str,
    payload: Dict[str, Any],
    tenant_id: str,
    *,
    apply_fn: Any,
    skill_fn: Any,
) -> Dict[str, Any]:
    """
    Extended ingestion entry point that routes rejections to the DLQ.

    Flow:
    1. ingest_provider_event → canonical envelope
    2. skill_fn(envelope.payload) → emitted events
    3. apply_fn(envelope, emitted) → Supabase apply_envelope result
    4. On non-APPLIED result or exception → write_to_dlq (best-effort, never blocks)

    This is the production-safe entry point. The canonical apply gate
    (apply_fn / apply_envelope) is never bypassed.
    """
    from .dead_letter import write_to_dlq

    envelope = process_ota_event(
        provider=provider,
        payload=payload,
        tenant_id=tenant_id,
    )

    envelope_dict = {
        "type": envelope.type,
        "idempotency": {"request_id": envelope.idempotency_key or ""},
        "payload": envelope.payload,
        "occurred_at": envelope.occurred_at.isoformat() if hasattr(envelope.occurred_at, "isoformat") else str(envelope.occurred_at),
    }

    try:
        skill_out = skill_fn(envelope.payload)
        emitted = [{"type": e.type, "payload": dict(e.payload)} for e in skill_out.events_to_emit]
    except Exception as exc:
        write_to_dlq(
            provider=provider,
            event_type=envelope.type,
            rejection_code="SKILL_ERROR",
            rejection_msg=str(exc),
            envelope_json=envelope_dict,
            emitted_json=None,
        )
        raise

    try:
        result = apply_fn(envelope_dict, emitted)
    except Exception as exc:
        write_to_dlq(
            provider=provider,
            event_type=envelope.type,
            rejection_code=type(exc).__name__,
            rejection_msg=str(exc),
            envelope_json=envelope_dict,
            emitted_json=emitted,
        )
        return {"status": "REJECTED", "rejection_code": type(exc).__name__, "rejection_msg": str(exc)}

    status = result.get("status", "") if isinstance(result, dict) else ""
    if status not in ("APPLIED", "ALREADY_APPLIED", "ALREADY_EXISTS", "ALREADY_EXISTS_BUSINESS"):
        write_to_dlq(
            provider=provider,
            event_type=envelope.type,
            rejection_code=status or "UNKNOWN_STATUS",
            rejection_msg=None,
            envelope_json=envelope_dict,
            emitted_json=emitted,
        )

    return result if isinstance(result, dict) else {"status": status}
