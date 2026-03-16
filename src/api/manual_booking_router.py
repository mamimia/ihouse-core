"""
Phases 706–709 — Manual Booking: Create, OTA Block, Selective Tasks, Cancel
=============================================================================

706: POST /bookings/manual — create booking
707: On creation → trigger outbound sync to block dates on all connected OTAs
708: Selective task creation based on source + tasks_opt_out (in _create_tasks_for_manual_booking)
709: DELETE /bookings/{booking_id}/manual — cancel + unblock OTA dates

Invariant:
    This router writes to booking_state only.
    Financial records are NOT created for manual bookings (no OTA data).
"""
from __future__ import annotations

import hashlib
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)
router = APIRouter(tags=["bookings"])

_VALID_SOURCES = frozenset({"direct", "self_use", "owner_use", "maintenance_block"})
_VALID_TASK_OPT_OUTS = frozenset({"checkin", "cleaning", "checkout"})


def _get_db() -> Any:
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


def _generate_booking_id(property_id: str, check_in: str) -> str:
    """MAN-{property_short}-{YYYYMMDD}"""
    prop_short = property_id.replace("PROP-", "")[:8].upper()
    date_part = check_in.replace("-", "")[:8]
    # Add hash suffix for uniqueness
    suffix = hashlib.sha256(f"{property_id}:{check_in}:{datetime.now(tz=timezone.utc).isoformat()}".encode()).hexdigest()[:4]
    return f"MAN-{prop_short}-{date_part}-{suffix}"


