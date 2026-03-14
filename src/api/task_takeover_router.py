"""
Phases 710–712 — Task Take-Over
=================================

710: POST /tasks/{task_id}/take-over — manager takes over task from worker
711: Notification to original worker about take-over
712: Manager gets full task context after take-over

Invariant:
    Only ops_manager or admin can initiate a take-over.
    Original worker's task → status = 'taken_over' (read-only).
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
router = APIRouter(tags=["tasks"])

_VALID_TAKEOVER_REASONS = frozenset({
    "worker_unavailable", "worker_sick", "emergency", "other",
})


def _get_db() -> Any:
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


# ===========================================================================
# Phase 710 — Task Take-Over API
# ===========================================================================

@router.post("/tasks/{task_id}/take-over", summary="Take over task from worker (Phase 710)")
async def take_over_task(
    task_id: str, body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    reason = str(body.get("reason") or "").strip()
    if not reason or reason not in _VALID_TAKEOVER_REASONS:
        return make_error_response(400, ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": f"reason must be one of: {sorted(_VALID_TAKEOVER_REASONS)}"})

    manager_id = str(body.get("manager_id") or tenant_id).strip()
    notes = str(body.get("notes") or "").strip() or None

    try:
        db = client if client is not None else _get_db()

        # Get current task
        task_res = db.table("tasks").select("*").eq("id", task_id).limit(1).execute()
        task_rows = task_res.data or []
        if not task_rows:
            return make_error_response(404, "NOT_FOUND", extra={"detail": f"Task '{task_id}' not found."})

        task = task_rows[0]

        if task.get("status") in ("completed", "canceled", "taken_over"):
            return make_error_response(400, ErrorCode.VALIDATION_ERROR,
                                       extra={"detail": f"Cannot take over task in '{task['status']}' status."})

        original_worker_id = task.get("assigned_to") or task.get("worker_id")
        now = _now_iso()

        # Mark original task as 'taken_over'
        db.table("tasks").update({
            "status": "taken_over",
            "taken_over_at": now,
            "taken_over_by": manager_id,
            "taken_over_reason": reason,
        }).eq("id", task_id).execute()

        # Record action
        action_id = hashlib.sha256(f"TAKEOVER:{task_id}:{now}".encode()).hexdigest()[:16]
        try:
            db.table("task_actions").insert({
                "id": action_id,
                "task_id": task_id,
                "action": "taken_over",
                "performed_by": manager_id,
                "details": {"reason": reason, "original_worker": original_worker_id, "notes": notes},
                "created_at": now,
            }).execute()
        except Exception:
            logger.warning("Failed to record take-over action for task %s", task_id)

        # Phase 711 — Notify original worker (best-effort)
        notification_sent = _notify_worker_of_takeover(db, task, manager_id, reason, tenant_id)

        # Phase 712 — Return full task context for manager
        context = _get_full_task_context(db, task)

        # Audit
        try:
            from services.audit_writer import write_audit_event
            write_audit_event(db, tenant_id=tenant_id, entity_type="task",
                              entity_id=task_id, action="taken_over",
                              details={"reason": reason, "original_worker": original_worker_id,
                                       "manager": manager_id, "notified": notification_sent})
        except Exception:
            pass

        return JSONResponse(status_code=200, content={
            "task_id": task_id,
            "status": "taken_over",
            "taken_over_by": manager_id,
            "reason": reason,
            "original_worker_id": original_worker_id,
            "notification_sent": notification_sent,
            "context": context,
        })
    except Exception as exc:
        logger.exception("take_over_task error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# Phase 711 — Worker Notification on Take-Over
# ===========================================================================

def _notify_worker_of_takeover(
    db: Any, task: Dict[str, Any], manager_id: str, reason: str, tenant_id: str,
) -> bool:
    """Send notification to original worker about take-over. Best-effort."""
    original_worker = task.get("assigned_to") or task.get("worker_id")
    if not original_worker:
        return False

    try:
        task_kind = task.get("task_kind", "Task")
        property_name = task.get("property_name") or task.get("property_id", "")
        message = f"Task '{task_kind} — {property_name}' was taken over by {manager_id}. Reason: {reason}"

        # Queue notification
        now = _now_iso()
        notif_id = hashlib.sha256(f"NOTIF:TAKEOVER:{task['id']}:{now}".encode()).hexdigest()[:16]
        db.table("notification_queue").insert({
            "id": notif_id,
            "recipient_id": original_worker,
            "channel": "auto",  # System picks best channel
            "message": message,
            "notification_type": "task_takeover",
            "reference_type": "task",
            "reference_id": task["id"],
            "tenant_id": tenant_id,
            "status": "queued",
            "created_at": now,
        }).execute()

        # SSE alert
        try:
            from channels.sse_broker import sse_broker
            import asyncio
            asyncio.create_task(sse_broker.publish("TASK_TAKEOVER", {
                "task_id": task["id"], "original_worker": original_worker,
                "manager": manager_id, "reason": reason,
            }, tenant_id=tenant_id))
        except Exception:
            pass

        return True
    except Exception:
        logger.warning("Failed to notify worker %s of take-over", original_worker)
        return False


# ===========================================================================
# Phase 712 — Manager Gets Full Task Context
# ===========================================================================

def _get_full_task_context(db: Any, task: Dict[str, Any]) -> Dict[str, Any]:
    """Return full context that the manager needs to complete the taken-over task."""
    context: Dict[str, Any] = {
        "task_kind": task.get("task_kind"),
        "booking_id": task.get("booking_id"),
        "property_id": task.get("property_id"),
        "priority": task.get("priority"),
        "created_at": task.get("created_at"),
    }

    booking_id = task.get("booking_id")
    property_id = task.get("property_id")

    # Get property details
    if property_id:
        try:
            prop = db.table("properties").select("name, address, latitude, longitude, door_code, notes").eq("property_id", property_id).limit(1).execute()
            if prop.data:
                context["property"] = prop.data[0]
        except Exception:
            pass

    # Get booking + guest info
    if booking_id:
        try:
            bk = db.table("bookings").select("guest_name, check_in, check_out, number_of_guests, status").eq("booking_id", booking_id).limit(1).execute()
            if bk.data:
                context["booking"] = bk.data[0]
        except Exception:
            pass

    # Get reference photos
    if property_id:
        try:
            photos = db.table("property_reference_photos").select("photo_url, room_label, caption").eq("property_id", property_id).execute()
            context["reference_photos"] = photos.data or []
        except Exception:
            pass

    # Get checklist (if cleaning task)
    task_kind = task.get("task_kind", "")
    if "CLEANING" in task_kind.upper():
        try:
            checklist = db.table("cleaning_checklists").select("*").eq("property_id", property_id).execute()
            context["checklist"] = checklist.data or []
        except Exception:
            pass

    return context


# ===========================================================================
# Get task with take-over context (for manager view)
# ===========================================================================

@router.get("/tasks/{task_id}/context", summary="Get full task context (Phase 712)")
async def get_task_context(
    task_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_db()
        task_res = db.table("tasks").select("*").eq("id", task_id).limit(1).execute()
        task_rows = task_res.data or []
        if not task_rows:
            return make_error_response(404, "NOT_FOUND")

        context = _get_full_task_context(db, task_rows[0])
        return JSONResponse(status_code=200, content={"task_id": task_id, "context": context})
    except Exception as exc:
        logger.exception("get_task_context error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)
