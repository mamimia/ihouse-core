"""
Phases 710–712, 1022, 1033 — Task Takeover & Management (Manager/Admin)
=======================================================================

Phase 1022 hardening of the Phase 710 skeleton.
Phase 1033 expansion: Task notes, manager alerts, team overview, and flexible reassign.

Canonical model (Phase 1022/1033):
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

Reassign endpoint (Phase 1022/1033):
    POST /tasks/{task_id}/reassign
    - Returns task to PENDING with new assigned_to (or null = open pool)
    - Works on any in-flight status (including MANAGER_EXECUTING)
    - Same task continues — no new task created
    - Full history preserved in task_actions

Endpoints:
    POST /tasks/{task_id}/take-over  — manager/admin takes over task
    POST /tasks/{task_id}/reassign   — manager/admin releases to new worker
    POST /tasks/{task_id}/notes      — add manager-specific notes
    GET  /tasks/{task_id}/context    — full task context for execution
    GET  /manager/tasks              — manager's task board
    GET  /manager/alerts             — manager-specific task alerts
    GET  /manager/team-overview      — status of all workers/tasks
"""
from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth, jwt_identity
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
        # Phase 1033: reassign works on any active in-flight status
        # (PENDING / ACKNOWLEDGED / IN_PROGRESS / MANAGER_EXECUTING)
        _REASSIGN_ELIGIBLE = frozenset({"PENDING", "ACKNOWLEDGED", "IN_PROGRESS", "MANAGER_EXECUTING"})
        if task.get("status") not in _REASSIGN_ELIGIBLE:
            return make_error_response(
                400, ErrorCode.VALIDATION_ERROR,
                extra={"detail": f"Can only reassign an active task (current: {task.get('status')})."},
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
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    GET /manager/tasks

    Returns all open tasks for the manager's supervised properties, grouped by status.
    Also includes tasks currently MANAGER_EXECUTING by this manager.

    Phase 1033 fix: uses jwt_identity (not jwt_auth) so that:
      - Preview As (X-Preview-Role: manager) correctly resolves role='manager'
      - Act As tokens (token_type=act_as, role=manager) correctly resolve role='manager'
      - No secondary DB lookup for role — the auth layer already resolved it

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

        # Role comes directly from the auth layer (preview overlay + act_as already applied)
        caller_role = str(identity.get("role", "worker")).strip()
        # For DB scoping, use user_id (the actual user UUID, = JWT sub)
        caller_user_id = str(identity.get("user_id") or identity.get("tenant_id", "")).strip()

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
            prop_ids = _get_manager_property_ids(db, caller_user_id)
            if not prop_ids:
                return JSONResponse(status_code=200, content={
                    "manager_id": caller_user_id,
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
                if caller_role == "admin" or t.get("taken_over_by") == caller_user_id:
                    groups["manager_executing"].append(t)
            elif status == "PENDING":
                groups["pending"].append(t)
            elif status == "ACKNOWLEDGED":
                groups["acknowledged"].append(t)
            elif status == "IN_PROGRESS":
                groups["in_progress"].append(t)

        total = sum(len(v) for v in groups.values())

        return JSONResponse(status_code=200, content={
            "manager_id": caller_user_id,
            "role": caller_role,
            "groups": groups,
            "total": total,
        })

    except Exception as exc:
        logger.exception("manager_task_board error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# Phase 1033 — POST /tasks/{task_id}/notes
# Operational note on a task (overlay, not booking core)
# ===========================================================================

@router.post(
    "/tasks/{task_id}/notes",
    summary="Add an operational note to a task (Phase 1033)",
)
async def add_task_note(
    task_id: str,
    body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    POST /tasks/{task_id}/notes

    Adds an operational note to a task. Notes are stored in task_actions
    with action=OPERATIONAL_NOTE and are visible to managers and admins.
    Workers do NOT receive a notification for notes.

    Body:
        note  (required) — free-text operational note
    """
    note = str(body.get("note") or "").strip()
    if not note:
        return make_error_response(
            400, ErrorCode.VALIDATION_ERROR,
            extra={"detail": "'note' is required."},
        )

    try:
        db = client if client is not None else _get_db()
        caller_role = _get_caller_role(db, tenant_id)
        if caller_role not in _TAKEOVER_AUTHORIZED_ROLES:
            return make_error_response(
                403, ErrorCode.VALIDATION_ERROR,
                extra={"detail": "Only managers and admins can add task notes."},
            )

        # Verify task exists and belongs to supervised properties (manager scope)
        task_res = db.table("tasks").select("id, status, property_id").eq("id", task_id).limit(1).execute()
        task_rows = task_res.data or []
        if not task_rows:
            return make_error_response(404, "NOT_FOUND", extra={"detail": f"Task '{task_id}' not found."})

        task = task_rows[0]
        if caller_role == "manager":
            prop_ids = _get_manager_property_ids(db, tenant_id)
            if task.get("property_id") not in prop_ids:
                return make_error_response(
                    403, ErrorCode.VALIDATION_ERROR,
                    extra={"detail": "Task does not belong to a supervised property."},
                )

        now = _now_iso()
        note_id = _action_id("NOTE", task_id, now)

        db.table("task_actions").insert({
            "id": note_id,
            "task_id": task_id,
            "action": "OPERATIONAL_NOTE",
            "performed_by": tenant_id,
            "details": {
                "note": note,
                "added_by": tenant_id,
                "caller_role": caller_role,
            },
            "created_at": now,
        }).execute()

        return JSONResponse(status_code=201, content={
            "note_id": note_id,
            "task_id": task_id,
            "note": note,
            "added_by": tenant_id,
            "created_at": now,
        })

    except Exception as exc:
        logger.exception("add_task_note error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# Phase 1033 — GET /manager/alerts
# Alert stream: critical/overdue tasks and coverage gaps
# ===========================================================================

@router.get(
    "/manager/alerts",
    summary="Manager alert stream — overdue critical tasks + coverage gaps (Phase 1033)",
)
async def manager_alerts(
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    GET /manager/alerts

    Returns alerts for the manager's supervised properties:
    - CRITICAL tasks that are overdue (due_date < now, status not COMPLETED/CANCELED)
    - HIGH priority tasks overdue
    - Tasks that are PENDING and have no assigned_to (open pool / uncovered)
    - Properties with no Primary worker in a lane (coverage gap)

    Scoping: manager → supervised properties; admin → all.
    """
    try:
        db = client if client is not None else _get_db()
        caller_role = _get_caller_role(db, tenant_id)

        if caller_role not in _TAKEOVER_AUTHORIZED_ROLES:
            return make_error_response(
                403, ErrorCode.VALIDATION_ERROR,
                extra={"detail": "Only managers and admins can view alerts."},
            )

        prop_ids: Optional[List[str]] = None
        if caller_role == "manager":
            prop_ids = _get_manager_property_ids(db, tenant_id)

        now_str = _now_iso()
        alerts: List[Dict[str, Any]] = []

        # ── Overdue CRITICAL tasks ───────────────────────────────────────
        try:
            q = (
                db.table("tasks")
                .select("id, task_kind, status, priority, property_id, assigned_to, due_date, title")
                .in_("status", ["PENDING", "ACKNOWLEDGED", "IN_PROGRESS", "MANAGER_EXECUTING"])
                .eq("priority", "CRITICAL")
                .lt("due_date", now_str)
            )
            if prop_ids is not None:
                q = q.in_("property_id", prop_ids)
            overdue_critical = (q.order("due_date", desc=False).limit(50).execute()).data or []
            for t in overdue_critical:
                alerts.append({
                    "type": "OVERDUE_CRITICAL",
                    "severity": "critical",
                    "task_id": t["id"],
                    "title": t.get("title") or t.get("task_kind"),
                    "property_id": t.get("property_id"),
                    "status": t.get("status"),
                    "due_date": t.get("due_date"),
                    "assigned_to": t.get("assigned_to"),
                })
        except Exception:
            pass

        # ── Overdue HIGH tasks ───────────────────────────────────────────
        try:
            q = (
                db.table("tasks")
                .select("id, task_kind, status, priority, property_id, assigned_to, due_date, title")
                .in_("status", ["PENDING", "ACKNOWLEDGED", "IN_PROGRESS"])
                .eq("priority", "HIGH")
                .lt("due_date", now_str)
            )
            if prop_ids is not None:
                q = q.in_("property_id", prop_ids)
            overdue_high = (q.order("due_date", desc=False).limit(30).execute()).data or []
            for t in overdue_high:
                alerts.append({
                    "type": "OVERDUE_HIGH",
                    "severity": "high",
                    "task_id": t["id"],
                    "title": t.get("title") or t.get("task_kind"),
                    "property_id": t.get("property_id"),
                    "status": t.get("status"),
                    "due_date": t.get("due_date"),
                    "assigned_to": t.get("assigned_to"),
                })
        except Exception:
            pass

        # ── PENDING tasks with no assigned_to (uncovered) ───────────────
        try:
            q = (
                db.table("tasks")
                .select("id, task_kind, status, priority, property_id, due_date, title")
                .eq("status", "PENDING")
                .is_("assigned_to", "null")
            )
            if prop_ids is not None:
                q = q.in_("property_id", prop_ids)
            uncovered = (q.order("due_date", desc=False).limit(20).execute()).data or []
            for t in uncovered:
                alerts.append({
                    "type": "TASK_UNCOVERED",
                    "severity": "warning",
                    "task_id": t["id"],
                    "title": t.get("title") or t.get("task_kind"),
                    "property_id": t.get("property_id"),
                    "status": t.get("status"),
                    "due_date": t.get("due_date"),
                    "assigned_to": None,
                })
        except Exception:
            pass

        # ── Coverage gaps: properties with no priority=1 in a lane ──────
        try:
            lanes = ["CLEANING", "MAINTENANCE", "CHECKIN_CHECKOUT"]
            q_assignments = db.table("staff_assignments").select(
                "property_id, operational_lane, priority"
            )
            if prop_ids is not None:
                q_assignments = q_assignments.in_("property_id", prop_ids)
            all_assignments = (q_assignments.execute()).data or []

            # Build: {(property_id, lane)} → min priority
            min_prio: Dict[tuple, int] = {}
            for row in all_assignments:
                key = (row["property_id"], row.get("operational_lane"))
                cur = min_prio.get(key, 9999)
                min_prio[key] = min(cur, row.get("priority") or 9999)

            # Properties in scope
            scope_props = prop_ids or list({r["property_id"] for r in all_assignments})
            for p in scope_props:
                for lane in lanes:
                    key = (p, lane)
                    if min_prio.get(key, 9999) > 1:
                        alerts.append({
                            "type": "COVERAGE_GAP",
                            "severity": "warning",
                            "property_id": p,
                            "lane": lane,
                            "detail": f"No Primary worker (priority=1) for {lane} lane on {p}.",
                        })
        except Exception:
            pass

        return JSONResponse(status_code=200, content={
            "manager_id": tenant_id,
            "role": caller_role,
            "alert_count": len(alerts),
            "alerts": alerts,
        })

    except Exception as exc:
        logger.exception("manager_alerts error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# Phase 1033 — GET /manager/team
# Team overview: workers, task load, coverage gaps per property+lane
# ===========================================================================

@router.get(
    "/manager/team",
    summary="Manager team overview — worker load + coverage gaps (Phase 1033)",
)
async def manager_team(
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    GET /manager/team

    Returns for each supervised property:
    - All assigned workers with their Primary/Backup designation per lane
    - Each worker's current task status (how many PENDING/IN_PROGRESS tasks)
    - Contact info from comm_preference
    - Coverage gaps (missing Primary in a lane)

    Scoping: manager → supervised properties; admin → all.
    """
    try:
        db = client if client is not None else _get_db()
        caller_role = _get_caller_role(db, tenant_id)

        if caller_role not in _TAKEOVER_AUTHORIZED_ROLES:
            return make_error_response(
                403, ErrorCode.VALIDATION_ERROR,
                extra={"detail": "Only managers and admins can view team overview."},
            )

        prop_ids: Optional[List[str]] = None
        if caller_role == "manager":
            prop_ids = _get_manager_property_ids(db, tenant_id)

        # ── Fetch all assignments in scope ───────────────────────────────
        q_assignments = db.table("staff_assignments").select(
            "user_id, property_id, operational_lane, priority"
        )
        if prop_ids is not None:
            q_assignments = q_assignments.in_("property_id", prop_ids)
        all_assignments = (q_assignments.execute()).data or []

        if not all_assignments and prop_ids is not None and len(prop_ids) == 0:
            return JSONResponse(status_code=200, content={
                "manager_id": tenant_id,
                "role": caller_role,
                "properties": [],
                "total_workers": 0,
            })

        # Collect unique worker IDs
        worker_ids = list({r["user_id"] for r in all_assignments if r.get("user_id")})
        scope_props = list({r["property_id"] for r in all_assignments if r.get("property_id")})

        # ── Fetch worker permission records (display_name, comm_preference, role) ─
        worker_data: Dict[str, Dict] = {}
        if worker_ids:
            try:
                perm_res = (
                    db.table("tenant_permissions")
                    .select("user_id, display_name, role, comm_preference, is_active")
                    .in_("user_id", worker_ids)
                    .execute()
                )
                for row in (perm_res.data or []):
                    worker_data[row["user_id"]] = row
            except Exception:
                pass

        # ── Fetch open task counts per worker per property ───────────────
        task_counts: Dict[str, Dict[str, int]] = {}  # {worker_id: {property_id: count}}
        if worker_ids:
            try:
                tasks_res = (
                    db.table("tasks")
                    .select("assigned_to, property_id, status")
                    .in_("assigned_to", worker_ids)
                    .in_("status", ["PENDING", "ACKNOWLEDGED", "IN_PROGRESS", "MANAGER_EXECUTING"])
                    .execute()
                )
                for t in (tasks_res.data or []):
                    wid = t.get("assigned_to") or ""
                    pid = t.get("property_id") or ""
                    if wid not in task_counts:
                        task_counts[wid] = {}
                    task_counts[wid][pid] = task_counts[wid].get(pid, 0) + 1
            except Exception:
                pass

        # ── Build per-property output ────────────────────────────────────
        lanes = ["CLEANING", "MAINTENANCE", "CHECKIN_CHECKOUT"]

        # Group assignments by property
        prop_workers: Dict[str, List[Dict]] = {p: [] for p in scope_props}
        for row in all_assignments:
            prop_workers.setdefault(row["property_id"], []).append(row)

        properties_out = []
        for p in scope_props:
            workers_in_prop = prop_workers.get(p, [])

            # Build lane coverage map: lane → {priority: user_id}
            lane_coverage: Dict[str, Dict[int, str]] = {lane: {} for lane in lanes}
            for row in workers_in_prop:
                lane = row.get("operational_lane") or ""
                prio = row.get("priority") or 99
                uid = row.get("user_id") or ""
                if lane in lane_coverage:
                    lane_coverage[lane][prio] = uid

            coverage_gaps = [
                lane for lane in lanes
                if 1 not in lane_coverage.get(lane, {})
            ]

            # Build worker list for this property
            workers_out = []
            seen_workers = set()
            for row in sorted(workers_in_prop, key=lambda r: (r.get("operational_lane") or "", r.get("priority") or 99)):
                uid = row.get("user_id") or ""
                lane = row.get("operational_lane") or ""
                prio = row.get("priority") or 99
                winfo = worker_data.get(uid, {})
                comm = winfo.get("comm_preference") or {}
                open_tasks = (task_counts.get(uid) or {}).get(p, 0)
                designation = "Primary" if prio == 1 else ("Backup" if prio == 2 else f"Priority {prio}")

                entry_key = (uid, lane)
                if entry_key not in seen_workers:
                    seen_workers.add(entry_key)
                    workers_out.append({
                        "user_id": uid,
                        "display_name": winfo.get("display_name") or uid,
                        "role": winfo.get("role") or "worker",
                        "is_active": winfo.get("is_active", True),
                        "lane": lane,
                        "priority": prio,
                        "designation": designation,
                        "open_tasks_on_property": open_tasks,
                        "contact": {
                            "line": comm.get("line_id") or comm.get("line") or "",
                            "phone": comm.get("phone") or "",
                            "email": comm.get("email") or "",
                        },
                    })

            properties_out.append({
                "property_id": p,
                "workers": workers_out,
                "lane_coverage": {
                    lane: {
                        "has_primary": 1 in lane_coverage.get(lane, {}),
                        "primary_user_id": lane_coverage.get(lane, {}).get(1),
                        "backup_user_id": lane_coverage.get(lane, {}).get(2),
                    }
                    for lane in lanes
                },
                "coverage_gaps": coverage_gaps,
            })

        total_workers = len({r["user_id"] for r in all_assignments if r.get("user_id")})

        return JSONResponse(status_code=200, content={
            "manager_id": tenant_id,
            "role": caller_role,
            "properties": properties_out,
            "total_workers": total_workers,
        })

    except Exception as exc:
        logger.exception("manager_team error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)