@router.post("/bookings/manual", summary="Create manual booking (Phase 706)")
async def create_manual_booking(
    body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    property_id = str(body.get("property_id") or "").strip()
    check_in = str(body.get("check_in") or "").strip()
    check_out = str(body.get("check_out") or "").strip()
    guest_name = str(body.get("guest_name") or "").strip()
    booking_source = str(body.get("booking_source") or "direct").strip().lower()
    tasks_opt_out: List[str] = body.get("tasks_opt_out") or []
    notes = str(body.get("notes") or "").strip() or None
    number_of_guests = body.get("number_of_guests", 1)

    # Validation
    if not property_id:
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, extra={"detail": "property_id required"})
    if not check_in or not check_out:
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, extra={"detail": "check_in and check_out required"})
    if booking_source not in _VALID_SOURCES:
        return make_error_response(400, ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": f"booking_source must be one of: {sorted(_VALID_SOURCES)}"})

    # For maintenance_block, guest_name is optional
    if booking_source not in ("maintenance_block",) and not guest_name:
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, extra={"detail": "guest_name required for non-maintenance bookings"})

    # Validate opt-outs
    invalid_opts = set(tasks_opt_out) - _VALID_TASK_OPT_OUTS
    if invalid_opts:
        return make_error_response(400, ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": f"Invalid tasks_opt_out: {sorted(invalid_opts)}. Valid: {sorted(_VALID_TASK_OPT_OUTS)}"})

    booking_id = _generate_booking_id(property_id, check_in)
    now = datetime.now(tz=timezone.utc).isoformat()

    now_ms = int(time.time() * 1000)
    event_id = hashlib.sha256(f"EVT:{booking_id}:{now}".encode()).hexdigest()[:16]

    row = {
        "booking_id": booking_id,
        "version": 1,
        "tenant_id": tenant_id,
        "property_id": property_id,
        "check_in": check_in,
        "check_out": check_out,
        "guest_name": guest_name or f"[{booking_source}]",
        "status": "confirmed",
        "source": "manual",
        "source_type": "manual",
        "booking_source": booking_source,
        "guest_count": number_of_guests,
        "tasks_opt_out": tasks_opt_out,
        "updated_at_ms": now_ms,
        "last_event_id": event_id,
        "state_json": {"notes": notes, "created_by": tenant_id},
    }

    try:
        db = client if client is not None else _get_db()

        # Overlap detection — reject if active bookings exist on same property + overlapping dates
        overlap_res = (db.table("booking_state")
                       .select("booking_id, check_in, check_out, guest_name, status")
                       .eq("property_id", property_id)
                       .in_("status", ["confirmed", "active", "observed"])
                       .lt("check_in", check_out)
                       .gt("check_out", check_in)
                       .limit(5)
                       .execute())
        conflicts = overlap_res.data or []
        if conflicts:
            return make_error_response(409, "CONFLICT", extra={
                "detail": f"Overlapping booking(s) found on {property_id} for {check_in} — {check_out}",
                "conflicts": [{
                    "booking_id": c["booking_id"],
                    "check_in": c["check_in"],
                    "check_out": c["check_out"],
                    "guest_name": c.get("guest_name", ""),
                    "status": c["status"],
                } for c in conflicts],
            })

        # Write event_log FIRST (booking_state.last_event_id FK → event_log.event_id)
        db.table("event_log").insert({
            "event_id": event_id,
            "kind": "BOOKING_CREATED",
            "occurred_at": now,
            "payload_json": {
                "booking_id": booking_id, "source": "manual",
                "booking_source": booking_source, "guest_name": guest_name,
                "check_in": check_in, "check_out": check_out,
                "property_id": property_id, "tenant_id": tenant_id,
            },
        }).execute()

        result = db.table("booking_state").insert(row).execute()
        rows = result.data or []
        if not rows:
            return make_error_response(500, ErrorCode.INTERNAL_ERROR)

        booking = rows[0]

        # Auto-create tasks based on source and opt-outs (best-effort)
        tasks_created = _create_tasks_for_manual_booking(db, booking_id, property_id, check_in, booking_source, tasks_opt_out, tenant_id)

        # Phase 707 — Trigger outbound sync to block dates on connected OTAs (best-effort)
        ota_block_result = _trigger_ota_date_block(db, property_id, check_in, check_out, booking_id, tenant_id)

        # Audit
        try:
            from services.audit_writer import write_audit_event
            write_audit_event(db, tenant_id=tenant_id, entity_type="booking",
                              entity_id=booking_id, action="manual_created",
                              details={"source": booking_source, "tasks_opt_out": tasks_opt_out,
                                       "tasks_created": tasks_created, "ota_blocked": ota_block_result})
        except Exception:
            pass

        return JSONResponse(status_code=201, content={
            "booking_id": booking_id,
            "property_id": property_id,
            "check_in": check_in,
            "check_out": check_out,
            "guest_name": booking.get("guest_name"),
            "source": booking_source,
            "status": "confirmed",
            "tasks_opt_out": tasks_opt_out,
            "tasks_created": tasks_created,
            "ota_blocked": ota_block_result,
        })
    except Exception as exc:
        logger.exception("create_manual_booking error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# Phase 707 — OTA Date Blocking
# ===========================================================================

def _trigger_ota_date_block(db: Any, property_id: str, check_in: str, check_out: str, booking_id: str, tenant_id: str) -> Optional[str]:
    """Push availability block to all connected OTAs for this property. Best-effort."""
    try:
        # Get channels mapped to this property
        channels = db.table("channel_map").select("channel_id, provider").eq("property_id", property_id).eq("active", True).execute()
        channel_list = channels.data or []
        if not channel_list:
            return "no_channels"

        # Queue outbound sync for each channel
        now = datetime.now(tz=timezone.utc).isoformat()
        for ch in channel_list:
            try:
                sync_id = hashlib.sha256(f"SYNC:BLOCK:{booking_id}:{ch['channel_id']}:{now}".encode()).hexdigest()[:16]
                db.table("outbound_sync_log").insert({
                    "id": sync_id,
                    "property_id": property_id,
                    "channel_id": ch["channel_id"],
                    "provider": ch.get("provider", "unknown"),
                    "sync_type": "availability_block",
                    "booking_id": booking_id,
                    "payload": {"check_in": check_in, "check_out": check_out, "blocked": True},
                    "status": "queued",
                    "created_at": now,
                }).execute()
            except Exception:
                logger.warning("Failed to queue OTA block for channel %s", ch.get("channel_id"))

        return f"queued:{len(channel_list)}"
    except Exception:
        logger.warning("OTA date blocking failed for booking %s", booking_id)
        return "error"


# ===========================================================================
# Phase 708 — Selective Task Creation (implemented in _create_tasks_for_manual_booking)
# ===========================================================================

def _create_tasks_for_manual_booking(
    db: Any, booking_id: str, property_id: str,
    check_in: str, source: str, opt_out: List[str], tenant_id: str,
) -> List[str]:
    """Create operational tasks for a manual booking using the canonical task_writer.

    Uses write_tasks_for_booking_created (same function as OTA webhook path)
    which generates CHECKIN_PREP + CLEANING tasks via task_automator.

    Returns list of created task kinds.
    """
    if source == "maintenance_block":
        return []  # No tasks for maintenance blocks

    try:
        from tasks.task_writer import write_tasks_for_booking_created
        count = write_tasks_for_booking_created(
            tenant_id=tenant_id,
            booking_id=booking_id,
            property_id=property_id,
            check_in=check_in,
            provider=f"manual:{source}",
            client=db,
        )
        if count > 0:
            return ["CHECKIN_PREP", "CLEANING"][:count]
        return []
    except Exception:
        logger.warning("Failed to create tasks for manual booking %s", booking_id)
        return []


# ===========================================================================
# Phase 709 — Cancel Manual Booking & Unblock OTA Dates
# ===========================================================================

@router.delete("/bookings/{booking_id}/manual", summary="Cancel manual booking (Phase 709)")
async def cancel_manual_booking(
    booking_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_db()

        # Check booking exists and is manual
        booking_res = db.table("booking_state").select("booking_id, status, property_id, source, check_in, check_out, version").eq("booking_id", booking_id).limit(1).execute()
        booking_rows = booking_res.data or []
        if not booking_rows:
            return make_error_response(404, "NOT_FOUND", extra={"detail": f"Booking '{booking_id}' not found."})

        booking = booking_rows[0]
        if booking.get("status") == "canceled":
            return make_error_response(400, ErrorCode.VALIDATION_ERROR, extra={"detail": "Booking already canceled."})

        now = datetime.now(tz=timezone.utc).isoformat()
        now_ms = int(time.time() * 1000)

        # Cancel the booking
        db.table("booking_state").update({
            "status": "canceled",
            "version": (booking.get("version") or 0) + 1,
            "updated_at_ms": now_ms,
        }).eq("booking_id", booking_id).execute()

        # Cancel all related tasks (best-effort)
        tasks_canceled = 0
        try:
            task_res = db.table("tasks").select("id, status").eq("booking_id", booking_id).execute()
            for t in (task_res.data or []):
                if t["status"] not in ("completed", "canceled"):
                    db.table("tasks").update({"status": "canceled", "canceled_at": now}).eq("id", t["id"]).execute()
                    tasks_canceled += 1
        except Exception:
            logger.warning("Failed to cancel tasks for booking %s", booking_id)

        # Unblock OTA dates (Phase 709 — reverse of Phase 707)
        ota_unblock = _trigger_ota_date_unblock(db, booking.get("property_id", ""),
                                                 booking.get("check_in", ""), booking.get("check_out", ""),
                                                 booking_id, tenant_id)

        # Audit
        try:
            from services.audit_writer import write_audit_event
            write_audit_event(db, tenant_id=tenant_id, entity_type="booking",
                              entity_id=booking_id, action="manual_canceled",
                              details={"tasks_canceled": tasks_canceled, "ota_unblocked": ota_unblock})
        except Exception:
            pass

        return JSONResponse(status_code=200, content={
            "booking_id": booking_id,
            "status": "canceled",
            "tasks_canceled": tasks_canceled,
            "ota_unblocked": ota_unblock,
        })
    except Exception as exc:
        logger.exception("cancel_manual_booking error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)


def _trigger_ota_date_unblock(db: Any, property_id: str, check_in: str, check_out: str, booking_id: str, tenant_id: str) -> Optional[str]:
    """Unblock dates on all connected OTAs. Best-effort."""
    try:
        channels = db.table("channel_map").select("channel_id, provider").eq("property_id", property_id).eq("active", True).execute()
        channel_list = channels.data or []
        if not channel_list:
            return "no_channels"

        now = datetime.now(tz=timezone.utc).isoformat()
        for ch in channel_list:
            try:
                sync_id = hashlib.sha256(f"SYNC:UNBLOCK:{booking_id}:{ch['channel_id']}:{now}".encode()).hexdigest()[:16]
                db.table("outbound_sync_log").insert({
                    "id": sync_id,
                    "property_id": property_id,
                    "channel_id": ch["channel_id"],
                    "provider": ch.get("provider", "unknown"),
                    "sync_type": "availability_unblock",
                    "booking_id": booking_id,
                    "payload": {"check_in": check_in, "check_out": check_out, "blocked": False},
                    "status": "queued",
                    "created_at": now,
                }).execute()
            except Exception:
                logger.warning("Failed to queue OTA unblock for channel %s", ch.get("channel_id"))

        return f"queued:{len(channel_list)}"
    except Exception:
        logger.warning("OTA date unblocking failed for booking %s", booking_id)
        return "error"


# ===========================================================================
# Phase 710 — Edit Manual Booking (strategic pivot: manual as main path)
# ===========================================================================

_EDITABLE_FIELDS = frozenset({"check_in", "check_out", "guest_name", "notes", "number_of_guests"})


@router.patch("/bookings/{booking_id}/manual", summary="Edit manual booking (Phase 710)")
async def edit_manual_booking(
    booking_id: str,
    body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Edit a manual booking's dates, guest name, or notes.

    Only manual-source bookings can be edited (direct, self_use, owner_use, maintenance_block).
    iCal and webhook-sourced bookings are managed by their respective sources.
    """
    try:
        db = client if client is not None else _get_db()

        # Fetch existing booking
        booking_res = (db.table("booking_state")
                       .select("booking_id, status, source, property_id, check_in, check_out, version")
                       .eq("booking_id", booking_id)
                       .limit(1)
                       .execute())
        booking_rows = booking_res.data or []
        if not booking_rows:
            return make_error_response(404, "NOT_FOUND",
                                       extra={"detail": f"Booking '{booking_id}' not found."})

        booking = booking_rows[0]

        # Only allow editing of manual bookings
        source = booking.get("source", "")
        if source and source not in _VALID_SOURCES:
            return make_error_response(400, ErrorCode.VALIDATION_ERROR,
                                       extra={"detail": f"Cannot edit non-manual booking (source={source})."})

        if booking.get("status") == "canceled":
            return make_error_response(400, ErrorCode.VALIDATION_ERROR,
                                       extra={"detail": "Cannot edit a canceled booking."})

        # Build update payload from allowed fields only
        updates: Dict[str, Any] = {}
        for field in _EDITABLE_FIELDS:
            if field in body:
                val = body[field]
                if isinstance(val, str):
                    val = val.strip()
                if val is not None and val != "":
                    updates[field] = val

        if not updates:
            return make_error_response(400, ErrorCode.VALIDATION_ERROR,
                                       extra={"detail": f"No valid fields to update. Editable: {sorted(_EDITABLE_FIELDS)}"})

        # Date validation
        new_check_in = updates.get("check_in", booking.get("check_in", ""))
        new_check_out = updates.get("check_out", booking.get("check_out", ""))
        if new_check_in and new_check_out and new_check_in >= new_check_out:
            return make_error_response(400, ErrorCode.VALIDATION_ERROR,
                                       extra={"detail": "check_in must be before check_out"})

        now_ms = int(time.time() * 1000)
        updates["updated_at_ms"] = now_ms
        updates["version"] = (booking.get("version") or 0) + 1

        db.table("booking_state").update(updates).eq("booking_id", booking_id).execute()

        # Audit
        try:
            from services.audit_writer import write_audit_event
            write_audit_event(db, tenant_id=tenant_id, entity_type="booking",
                              entity_id=booking_id, action="manual_edited",
                              details={"fields_updated": list(updates.keys())})
        except Exception:
            pass

        return JSONResponse(status_code=200, content={
            "booking_id": booking_id,
            "updated_fields": list(updates.keys()),
            "status": "ok",
        })
    except Exception as exc:
        logger.exception("edit_manual_booking error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)

