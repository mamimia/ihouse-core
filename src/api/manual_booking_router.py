"""
Phase 706 — Manual Booking: Create API
========================================

POST /bookings/manual
    Create a booking from the management dashboard (not OTA).
    Supports booking_source: 'direct', 'self_use', 'owner_use', 'maintenance_block'.
    Returns booking_id in format MAN-{property_short}-{YYYYMMDD}.

Invariant:
    This router writes to booking_state only.
    Financial records are NOT created for manual bookings (no OTA data).
"""
from __future__ import annotations

import hashlib
import logging
import os
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

    row = {
        "booking_id": booking_id,
        "tenant_id": tenant_id,
        "property_id": property_id,
        "check_in": check_in,
        "check_out": check_out,
        "guest_name": guest_name or f"[{booking_source}]",
        "status": "confirmed",
        "source": booking_source,
        "number_of_guests": number_of_guests,
        "notes": notes,
        "tasks_opt_out": tasks_opt_out,
        "created_by": tenant_id,
        "created_at": now,
    }

    try:
        db = client if client is not None else _get_db()
        result = db.table("bookings").insert(row).execute()
        rows = result.data or []
        if not rows:
            return make_error_response(500, ErrorCode.INTERNAL_ERROR)

        booking = rows[0]

        # Auto-create tasks based on source and opt-outs (best-effort)
        tasks_created = _create_tasks_for_manual_booking(db, booking_id, property_id, booking_source, tasks_opt_out, tenant_id)

        # Audit
        try:
            from services.audit_writer import write_audit_event
            write_audit_event(db, tenant_id=tenant_id, entity_type="booking",
                              entity_id=booking_id, action="manual_created",
                              details={"source": booking_source, "tasks_opt_out": tasks_opt_out,
                                       "tasks_created": tasks_created})
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
        })
    except Exception as exc:
        logger.exception("create_manual_booking error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)


def _create_tasks_for_manual_booking(
    db: Any, booking_id: str, property_id: str,
    source: str, opt_out: List[str], tenant_id: str,
) -> List[str]:
    """Create tasks based on booking source and opt-outs. Returns list of created task kinds."""
    if source == "maintenance_block":
        return []  # No tasks for maintenance blocks

    all_tasks = ["checkin", "cleaning", "checkout"]
    if source in ("self_use", "owner_use"):
        tasks_to_create = [t for t in all_tasks if t not in opt_out]
    else:  # direct
        tasks_to_create = all_tasks  # Always create all

    created = []
    for task_kind in tasks_to_create:
        try:
            from tasks.task_model import Task
            from tasks.task_automator import create_task_if_needed
            kind_map = {"checkin": "CHECKIN_PREP", "cleaning": "CLEANING", "checkout": "CHECKOUT_VERIFY"}
            task = Task.build(
                task_kind=kind_map.get(task_kind, task_kind.upper()),
                booking_id=booking_id,
                property_id=property_id,
                priority="MEDIUM",
                ack_sla_minutes=60,
            )
            create_task_if_needed(db, task, tenant_id=tenant_id)
            created.append(task_kind)
        except Exception:
            logger.warning("Failed to create %s task for manual booking %s", task_kind, booking_id)

    return created
