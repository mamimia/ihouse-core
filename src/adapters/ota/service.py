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

    # Phase 76: recorded_at = server wall-clock at ingestion time.
    # This is DIFFERENT from occurred_at (business event time from OTA provider).
    # recorded_at is always set by OUR server and is never overridable by the payload.
    from datetime import datetime, timezone as _tz
    _recorded_at = datetime.now(_tz.utc).isoformat().replace("+00:00", "Z")

    envelope_dict = {
        "type": envelope.type,
        "idempotency": {"request_id": envelope.idempotency_key or ""},
        "payload": envelope.payload,
        "occurred_at": envelope.occurred_at.isoformat() if hasattr(envelope.occurred_at, "isoformat") else str(envelope.occurred_at),
        "recorded_at": _recorded_at,
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

    # Phase 73: BOOKING_NOT_FOUND → Ordering Buffer Auto-Route
    #
    # When a BOOKING_CANCELED or BOOKING_AMENDED arrives before BOOKING_CREATED,
    # apply_envelope returns BOOKING_NOT_FOUND. Instead of sending it only to the
    # DLQ (where it sits permanently), we also buffer it in ota_ordering_buffer so
    # ordering_trigger can auto-replay it once BOOKING_CREATED is APPLIED.
    #
    # Flow:
    #   1. write_to_dlq_returning_id → preserves event for audit (returns dlq_row_id)
    #   2. buffer_event(dlq_row_id, booking_id, event_type) → marks it as "waiting"
    #   3. ordering_trigger.trigger_ordered_replay fires on BOOKING_CREATED APPLIED
    #      → replays all "waiting" buffer rows via replay_dlq_row
    #
    # If buffering fails (best-effort), the event is still in the DLQ.

    _BUFFERABLE_TYPES = {"BOOKING_CANCELED", "BOOKING_AMENDED"}

    if status == "BOOKING_NOT_FOUND" and envelope.type in _BUFFERABLE_TYPES:
        try:
            from .dead_letter import write_to_dlq_returning_id
            from .ordering_buffer import buffer_event
            booking_id_for_buffer = (emitted[0]["payload"].get("booking_id", "") if emitted else "")
            dlq_row_id = write_to_dlq_returning_id(
                provider=provider,
                event_type=envelope.type,
                rejection_code="BOOKING_NOT_FOUND",
                rejection_msg="Buffered in ordering_buffer — awaiting BOOKING_CREATED",
                envelope_json=envelope_dict,
                emitted_json=emitted,
            )
            if booking_id_for_buffer:
                buffer_event(
                    dlq_row_id=dlq_row_id,
                    booking_id=booking_id_for_buffer,
                    event_type=envelope.type,
                )
        except Exception:
            pass  # best-effort — DLQ write via the original path below is the safety net
        # Return BUFFERED — event is not dead, it will be auto-replayed
        return {"status": "BUFFERED", "reason": "AWAITING_BOOKING_CREATED", "event_type": envelope.type}

    if status not in ("APPLIED", "ALREADY_APPLIED", "ALREADY_EXISTS", "ALREADY_EXISTS_BUSINESS"):
        write_to_dlq(
            provider=provider,
            event_type=envelope.type,
            rejection_code=status or "UNKNOWN_STATUS",
            rejection_msg=None,
            envelope_json=envelope_dict,
            emitted_json=emitted,
        )

    # After a successful BOOKING_CREATED, check the ordering buffer for
    # events that were waiting for this booking_id and replay them.
    if envelope.type == "BOOKING_CREATED" and status == "APPLIED":
        try:
            from .ordering_trigger import trigger_ordered_replay
            booking_id = (emitted[0]["payload"].get("booking_id", "") if emitted else "")
            if booking_id:
                trigger_ordered_replay(booking_id)
        except Exception:
            pass  # best-effort — never block the main response

        # Phase 66: persist financial facts to booking_financial_facts table (best-effort)
        try:
            from .financial_extractor import extract_financial_facts
            from .financial_writer import write_financial_facts
            booking_id = (emitted[0]["payload"].get("booking_id", "") if emitted else "")
            facts = extract_financial_facts(provider, payload)
            if booking_id and facts:
                write_financial_facts(
                    booking_id=booking_id,
                    tenant_id=tenant_id,
                    event_kind="BOOKING_CREATED",
                    facts=facts,
                )
        except Exception:
            pass  # best-effort — never block the main response

        # Phase 115: persist operational tasks after BOOKING_CREATED (best-effort)
        try:
            from tasks.task_writer import write_tasks_for_booking_created
            booking_id = (emitted[0]["payload"].get("booking_id", "") if emitted else "")
            check_in = payload.get("check_in") or payload.get("arrival_date") or ""
            property_id = (emitted[0]["payload"].get("property_id", "") if emitted else "")
            if booking_id and check_in and property_id:
                write_tasks_for_booking_created(
                    tenant_id=tenant_id,
                    booking_id=booking_id,
                    property_id=property_id,
                    check_in=check_in,
                    provider=provider,
                )
        except Exception:
            pass  # best-effort — never block the main response

    # Phase 69: persist updated financial facts for BOOKING_AMENDED events (best-effort)
    if envelope.type == "BOOKING_AMENDED" and status == "APPLIED":
        try:
            from .financial_extractor import extract_financial_facts
            from .financial_writer import write_financial_facts
            booking_id = (emitted[0]["payload"].get("booking_id", "") if emitted else "")
            facts = extract_financial_facts(provider, payload)
            if booking_id and facts:
                write_financial_facts(
                    booking_id=booking_id,
                    tenant_id=tenant_id,
                    event_kind="BOOKING_AMENDED",
                    facts=facts,
                )
        except Exception:
            pass  # best-effort — never block the main response

        # Phase 115: reschedule tasks due_date after BOOKING_AMENDED (best-effort)
        try:
            from tasks.task_writer import reschedule_tasks_for_booking_amended
            from .amendment_extractor import normalize_amendment
            booking_id = (emitted[0]["payload"].get("booking_id", "") if emitted else "")
            amendment = normalize_amendment(provider, payload)
            new_check_in = amendment.new_check_in if amendment else None
            if booking_id and new_check_in:
                reschedule_tasks_for_booking_amended(
                    booking_id=booking_id,
                    new_check_in=new_check_in,
                    tenant_id=tenant_id,
                )
        except Exception:
            pass  # best-effort — never block the main response

    # Phase 115: cancel PENDING tasks after BOOKING_CANCELED (best-effort)
    if envelope.type == "BOOKING_CANCELED" and status == "APPLIED":
        try:
            from tasks.task_writer import cancel_tasks_for_booking_canceled
            booking_id = (emitted[0]["payload"].get("booking_id", "") if emitted else "")
            if booking_id:
                cancel_tasks_for_booking_canceled(
                    booking_id=booking_id,
                    tenant_id=tenant_id,
                )
        except Exception:
            pass  # best-effort — never block the main response

    return result if isinstance(result, dict) else {"status": status}
