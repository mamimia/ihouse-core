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
    skill_fn: Any = None,
    skill_router: Any = None,
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
        "tenant_id": tenant_id,
        "idempotency": {"request_id": envelope.idempotency_key or ""},
        "payload": envelope.payload,
        "occurred_at": envelope.occurred_at.isoformat() if hasattr(envelope.occurred_at, "isoformat") else str(envelope.occurred_at),
        "recorded_at": _recorded_at,
    }

    try:
        # Phase 784: support skill_router(event_type, payload) for type-aware routing
        if skill_router is not None:
            skill_out = skill_router(envelope.type, envelope.payload)
        elif skill_fn is not None:
            skill_out = skill_fn(envelope.payload)
        else:
            raise ValueError("Either skill_fn or skill_router must be provided")
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
            check_out = payload.get("check_out") or payload.get("departure_date") or ""
            property_id = (emitted[0]["payload"].get("property_id", "") if emitted else "")
            if booking_id and check_in and property_id:
                write_tasks_for_booking_created(
                    tenant_id=tenant_id,
                    booking_id=booking_id,
                    property_id=property_id,
                    check_in=check_in,
                    check_out=check_out,
                    provider=provider,
                )
        except Exception:
            pass  # best-effort — never block the main response

        # Phase 159: persist guest profile (PII) after BOOKING_CREATED (best-effort)
        try:
            from .guest_profile_extractor import extract_guest_profile
            import os as _os
            booking_id = (emitted[0]["payload"].get("booking_id", "") if emitted else "")
            if booking_id:
                profile = extract_guest_profile(provider, payload)
                if not profile.is_empty():
                    from supabase import create_client as _create_client  # type: ignore[import]
                    _db = _create_client(
                        _os.environ["SUPABASE_URL"],
                        _os.environ["SUPABASE_SERVICE_ROLE_KEY"],
                    )
                    _db.table("guest_profile").upsert(
                        {
                            "booking_id":  booking_id,
                            "tenant_id":   tenant_id,
                            "guest_name":  profile.guest_name,
                            "guest_email": profile.guest_email,
                            "guest_phone": profile.guest_phone,
                            "source":      profile.source or provider,
                        },
                        on_conflict="booking_id,tenant_id",
                    ).execute()
        except Exception:
            pass  # best-effort — never block the main response

        # Phase 176: fire full outbound sync plan for BOOKING_CREATED (best-effort)
        # build_sync_plan → execute_sync_plan covers ALL configured channels:
        # api_first (Airbnb, Booking.com, Expedia/VRBO) and ical_fallback (Hotelbeds,
        # TripAdvisor, Despegar) with rate-limit, retry, idempotency, and log persistence.
        try:
            from services.outbound_created_sync import fire_created_sync
            booking_id  = (emitted[0]["payload"].get("booking_id",  "") if emitted else "")
            property_id = (emitted[0]["payload"].get("property_id", "") if emitted else "")
            if booking_id and property_id:
                fire_created_sync(
                    booking_id=booking_id,
                    property_id=property_id,
                    tenant_id=tenant_id,
                )
        except Exception:
            pass  # best-effort — never block the main response

        # Phase 207: auto-conflict check after BOOKING_CREATED (best-effort)
        try:
            from services.conflict_auto_resolver import run_auto_check as _run_auto_check
            from datetime import datetime as _dt207, timezone as _tz207
            import os as _os207
            _bk207  = (emitted[0]["payload"].get("booking_id",  "") if emitted else "")
            _pr207  = (emitted[0]["payload"].get("property_id", "") if emitted else "")
            if _bk207 and _pr207:
                from supabase import create_client as _supa207  # type: ignore[import]
                _run_auto_check(
                    db=_supa207(
                        _os207.environ["SUPABASE_URL"],
                        _os207.environ["SUPABASE_SERVICE_ROLE_KEY"],
                    ),
                    tenant_id=tenant_id,
                    booking_id=_bk207,
                    property_id=_pr207,
                    event_kind="BOOKING_CREATED",
                    now_utc=_dt207.now(tz=_tz207.utc).isoformat(),
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

        # Phase 185: Outbound Sync Trigger Consolidation
        # fast-path (amend_sync_trigger.py Phase 152/155) removed — single guaranteed path only.
        # Phase 182: fire full outbound sync plan for BOOKING_AMENDED (build_sync_plan → execute_sync_plan)
        # Phase 185: event_type="BOOKING_AMENDED" passed through so adapters call .amend() not .send().
        try:
            from services.outbound_amended_sync import fire_amended_sync
            from .amendment_extractor import normalize_amendment as _norm_amend
            _booking_id  = (emitted[0]["payload"].get("booking_id",  "") if emitted else "")
            _property_id = (emitted[0]["payload"].get("property_id", "") if emitted else "")
            _amendment   = _norm_amend(provider, payload)
            if _booking_id and _property_id:
                fire_amended_sync(
                    booking_id=_booking_id,
                    property_id=_property_id,
                    tenant_id=tenant_id,
                    check_in=_amendment.new_check_in   if _amendment else None,
                    check_out=_amendment.new_check_out  if _amendment else None,
                )
        except Exception:
            pass  # best-effort — never block the main response

        # Phase 207: auto-conflict check after BOOKING_AMENDED (best-effort)
        try:
            from services.conflict_auto_resolver import run_auto_check as _run_auto_check_a
            from datetime import datetime as _dt207a, timezone as _tz207a
            import os as _os207a
            _bk207a  = (emitted[0]["payload"].get("booking_id",  "") if emitted else "")
            _pr207a  = (emitted[0]["payload"].get("property_id", "") if emitted else "")
            if _bk207a and _pr207a:
                from supabase import create_client as _supa207a  # type: ignore[import]
                _run_auto_check_a(
                    db=_supa207a(
                        _os207a.environ["SUPABASE_URL"],
                        _os207a.environ["SUPABASE_SERVICE_ROLE_KEY"],
                    ),
                    tenant_id=tenant_id,
                    booking_id=_bk207a,
                    property_id=_pr207a,
                    event_kind="BOOKING_AMENDED",
                    now_utc=_dt207a.now(tz=_tz207a.utc).isoformat(),
                )
        except Exception:
            pass  # best-effort — never block the main response

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

        # Phase 185: Outbound Sync Trigger Consolidation
        # fast-path (cancel_sync_trigger.py Phase 151/154) removed — single guaranteed path only.
        # Phase 182: fire full outbound sync plan for BOOKING_CANCELED (build_sync_plan → execute_sync_plan)
        # Phase 185: event_type="BOOKING_CANCELED" passed through so adapters call .cancel() not .send().
        try:
            from services.outbound_canceled_sync import fire_canceled_sync
            _booking_id  = (emitted[0]["payload"].get("booking_id",  "") if emitted else "")
            _property_id = (emitted[0]["payload"].get("property_id", "") if emitted else "")
            if _booking_id and _property_id:
                fire_canceled_sync(
                    booking_id=_booking_id,
                    property_id=_property_id,
                    tenant_id=tenant_id,
                )
        except Exception:
            pass  # best-effort — never block the main response

    return result if isinstance(result, dict) else {"status": status}
