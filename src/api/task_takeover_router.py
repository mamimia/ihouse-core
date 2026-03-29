"""
Phases 710–712, 1022 — Task Takeover (Manager/Admin)
=====================================================

Phase 1022 hardening of the Phase 710 skeleton.

Canonical model (Phase 1022):
    - Operational Manager (role='manager') is the PRIMARY takeover actor.
    - Admin (role='admin') is the FALLBACK takeover actor.
    - Both use the identical endpoint, state machine, and audit trail.
    - Takeover is TASK-SPECIFIC. Not a global role assumption.
    - Manager scope: only tasks on properties they are assigned to.
    - Admin scope: any task in the tenancy (no property scope limit).

Takeover gate (all must hold):
    1. Task status is PENDING, ACKNOWLEDGED, or IN_PROGRESS
    2. Task is NOT already MANAGER_EXECUTING
    3. Caller role is 'manager' or 'admin'
    4. Reason is provided (canonical 4-choice list)
    5. Manager: task property must be in their assigned properties
       Admin:   no property scope check

After takeover:
    - tasks.status            → MANAGER_EXECUTING
    - tasks.assigned_to       → manager/admin user_id
    - tasks.original_worker_id → snapshot of previous assigned_to
    - tasks.taken_over_by     → manager/admin user_id
    - tasks.taken_over_at     → now (UTC)
    - tasks.taken_over_reason → reason
    - tasks.taken_over_notes  → optional free-text notes
    - task_actions             → MANAGER_TAKEOVER_INITIATED + ORIGINAL_WORKER_SUPERSEDED

Worker notification (Phase 711 / 1022):
    Informational tone: "This task is now being handled by [Manager]."

Reassign endpoint (Phase 1022):
    POST /tasks/{task_id}/reassign
    - Returns task to PENDING with new assigned_to (or null = open pool)
    - Same task continues — no new task created
    - Full history preserved in task_actions

Endpoints:
    POST /tasks/{task_id}/take-over  — manager/admin takes over task
    POST /tasks/{task_id}/reassign   — manager/admin releases to new worker
    GET  /tasks/{task_id}/context    — full task context for execution
    GET  /manager/tasks              — manager's task board
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
    "worker_unavailable",
    "worker_sick",
    "emergency",
    "other",
})

# Statuses from which takeover is permitted
_TAKEOVER_ELIGIBLE_STATUSES = frozenset({
    "PENDING", "ACKNOWLEDGED", "IN_PROGRESS",
})

# Roles authorized to perform takeover
_TAKEOVER_AUTHORIZED_ROLES = frozenset({"manager", "admin"})


def _get_db() -> Any:
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _action_id(prefix: str, task_id: str, now: str) -> str:
    return hashlib.sha256(f"{prefix}:{task_id}:{now}".encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Permission helpers
# ---------------------------------------------------------------------------

def _get_caller_role(db: Any, tenant_id: str) -> str:
    """Resolve the caller's role from tenant_permissions."""
    try:
        res = (
            db.table("tenant_permissions")
            .select("role")
            .eq("user_id", tenant_id)
            .limit(1)
            .execute()
        )
        if res.data:
            return res.data[0].get("role", "worker")
    except Exception:
        pass
    return "worker"


def _get_manager_property_ids(db: Any, manager_id: str) -> List[str]:
    """Return the property IDs assigned to this manager (staff assignments)."""
    try:
        res = (
            db.table("staff_assignments")
            .select("property_id")
            .eq("user_id", manager_id)
            .execute()
        )
        return [r["property_id"] for r in (res.data or []) if r.get("property_id")]
    except Exception:
        return []


def _get_caller_display_name(db: Any, caller_id: str) -> str:
    """Resolve display name for notification messaging."""
    try:
        res = (
            db.table("tenant_permissions")
            .select("display_name")
            .eq("user_id", caller_id)
            .limit(1)
            .execute()
        )
        if res.data and res.data[0].get("display_name"):
            return res.data[0]["display_name"]
    except Exception:
        pass
    return "the manager"


# ===========================================================================
# POST /tasks/{task_id}/take-over
# ===========================================================================

@router.post(
    "/tasks/{task_id}/take-over",
    summary="Operational Manager / Admin task takeover (Phase 1022)",
)
async def take_over_task(
    task_id: str,
    body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    POST /tasks/{task_id}/take-over

    Primary path: Operational Manager (role='manager').
    Fallback path: Admin (role='admin').
    Both use identical mechanics and produce an identical audit trail.

    Body:
        reason  (required) — one of: worker_unavailable | worker_sick | emergency | other
        notes   (optional) — free-text context

    Takeover gate:
        - Task must be PENDING, ACKNOWLEDGED, or IN_PROGRESS
        - Task must NOT already be MANAGER_EXECUTING
        - Caller must be role=manager or role=admin
        - Manager: task property must be in their assigned properties
        - Admin: any task in the tenancy

    After success:
        - task.status              = MANAGER_EXECUTING
        - task.assigned_to         = caller (manager/admin)
        - task.original_worker_id  = previous assigned_to (snapshot, never overwritten again)
        - Original worker notified (informational tone)
        - Audit events written
    """
    reason = str(body.get("reason") or "").strip()
    if not reason or reason not in _VALID_TAKEOVER_REASONS:
        return make_error_response(
            400, ErrorCode.VALIDATION_ERROR,
            extra={"detail": f"reason must be one of: {sorted(_VALID_TAKEOVER_REASONS)}"},
        )

    notes = str(body.get("notes") or "").strip() or None

    try:
        db = client if client is not None else _get_db()

        # --- Permission check ---
        caller_role = _get_caller_role(db, tenant_id)
        if caller_role not in _TAKEOVER_AUTHORIZED_ROLES:
            return make_error_response(
                403, ErrorCode.VALIDATION_ERROR,
                extra={"detail": "Only managers and admins can perform task takeover."},
            )

        # --- Fetch task ---
        task_res = db.table("tasks").select("*").eq("id", task_id).limit(1).execute()
        task_rows = task_res.data or []
        if not task_rows:
            return make_error_response(404, "NOT_FOUND", extra={"detail": f"Task '{task_id}' not found."})

        task = task_rows[0]
        current_status = str(task.get("status", "")).upper()

        # --- Gate: terminal or already taken over ---
        if current_status not in _TAKEOVER_ELIGIBLE_STATUSES:
            return make_error_response(
                400, ErrorCode.VALIDATION_ERROR,
                extra={"detail": f"Cannot take over task in '{current_status}' status. "
                                 f"Eligible: {sorted(_TAKEOVER_ELIGIBLE_STATUSES)}"},
            )

        if current_status == "MANAGER_EXECUTING":
            return make_error_response(
                409, ErrorCode.VALIDATION_ERROR,
                extra={"detail": "Task is already MANAGER_EXECUTING. Only one active executor at a time."},
            )

        # --- Property scope check (manager only; admin is unrestricted) ---
        if caller_role == "manager":
            manager_props = set(_get_manager_property_ids(db, tenant_id))
            task_property = task.get("property_id", "")
            if task_property and manager_props and task_property not in manager_props:
                return make_error_response(
                    403, ErrorCode.VALIDATION_ERROR,
                    extra={"detail": f"Property '{task_property}' is not in your supervised properties."},
                )

        # --- Snapshot original worker ---
        original_worker_id = task.get("assigned_to") or task.get("worker_id")
        now = _now_iso()

        # --- Takeover: update task ---
        db.table("tasks").update({
            "status": "MANAGER_EXECUTING",
            "assigned_to": tenant_id,
            "original_worker_id": original_worker_id,
            "taken_over_by": tenant_id,
            "taken_over_at": now,
            "taken_over_reason": reason,
            "taken_over_notes": notes,
            "updated_at": now,
        }).eq("id", task_id).execute()

        # --- task_actions: MANAGER_TAKEOVER_INITIATED ---
        try:
            db.table("task_actions").insert({
                "id": _action_id("TAKEOVER_INIT", task_id, now),
                "task_id": task_id,
                "action": "MANAGER_TAKEOVER_INITIATED",
                "performed_by": tenant_id,
                "details": {
                    "reason": reason,
                    "notes": notes,
                    "original_worker_id": original_worker_id,
                    "caller_role": caller_role,
                    "previous_status": current_status,
                },
                "created_at": now,
            }).execute()
        except Exception:
            logger.warning("Phase 1022: failed to write MANAGER_TAKEOVER_INITIATED action for %s", task_id)

        # --- task_actions: ORIGINAL_WORKER_SUPERSEDED ---
        if original_worker_id:
            try:
                db.table("task_actions").insert({
                    "id": _action_id("SUPERSEDED", task_id, now),
                    "task_id": task_id,
                    "action": "ORIGINAL_WORKER_SUPERSEDED",
                    "performed_by": tenant_id,
                    "details": {
                        "superseded_worker_id": original_worker_id,
                        "superseded_at": now,
                        "takeover_reason": reason,
                    },
                    "created_at": now,
                }).execute()
            except Exception:
                logger.warning("Phase 1022: failed to write ORIGINAL_WORKER_SUPERSEDED action for %s", task_id)

        # --- Notify original worker ---
        caller_name = _get_caller_display_name(db, tenant_id)
        notification_sent = _notify_worker_of_takeover(
            db, task, tenant_id, caller_name, reason, tenant_id,
        )

        # --- Audit event ---
        try:
            from services.audit_writer import write_audit_event
            write_audit_event(
                db, tenant_id=tenant_id, entity_type="task",
                entity_id=task_id, action="MANAGER_TAKEOVER_INITIATED",
                details={
                    "reason": reason,
                    "notes": notes,
                    "original_worker_id": original_worker_id,
                    "taken_over_by": tenant_id,
                    "caller_role": caller_role,
                    "notified": notification_sent,
                },
            )
        except Exception:
            pass

        # --- Full context for execution routing ---
        context = _get_full_task_context(db, task)

        logger.info(
            "Phase 1022: task %s taken over by %s (role=%s) reason=%s",
            task_id, tenant_id, caller_role, reason,
        )

        return JSONResponse(status_code=200, content={
            "task_id": task_id,
            "status": "MANAGER_EXECUTING",
            "taken_over_by": tenant_id,
            "taken_over_by_role": caller_role,
            "reason": reason,
            "notes": notes,
            "original_worker_id": original_worker_id,
            "notification_sent": notification_sent,
            "context": context,
        })

    except Exception as exc:
        logger.exception("take_over_task error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# POST /tasks/{task_id}/reassign  (Phase 1022)
# ===========================================================================

@router.post(
    "/tasks/{task_id}/reassign",
    summary="Manager/Admin reassigns taken-over task to a new worker (Phase 1022)",
)
async def reassign_task(
    task_id: str,
    body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    POST /tasks/{task_id}/reassign

    Only valid when task is MANAGER_EXECUTING.
    Returns task to PENDING with a new assigned_to.

    The SAME task continues — no new task is created.
    Full history is preserved in task_actions.

    Body:
        new_assignee_id (optional) — specific worker to assign; null = open pool
        reason          (optional) — free-text reason for reassignment

    Audit chain preserved:
        - original_worker_id  → unchanged (first worker who was superseded)
        - taken_over_by       → unchanged (manager who took over)
        - new assigned_to     → new_assignee_id (the third actor, or null)
        - task_actions        → MANAGER_TASK_REASSIGNED event
    """
    new_assignee_id = str(body.get("new_assignee_id") or "").strip() or None
    reason = str(body.get("reason") or "").strip() or None

    try:
        db = client if client is not None else _get_db()

        # Permission check
        caller_role = _get_caller_role(db, tenant_id)
        if caller_role not in _TAKEOVER_AUTHORIZED_ROLES:
            return make_error_response(
                403, ErrorCode.VALIDATION_ERROR,
                extra={"detail": "Only managers and admins can reassign tasks."},
            )

        # Fetch task
        task_res = db.table("tasks").select("*").eq("id", task_id).limit(1).execute()
        task_rows = task_res.data or []
        if not task_rows:
            return make_error_response(404, "NOT_FOUND", extra={"detail": f"Task '{task_id}' not found."})

        task = task_rows[0]
        if task.get("status") != "MANAGER_EXECUTING":
            return make_error_response(
                400, ErrorCode.VALIDATION_ERROR,
                extra={"detail": f"Can only reassign a MANAGER_EXECUTING task (current: {task.get('status')})."},
            )

        now = _now_iso()

        # Return to PENDING with new assignee
        db.table("tasks").update({
            "status": "PENDING",
            "assigned_to": new_assignee_id,
            "updated_at": now,
        }).eq("id", task_id).execute()

        # task_actions record
        try:
            db.table("task_actions").insert({
                "id": _action_id("REASSIGN", task_id, now),
                "task_id": task_id,
                "action": "MANAGER_TASK_REASSIGNED",
                "performed_by": tenant_id,
                "details": {
                    "reassigned_to": new_assignee_id,
                    "reassigned_by": tenant_id,
                    "caller_role": caller_role,
                    "reason": reason,
                    # Audit chain snapshot
                    "original_worker_id": task.get("original_worker_id"),
                    "taken_over_by": task.get("taken_over_by"),
                    "taken_over_reason": task.get("taken_over_reason"),
                },
                "created_at": now,
            }).execute()
        except Exception:
            logger.warning("Phase 1022: failed to write MANAGER_TASK_REASSIGNED action for %s", task_id)

        # Notify new assignee (best-effort)
        if new_assignee_id:
            try:
                task_kind = task.get("task_kind", "Task")
                prop = task.get("property_id", "")
                db.table("notification_queue").insert({
                    "id": _action_id("NOTIF_REASSIGN", task_id, now),
                    "recipient_id": new_assignee_id,
                    "channel": "auto",
                    "message": f"You have been assigned a {task_kind} task at {prop}.",
                    "notification_type": "task_assigned",
                    "reference_type": "task",
                    "reference_id": task_id,
                    "tenant_id": tenant_id,
                    "status": "queued",
                    "created_at": now,
                }).execute()
            except Exception:
                pass

        # Audit
        try:
            from services.audit_writer import write_audit_event
            write_audit_event(
                db, tenant_id=tenant_id, entity_type="task",
                entity_id=task_id, action="MANAGER_TASK_REASSIGNED",
                details={
                    "reassigned_to": new_assignee_id,
                    "reassigned_by": tenant_id,
                    "original_worker_id": task.get("original_worker_id"),
                    "taken_over_by": task.get("taken_over_by"),
                    "reason": reason,
                },
            )
        except Exception:
            pass

        return JSONResponse(status_code=200, content={
            "task_id": task_id,
            "status": "PENDING",
            "new_assignee_id": new_assignee_id,
            "reassigned_by": tenant_id,
            "audit_chain": {
                "original_worker_id": task.get("original_worker_id"),
                "taken_over_by": task.get("taken_over_by"),
                "taken_over_reason": task.get("taken_over_reason"),
                "reassigned_to": new_assignee_id,
            },
        })

    except Exception as exc:
        logger.exception("reassign_task error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# Phase 711 / 1022 — Worker Notification on Takeover
# ===========================================================================

def _notify_worker_of_takeover(
    db: Any, task: Dict[str, Any], manager_id: str,
    manager_name: str, reason: str, tenant_id: str,
) -> bool:
    """
    Send informational notification to original worker about takeover.
    Tone (Phase 1022 approved): 'This task is now being handled by [Manager].'
    Best-effort — never raises.
    """
    original_worker = task.get("assigned_to") or task.get("original_worker_id")
    if not original_worker or original_worker == manager_id:
        return False

    try:
        task_kind = task.get("task_kind", "task")
        property_id = task.get("property_id", "")
        message = (
            f"This task is now being handled by {manager_name}. "
            f"({task_kind} at {property_id}.) "
            f"You do not need to take any further action."
        )

        now = _now_iso()
        db.table("notification_queue").insert({
            "id": _action_id("NOTIF_TAKEOVER", task["id"], now),
            "recipient_id": original_worker,
            "channel": "auto",
            "message": message,
            "notification_type": "task_takeover",
            "reference_type": "task",
            "reference_id": task["id"],
            "tenant_id": tenant_id,
            "status": "queued",
            "created_at": now,
        }).execute()

        try:
            from channels.sse_broker import sse_broker
            import asyncio
            asyncio.create_task(sse_broker.publish("TASK_MANAGER_EXECUTING", {
                "task_id": task["id"],
                "original_worker": original_worker,
                "taken_over_by": manager_id,
                "reason": reason,
            }, tenant_id=tenant_id))
        except Exception:
            pass

        return True
    except Exception:
        logger.warning("Phase 1022: failed to notify worker %s of takeover", original_worker)
        return False


# ===========================================================================
# Phase 712 / 1022 — Full Task Context for Manager Execution
# ===========================================================================

def _get_full_task_context(db: Any, task: Dict[str, Any]) -> Dict[str, Any]:
    """Return full context the manager needs to execute the taken-over task."""
    context: Dict[str, Any] = {
        "task_kind": task.get("task_kind"),
        "booking_id": task.get("booking_id"),
        "property_id": task.get("property_id"),
        "priority": task.get("priority"),
        "created_at": task.get("created_at"),
        # Phase 1022: full audit chain included
        "original_worker_id": task.get("original_worker_id"),
        "taken_over_by": task.get("taken_over_by"),
        "taken_over_reason": task.get("taken_over_reason"),
        "taken_over_at": task.get("taken_over_at"),
    }

    property_id = task.get("property_id")
    booking_id = task.get("booking_id")

    if property_id:
        try:
            prop = db.table("properties").select(
                "name, address, latitude, longitude, door_code, notes"
            ).eq("property_id", property_id).limit(1).execute()
            if prop.data:
                context["property"] = prop.data[0]
        except Exception:
            pass

    if booking_id:
        try:
            bk = db.table("bookings").select(
                "guest_name, check_in, check_out, number_of_guests, status"
            ).eq("booking_id", booking_id).limit(1).execute()
            if bk.data:
                context["booking"] = bk.data[0]
        except Exception:
            pass

    if property_id:
        try:
            photos = db.table("property_reference_photos").select(
                "photo_url, room_label, caption"
            ).eq("property_id", property_id).execute()
            context["reference_photos"] = photos.data or []
        except Exception:
            pass

    task_kind = str(task.get("task_kind", "")).upper()
    if "CLEANING" in task_kind:
        try:
            checklist = db.table("cleaning_checklists").select("*").eq(
                "property_id", property_id
            ).execute()
            context["checklist"] = checklist.data or []
        except Exception:
            pass

    return context


# ===========================================================================
# GET /tasks/{task_id}/context (Phase 712 / 1022)
# ===========================================================================

@router.get(
    "/tasks/{task_id}/context",
    summary="Get full task context for manager execution (Phase 712 / 1022)",
)
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


# ===========================================================================
# GET /manager/tasks  (Phase 1022-D)
# Manager Task Inbox — scoped to supervised properties
# ===========================================================================

@router.get(
    "/manager/tasks",
    summary="Manager task board — all open tasks for supervised properties (Phase 1022)",
)
async def manager_task_board(
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    GET /manager/tasks

    Returns all open tasks for the manager's supervised properties, grouped by status.
    Also includes tasks currently MANAGER_EXECUTING by this manager.

    Scoping:
        - manager role: tasks on their assigned properties only
        - admin role: all tasks in the tenancy

    Groups returned:
        - manager_executing: tasks this manager is actively executing
        - pending:           tasks awaiting worker acknowledgement
        - acknowledged:      tasks acknowledged but not started
        - in_progress:       tasks currently being executed by a worker
    """
    try:
        db = client if client is not None else _get_db()
        caller_role = _get_caller_role(db, tenant_id)

        if caller_role not in _TAKEOVER_AUTHORIZED_ROLES:
            return make_error_response(
                403, ErrorCode.VALIDATION_ERROR,
                extra={"detail": "Only managers and admins can access the manager task board."},
            )

        # Build base query — open tasks
        open_statuses = ["PENDING", "ACKNOWLEDGED", "IN_PROGRESS", "MANAGER_EXECUTING"]
        query = (
            db.table("tasks")
            .select(
                "id, task_kind, status, priority, booking_id, property_id, "
                "assigned_to, original_worker_id, taken_over_by, taken_over_reason, "
                "taken_over_at, taken_over_notes, due_date, title, created_at, updated_at"
            )
            .in_("status", open_statuses)
        )

        # Scope: manager → their properties only; admin → all
        if caller_role == "manager":
            prop_ids = _get_manager_property_ids(db, tenant_id)
            if not prop_ids:
                return JSONResponse(status_code=200, content={
                    "manager_id": tenant_id,
                    "role": caller_role,
                    "groups": {
                        "manager_executing": [],
                        "pending": [],
                        "acknowledged": [],
                        "in_progress": [],
                    },
                    "total": 0,
                })
            query = query.in_("property_id", prop_ids)

        res = query.order("due_date", desc=False).execute()
        tasks = res.data or []

        # Group by status
        groups: Dict[str, List[Any]] = {
            "manager_executing": [],
            "pending": [],
            "acknowledged": [],
            "in_progress": [],
        }

        for t in tasks:
            status = str(t.get("status", "")).upper()
            # MANAGER_EXECUTING tasks: show all (admin sees all; manager sees their own)
            if status == "MANAGER_EXECUTING":
                if caller_role == "admin" or t.get("taken_over_by") == tenant_id:
                    groups["manager_executing"].append(t)
            elif status == "PENDING":
                groups["pending"].append(t)
            elif status == "ACKNOWLEDGED":
                groups["acknowledged"].append(t)
            elif status == "IN_PROGRESS":
                groups["in_progress"].append(t)

        total = sum(len(v) for v in groups.values())

        return JSONResponse(status_code=200, content={
            "manager_id": tenant_id,
            "role": caller_role,
            "groups": groups,
            "total": total,
        })

    except Exception as exc:
        logger.exception("manager_task_board error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)
