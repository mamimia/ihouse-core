"""
Phases 710–712, 1022, 1033, 1034 — Task Takeover & Management (Manager/Admin)
=======================================================================

Phase 1022 hardening of the Phase 710 skeleton.
Phase 1033 expansion: Task notes, manager alerts, team overview, and flexible reassign.
Phase 1034 (OM-1): takeover-start route (dedicated timing-bypass execution path).

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
    POST /tasks/{task_id}/take-over       — manager/admin takes over task (→ MANAGER_EXECUTING)
    POST /tasks/{task_id}/takeover-start  — Phase 1034: PENDING→IN_PROGRESS bypass (no MANAGER_EXECUTING)
    POST /tasks/{task_id}/reassign        — manager/admin releases to new worker
    POST /tasks/{task_id}/notes           — add attributed note to tasks.notes[] JSONB
    GET  /tasks/{task_id}/context         — full task context for execution
    GET  /manager/tasks                   — manager's task board
    GET  /manager/alerts                  — manager-specific task alerts
    GET  /manager/team-overview           — status of all workers/tasks
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
    """Return the property IDs assigned to this manager."""
    try:
        res = (
            db.table("staff_property_assignments")
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
        task_res = db.table("tasks").select("*").eq("task_id", task_id).limit(1).execute()
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
        }).eq("task_id", task_id).execute()

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
# Phase 1034 (OM-1) — POST /tasks/{task_id}/takeover-start
# Dedicated timing-bypass execution path for manager/admin
# ===========================================================================

@router.post(
    "/tasks/{task_id}/takeover-start",
    summary="Manager/Admin takeover-start: PENDING→IN_PROGRESS bypass (Phase 1034)",
)
async def takeover_start_task(
    task_id: str,
    body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    POST /tasks/{task_id}/takeover-start

    Phase 1034 (OM-1) locked constraint:
    This is the ONLY path where worker timing gates are bypassed.
    The existing /acknowledge and /start endpoints are NEVER globally bypassed by role.

    Atomically walks the task from its current status to IN_PROGRESS:
        PENDING          → ACKNOWLEDGED → IN_PROGRESS
        ACKNOWLEDGED     → IN_PROGRESS
        IN_PROGRESS      → IN_PROGRESS (idempotent, still valid)
        MANAGER_EXECUTING → rejected (use existing take-over endpoint)

    Unlike /take-over (which sets MANAGER_EXECUTING), this endpoint keeps the
    task on the normal worker state machine (IN_PROGRESS). The manager is
    executing as the temporary assigned worker, not creating a MANAGER_EXECUTING silo.

    Gate:
        - Caller must be role=manager or role=admin
        - Manager: task property must be in their assigned properties
        - Admin: any task in tenancy
        - Task must NOT be COMPLETED or CANCELED
        - MANAGER_EXECUTING tasks are rejected (not this endpoint's domain)

    Body:
        reason  (optional) — free-text reason for takeover-start

    Audit:
        task_actions → TASK_TAKEOVER_STARTED
    """
    reason = str(body.get("reason") or "").strip() or None

    try:
        db = client if client is not None else _get_db()

        # Permission check
        caller_role = _get_caller_role(db, tenant_id)
        if caller_role not in _TAKEOVER_AUTHORIZED_ROLES:
            return make_error_response(
                403, ErrorCode.VALIDATION_ERROR,
                extra={"detail": "Only managers and admins can use takeover-start."},
            )

        # Fetch task
        task_res = db.table("tasks").select("*").eq("task_id", task_id).limit(1).execute()
        task_rows = task_res.data or []
        if not task_rows:
            return make_error_response(404, "NOT_FOUND", extra={"detail": f"Task '{task_id}' not found."})

        task = task_rows[0]
        current_status = str(task.get("status", "")).upper()

        # Reject terminal states
        if current_status in {"COMPLETED", "CANCELED"}:
            return make_error_response(
                400, ErrorCode.VALIDATION_ERROR,
                extra={"detail": f"Cannot use takeover-start on a terminal task (status={current_status})."},
            )

        # Reject MANAGER_EXECUTING — that's the /take-over endpoint's domain
        if current_status == "MANAGER_EXECUTING":
            return make_error_response(
                409, ErrorCode.VALIDATION_ERROR,
                extra={"detail": "Task is MANAGER_EXECUTING. Use /take-over for full takeover execution."},
            )

        # Manager property scope check
        if caller_role == "manager":
            manager_props = set(_get_manager_property_ids(db, tenant_id))
            task_property = task.get("property_id", "")
            if task_property and manager_props and task_property not in manager_props:
                return make_error_response(
                    403, ErrorCode.VALIDATION_ERROR,
                    extra={"detail": f"Property '{task_property}' is not in your supervised properties."},
                )

        now = _now_iso()

        # Atomic walk: PENDING → ACKNOWLEDGED → IN_PROGRESS
        # If already ACKNOWLEDGED or IN_PROGRESS, only advance what's needed.
        previous_status = current_status
        update_payload: Dict[str, Any] = {"updated_at": now}

        if current_status == "PENDING":
            # Walk through ACKNOWLEDGED immediately then to IN_PROGRESS
            update_payload["status"] = "IN_PROGRESS"
            # Record that we skipped ACKNOWLEDGED gate
            update_payload["acknowledged_at"] = now
            update_payload["assigned_to"] = tenant_id
        elif current_status == "ACKNOWLEDGED":
            update_payload["status"] = "IN_PROGRESS"
            update_payload["assigned_to"] = tenant_id
        elif current_status == "IN_PROGRESS":
            # Idempotent — already where we need to be
            # Still take ownership
            update_payload["assigned_to"] = tenant_id
        # else: caught above by terminal/MANAGER_EXECUTING checks

        db.table("tasks").update(update_payload).eq("task_id", task_id).execute()
        final_status = update_payload.get("status", current_status)

        # task_actions: TASK_TAKEOVER_STARTED
        try:
            db.table("task_actions").insert({
                "id": _action_id("TAKEOVER_START", task_id, now),
                "task_id": task_id,
                "action": "TASK_TAKEOVER_STARTED",
                "performed_by": tenant_id,
                "details": {
                    "previous_status": previous_status,
                    "final_status": final_status,
                    "caller_role": caller_role,
                    "reason": reason,
                    "timing_gate_bypassed": True,
                    "bypass_method": "takeover-start",
                },
                "created_at": now,
            }).execute()
        except Exception:
            logger.warning("Phase 1034: failed to write TASK_TAKEOVER_STARTED action for %s", task_id)

        logger.info(
            "Phase 1034: task %s takeover-start by %s (role=%s) %s→%s",
            task_id, tenant_id, caller_role, previous_status, final_status,
        )

        return JSONResponse(status_code=200, content={
            "task_id": task_id,
            "status": final_status,
            "previous_status": previous_status,
            "taken_over_by": tenant_id,
            "taken_over_by_role": caller_role,
            "timing_gate_bypassed": True,
            "bypass_method": "takeover-start",
            "reason": reason,
        })

    except Exception as exc:
        logger.exception("takeover_start_task error: %s", exc)
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
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    POST /tasks/{task_id}/reassign

    Phase 1035: switched to jwt_identity (same as all other manager endpoints).
    Works on any active in-flight task status.

    Body:
        new_assignee_id (optional) — specific worker UUID to assign; null = open pool
        reason          (optional) — manager reason (internal, audit only)
        handoff_note    (optional) — worker-visible message appended to tasks.notes[]
                                     with source="handoff" — different from internal notes

    Worker notification:
        - Previous assignee receives "task reassigned away" notification
        - New assignee receives "task assigned to you" notification
        - Handoff note (if any) is written to tasks.notes[] and visible on worker surface
    """
    new_assignee_id = str(body.get("new_assignee_id") or "").strip() or None
    reason = str(body.get("reason") or "").strip() or None
    handoff_note = str(body.get("handoff_note") or "").strip() or None

    try:
        db = client if client is not None else _get_db()

        # Phase 1035: jwt_identity (not jwt_auth) — same pattern as all manager endpoints
        caller_role = str(identity.get("role", "worker")).strip()
        caller_user_id = str(identity.get("user_id", "")).strip()
        caller_name = _get_caller_display_name(db, caller_user_id)

        if caller_role not in _TAKEOVER_AUTHORIZED_ROLES:
            return make_error_response(
                403, ErrorCode.VALIDATION_ERROR,
                extra={"detail": "Only managers and admins can reassign tasks."},
            )

        # Fetch task
        task_res = db.table("tasks").select("*").eq("task_id", task_id).limit(1).execute()
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
        }).eq("task_id", task_id).execute()

        task_kind_label = (task.get("kind") or task.get("task_kind") or "task").replace("_", " ").lower()
        prop_label = task.get("property_id", "")
        previous_assignee = task.get("assigned_to")

        # task_actions record
        try:
            db.table("task_actions").insert({
                "id": _action_id("REASSIGN", task_id, now),
                "task_id": task_id,
                "action": "MANAGER_TASK_REASSIGNED",
                "performed_by": caller_user_id,
                "details": {
                    "reassigned_to": new_assignee_id,
                    "reassigned_by": caller_user_id,
                    "reassigned_by_name": caller_name,
                    "caller_role": caller_role,
                    "reason": reason,
                    "handoff_note": handoff_note,
                    # Audit chain snapshot
                    "original_worker_id": task.get("original_worker_id"),
                    "taken_over_by": task.get("taken_over_by"),
                    "taken_over_reason": task.get("taken_over_reason"),
                    "previous_assignee": previous_assignee,
                },
                "created_at": now,
            }).execute()
        except Exception:
            logger.warning("Phase 1035: failed to write MANAGER_TASK_REASSIGNED action for %s", task_id)

        # Write handoff_note to tasks.notes[] — worker-visible (source="handoff")
        if handoff_note:
            try:
                existing_notes: list = task.get("notes") or []
                note_entry = {
                    "id": _action_id("HANDOFF_NOTE", task_id, now),
                    "text": handoff_note,
                    "author_id": caller_user_id,
                    "author_name": caller_name,
                    "author_role": caller_role,
                    "source": "handoff",          # worker surface can filter on this
                    "created_at": now,
                }
                db.table("tasks").update({
                    "notes": existing_notes + [note_entry],
                    "updated_at": now,
                }).eq("task_id", task_id).execute()
            except Exception as ne:
                logger.warning("Phase 1035: failed to write handoff note for %s: %s", task_id, ne)

        # Notify previous assignee that task was reassigned away (best-effort)
        if previous_assignee and previous_assignee != new_assignee_id:
            try:
                db.table("notification_queue").insert({
                    "id": _action_id("NOTIF_REASSIGN_OLD", task_id, now),
                    "recipient_id": previous_assignee,
                    "channel": "auto",
                    "message": f"Your {task_kind_label} task at {prop_label} has been reassigned by {caller_name or 'a manager'}.",
                    "notification_type": "task_reassigned_away",
                    "reference_type": "task",
                    "reference_id": task_id,
                    "tenant_id": identity.get("tenant_id", ""),
                    "status": "queued",
                    "created_at": now,
                }).execute()
            except Exception:
                pass

        # Notify new assignee (best-effort)
        if new_assignee_id:
            try:
                msg = f"You have been assigned a {task_kind_label} task at {prop_label}."
                if handoff_note:
                    msg += f" Note from manager: {handoff_note[:120]}"
                db.table("notification_queue").insert({
                    "id": _action_id("NOTIF_REASSIGN", task_id, now),
                    "recipient_id": new_assignee_id,
                    "channel": "auto",
                    "message": msg,
                    "notification_type": "task_assigned",
                    "reference_type": "task",
                    "reference_id": task_id,
                    "tenant_id": identity.get("tenant_id", ""),
                    "status": "queued",
                    "created_at": now,
                }).execute()
            except Exception:
                pass

        # Audit event
        try:
            from services.audit_writer import write_audit_event
            write_audit_event(
                db, tenant_id=identity.get("tenant_id", ""), entity_type="task",
                entity_id=task_id, action="MANAGER_TASK_REASSIGNED",
                details={
                    "reassigned_to": new_assignee_id,
                    "reassigned_by": caller_user_id,
                    "original_worker_id": task.get("original_worker_id"),
                    "taken_over_by": task.get("taken_over_by"),
                    "reason": reason,
                    "handoff_note": handoff_note,
                },
            )
        except Exception:
            pass

        return JSONResponse(status_code=200, content={
            "task_id": task_id,
            "status": "PENDING",
            "new_assignee_id": new_assignee_id,
            "reassigned_by": caller_user_id,
            "handoff_note_written": bool(handoff_note),
            "audit_chain": {
                "original_worker_id": task.get("original_worker_id"),
                "taken_over_by": task.get("taken_over_by"),
                "taken_over_reason": task.get("taken_over_reason"),
                "previous_assignee": previous_assignee,
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
            "id": _action_id("NOTIF_TAKEOVER", task.get("task_id", task.get("id", "")), now),
            "recipient_id": original_worker,
            "channel": "auto",
            "message": message,
            "notification_type": "task_takeover",
            "reference_type": "task",
            "reference_id": task.get("task_id", task.get("id", "")),
            "tenant_id": tenant_id,
            "status": "queued",
            "created_at": now,
        }).execute()

        try:
            from channels.sse_broker import sse_broker
            import asyncio
            asyncio.create_task(sse_broker.publish("TASK_MANAGER_EXECUTING", {
                "task_id": task.get("task_id", task.get("id", "")),
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
        task_res = db.table("tasks").select("*").eq("task_id", task_id).limit(1).execute()
        task_rows = task_res.data or []
        if not task_rows:
            return make_error_response(404, "NOT_FOUND")
        context = _get_full_task_context(db, task_rows[0])
        return JSONResponse(status_code=200, content={"task_id": task_id, "context": context})
    except Exception as exc:
        logger.exception("get_task_context error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# Phase 1034 (OM-1) — GET /tasks/{task_id}
# Single task fetch for ManagerTaskCard — timing fields + notes + property name
# ===========================================================================

@router.get(
    "/tasks/detail/{task_id}",
    summary="Get single task enrichment for ManagerTaskCard — GET /tasks/detail/{task_id} (Phase 1034)",
)
async def get_task_for_manager(
    task_id: str,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    GET /tasks/detail/{task_id}

    Phase 1034 (OM-1): Returns the full task row enriched with timing fields
    and property display name for ManagerTaskCard drill-down.
    Used by stream event expand and alert rail task links.

    Timing fields: ack_is_open, ack_allowed_at, start_is_open, start_allowed_at
    Extra fields: property_name (display), notes (list, never null)
    Permission: manager (property-scoped) or admin (all). Workers cannot access.

    Phase 1033 pattern: uses jwt_identity so Preview As and Act As sessions
    correctly resolve the caller role and user_id from the JWT directly.
    """
    try:
        db = client if client is not None else _get_db()
        caller_role = str(identity.get("role", "worker")).strip()
        caller_user_id = str(identity.get("user_id", "")).strip()
        if caller_role not in _TAKEOVER_AUTHORIZED_ROLES:
            return make_error_response(
                403, ErrorCode.VALIDATION_ERROR,
                extra={"detail": "Only managers and admins can access this endpoint."},
            )

        task_res = db.table("tasks").select("*").eq("task_id", task_id).limit(1).execute()
        task_rows = task_res.data or []
        if not task_rows:
            return make_error_response(404, "NOT_FOUND", extra={"detail": f"Task '{task_id}' not found."})

        task = task_rows[0]

        # Manager property scope check
        if caller_role == "manager":
            prop_ids = set(_get_manager_property_ids(db, caller_user_id))
            task_property = task.get("property_id", "")
            if task_property and prop_ids and task_property not in prop_ids:
                return make_error_response(
                    403, ErrorCode.VALIDATION_ERROR,
                    extra={"detail": f"Property '{task_property}' is not in your supervised properties."},
                )

        # Timing enrichment (same as worker_router)
        timing: Dict[str, Any] = {}
        try:
            from tasks.timing import compute_task_timing
            timing = compute_task_timing(task)
        except Exception:
            pass

        # Property display name (best-effort)
        property_name: Optional[str] = None
        prop_id = task.get("property_id")
        if prop_id:
            try:
                prop_res = (
                    db.table("properties")
                    .select("display_name")
                    .eq("property_id", prop_id)   # property_id is the text key, not id (bigint)
                    .limit(1)
                    .execute()
                )
                if prop_res.data:
                    property_name = prop_res.data[0].get("display_name")
            except Exception:
                pass

        # Resolve assigned_to UUID → display name (best-effort)
        assigned_to_name: Optional[str] = None
        original_worker_name: Optional[str] = None
        taken_over_by_name: Optional[str] = None
        _resolve_ids = list(filter(None, [
            task.get("assigned_to"), task.get("original_worker_id"), task.get("taken_over_by")
        ]))
        if _resolve_ids:
            try:
                _name_res = (
                    db.table("tenant_permissions")
                    .select("user_id, display_name")
                    .in_("user_id", list(set(_resolve_ids)))
                    .execute()
                )
                _name_map: Dict[str, str] = {
                    r["user_id"]: (r.get("display_name") or r["user_id"][:14])
                    for r in (_name_res.data or [])
                }
                assigned_to_name    = _name_map.get(task.get("assigned_to") or "") or None
                original_worker_name= _name_map.get(task.get("original_worker_id") or "") or None
                taken_over_by_name  = _name_map.get(task.get("taken_over_by") or "") or None
            except Exception:
                pass

        return JSONResponse(status_code=200, content={
            "task": {
                **task,
                # Normalize column names to match ManagerTaskCardTask type
                "id":           task.get("task_id"),         # frontend expects 'id'
                "task_kind":    task.get("kind"),             # frontend expects 'task_kind'
                # Timing enrichment
                "ack_is_open":      timing.get("ack_is_open"),
                "ack_allowed_at":   timing.get("ack_allowed_at"),
                "start_is_open":    timing.get("start_is_open"),
                "start_allowed_at": timing.get("start_allowed_at"),
                "property_name":    property_name,
                "notes":            task.get("notes") or [],
                # Resolved display names for worker identity
                "assigned_to_name":      assigned_to_name,
                "original_worker_name":  original_worker_name,
                "taken_over_by_name":    taken_over_by_name,
            },
        })

    except Exception as exc:
        logger.exception("get_task_for_manager error: %s", exc)
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
        # Runway rule (Phase 1037):
        #   - Overdue tasks (due_date < today): always show, no cutoff
        #   - Future tasks: cap at today + 30 days
        #   - Never show far-future tasks (August, September, next year, etc.)
        open_statuses = ["PENDING", "ACKNOWLEDGED", "IN_PROGRESS", "MANAGER_EXECUTING"]
        _TASK_HORIZON_DAYS = 30  # forward cap
        task_horizon_date = (datetime.now(timezone.utc) + timedelta(days=_TASK_HORIZON_DAYS)).strftime("%Y-%m-%d")
        query = (
            db.table("tasks")
            .select(
                "task_id, kind, status, priority, booking_id, property_id, "
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

        # Apply 30-day forward horizon: exclude tasks due more than 30 days from now.
        # Overdue tasks have no lower bound — they are always visible until resolved.
        query = query.lte("due_date", task_horizon_date)

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

        # Batch-resolve property names and worker display names for human-first display
        all_prop_ids = list({t.get("property_id") for t in tasks if t.get("property_id")})
        all_worker_ids = list({
            uid for t in tasks for uid in [t.get("assigned_to"), t.get("taken_over_by"), t.get("original_worker_id")]
            if uid
        })

        property_name_map: Dict[str, str] = {}
        worker_name_map: Dict[str, str] = {}

        if all_prop_ids:
            try:
                # Key: use property_id (text) not id (bigint surrogate)
                pr = db.table("properties").select("property_id, display_name").in_("property_id", all_prop_ids).execute()
                for row in (pr.data or []):
                    property_name_map[row["property_id"]] = row.get("display_name") or row["property_id"]
            except Exception:
                pass

        if all_worker_ids:
            try:
                wr = db.table("tenant_permissions").select("user_id, display_name").in_("user_id", all_worker_ids).execute()
                for row in (wr.data or []):
                    worker_name_map[row["user_id"]] = row.get("display_name") or row["user_id"][:14]
            except Exception:
                pass

        # Normalize: alias columns + inject resolved names for human-first display
        def _normalize(t: dict) -> dict:
            out = dict(t)
            out["id"] = out.get("task_id")
            out["task_kind"] = out.get("kind")
            prop_id = out.get("property_id") or ""
            out["property_name"] = property_name_map.get(prop_id) or prop_id
            out["assigned_to_name"] = worker_name_map.get(out.get("assigned_to") or "") or None
            out["taken_over_by_name"] = worker_name_map.get(out.get("taken_over_by") or "") or None
            out["original_worker_name"] = worker_name_map.get(out.get("original_worker_id") or "") or None
            return out

        return JSONResponse(status_code=200, content={
            "manager_id": caller_user_id,
            "role": caller_role,
            "groups": {k: [_normalize(t) for t in v] for k, v in groups.items()},
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
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    POST /tasks/{task_id}/notes

    Adds an operational note to a task. Notes are stored in tasks.notes[] JSONB
    and dual-written to task_actions for the audit trail.
    Visible to managers and admins only. Workers not notified.

    Body:
        note  (required) — free-text operational note

    Phase 1033 pattern: uses jwt_identity so Preview As and Act As sessions
    correctly resolve the caller role and user_id without a secondary DB lookup.
    """
    note = str(body.get("note") or "").strip()
    if not note:
        return make_error_response(
            400, ErrorCode.VALIDATION_ERROR,
            extra={"detail": "'note' is required."},
        )

    try:
        db = client if client is not None else _get_db()
        caller_role = str(identity.get("role", "worker")).strip()
        caller_user_id = str(identity.get("user_id", "")).strip()
        if caller_role not in _TAKEOVER_AUTHORIZED_ROLES:
            return make_error_response(
                403, ErrorCode.VALIDATION_ERROR,
                extra={"detail": "Only managers and admins can add task notes."},
            )

        # Resolve author display name for attribution
        author_name = _get_caller_display_name(db, caller_user_id)

        # Verify task exists and belongs to supervised properties (manager scope)
        task_res = db.table("tasks").select("task_id, status, property_id, notes").eq("task_id", task_id).limit(1).execute()
        task_rows = task_res.data or []
        if not task_rows:
            return make_error_response(404, "NOT_FOUND", extra={"detail": f"Task '{task_id}' not found."})

        task = task_rows[0]
        if caller_role == "manager":
            prop_ids = _get_manager_property_ids(db, caller_user_id)
            if task.get("property_id") not in prop_ids:
                return make_error_response(
                    403, ErrorCode.VALIDATION_ERROR,
                    extra={"detail": "Task does not belong to a supervised property."},
                )

        now = _now_iso()
        note_id = _action_id("NOTE", task_id, now)

        # Phase 1034: note object with full attribution fields
        note_obj = {
            "id": note_id,
            "text": note,
            "author_id": caller_user_id,
            "author_name": author_name,
            "author_role": caller_role,
            "created_at": now,
            "source": "manager",
        }

        # Append to tasks.notes[] JSONB array (append-only — never deletes or overwrites)
        existing_notes = task.get("notes") or []
        if not isinstance(existing_notes, list):
            existing_notes = []
        updated_notes = existing_notes + [note_obj]

        try:
            db.table("tasks").update({
                "notes": updated_notes,
                "updated_at": now,
            }).eq("task_id", task_id).execute()
        except Exception as notes_err:
            logger.warning("Phase 1034: failed to append note to tasks.notes[] for %s: %s", task_id, notes_err)
            # Fallback: still write to task_actions so note is not lost

        # Also write to task_actions for the audit trail
        try:
            db.table("task_actions").insert({
                "id": note_id,
                "task_id": task_id,
                "action": "OPERATIONAL_NOTE",
                "performed_by": caller_user_id,
                "details": {
                    "note": note,
                    "author_id": caller_user_id,
                    "author_name": author_name,
                    "author_role": caller_role,
                    "source": "manager",
                    "created_at": now,
                },
                "created_at": now,
            }).execute()
        except Exception:
            logger.warning("Phase 1034: failed to write OPERATIONAL_NOTE action for %s", task_id)

        return JSONResponse(status_code=201, content={
            "note_id": note_id,
            "task_id": task_id,
            "note": note_obj,
            "notes_count": len(updated_notes),
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
# Phase 1035/1037 — GET /manager/stream/bookings
# Operational booking runway for OM Stream.
# ===========================================================================
# Data source: booking_state (NOT bookings, NOT audit_events).
#
# WHY booking_state AND NOT bookings:
#   - booking_state is the live operational truth — it has tenant_id,
#     status = 'active'/'checked_in', check_in, check_out, early_checkout_status.
#   - bookings table holds raw OTA-synced data with start_date/end_date
#     and no tenant_id. It does NOT have live operational status.
#   - All other operational routers (operations_router, manual_booking_router,
#     early_checkout_router, worker_router) use booking_state. So must we.
#
# Schema (booking_state):
#   booking_id, tenant_id, property_id, check_in, check_out,
#   guest_name, status, source, early_checkout_status
#
# A booking is operationally alive if:
#   check_out >= yesterday AND check_in <= window_end AND status NOT terminal
# This single inequality naturally captures:
#   - Active in-stay (check_in < today, check_out > today)
#   - Arriving today (check_in == today)
#   - Departing today (check_out == today)
#   - All upcoming in the forward runway window
#
# Terminal statuses (exclude): canceled, cancelled, rejected, checked_out, completed
# Forward horizon: 30 days (updated from 7d per Phase 1037 product rule)

from datetime import datetime, timedelta, timezone

_BOOKING_RUNWAY_DAYS_BACK    = 1   # include yesterday's departures
_BOOKING_RUNWAY_DAYS_FORWARD = 30  # 30-day forward runway (Phase 1037 rule)

# Terminal statuses — exclude from operational runway
_TERMINAL_BOOKING_STATUSES = frozenset({
    "cancelled", "canceled", "rejected", "checked_out", "completed"
})

@router.get(
    "/manager/stream/bookings",
    summary="Operational booking runway for OM Stream (Phase 1035/1037)",
)
async def manager_stream_bookings(
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    GET /manager/stream/bookings

    Operational booking runway. Source: booking_state (live operational table).
    Visibility rule: all non-terminal bookings where check_out >= yesterday
    AND check_in <= today + 30 days.

    This naturally captures:
    - Active in-stay bookings (guest currently in property)
    - Arriving today / this week / this month
    - Departing today / tomorrow
    Not booking event history. Not audit data.
    """
    try:
        db = client if client is not None else _get_db()
        caller_role    = str(identity.get("role", "worker")).strip()
        caller_user_id = str(identity.get("user_id", "")).strip()
        tenant_id      = str(identity.get("tenant_id", "")).strip()

        if caller_role not in _TAKEOVER_AUTHORIZED_ROLES:
            return make_error_response(
                403, ErrorCode.VALIDATION_ERROR,
                extra={"detail": "Only managers and admins can view booking runway."},
            )

        now          = datetime.now(timezone.utc)
        window_start = (now - timedelta(days=_BOOKING_RUNWAY_DAYS_BACK)).strftime("%Y-%m-%d")
        window_end   = (now + timedelta(days=_BOOKING_RUNWAY_DAYS_FORWARD)).strftime("%Y-%m-%d")
        today_str    = now.strftime("%Y-%m-%d")

        # Fetch property IDs in scope (manager-scoped; admin sees all)
        prop_ids: Optional[List[str]] = None
        if caller_role == "manager":
            prop_ids = _get_manager_property_ids(db, caller_user_id)
            if not prop_ids:
                return JSONResponse(status_code=200, content={"bookings": [], "total": 0})

        # ── Single query against booking_state ────────────────────────────────
        # check_out >= window_start AND check_in <= window_end
        # covers all live cases: in-stay, arriving, departing — in one pass.
        # No need for three separate queries. In-stay bookings are captured
        # because check_out >= yesterday is TRUE for any booking still ongoing.
        _BS_SELECT = (
            "booking_id, property_id, check_in, check_out, "
            "status, guest_name, source, early_checkout_status"
        )
        try:
            q = (
                db.table("booking_state")
                .select(_BS_SELECT)
                .gte("check_out", window_start)   # not yet checked out past yesterday
                .lte("check_in",  window_end)      # arrives before the 30-day horizon
            )
            # Tenant isolation — always apply
            if tenant_id:
                q = q.eq("tenant_id", tenant_id)
            # Manager property scope
            if prop_ids is not None:
                q = q.in_("property_id", prop_ids)

            result = q.execute()
            raw_rows = result.data or []

            # Filter terminal statuses
            all_bookings = [
                r for r in raw_rows
                if str(r.get("status") or "").lower() not in _TERMINAL_BOOKING_STATUSES
            ]
        except Exception as qe:
            logger.warning("manager_stream_bookings: booking_state query error %s", qe)
            all_bookings = []

        # Resolve property names
        scope_prop_ids = list({b.get("property_id") for b in all_bookings if b.get("property_id")})
        prop_name_map: Dict[str, str] = {}
        if scope_prop_ids:
            try:
                pn = db.table("properties").select("property_id, display_name").in_(
                    "property_id", scope_prop_ids
                ).execute()
                for row in (pn.data or []):
                    prop_name_map[row["property_id"]] = row.get("display_name") or row["property_id"]
            except Exception:
                pass

        # Urgency sort key — uses check_in / check_out (booking_state columns)
        # Priority: Departing Today (1) → Arriving Today (2) → Active In-Stay (3)
        # → Departing Tomorrow (4) → Arriving Tomorrow (5) → Upcoming (6)
        def _urgency(booking: dict) -> tuple:
            ci = str(booking.get("check_in")  or "")
            co = str(booking.get("check_out") or "")
            if co == today_str:              return (1, co, ci)   # departing today (most urgent)
            if ci == today_str:              return (2, ci, co)   # arriving today
            if ci < today_str and co > today_str: return (3, co, ci)  # active in-stay (soonest out first)
            try:
                dep_days = (datetime.strptime(co, "%Y-%m-%d").date() - now.date()).days
                arr_days = (datetime.strptime(ci, "%Y-%m-%d").date() - now.date()).days
                if dep_days == 1: return (4, co, ci)  # departing tomorrow
                if arr_days == 1: return (5, ci, co)  # arriving tomorrow
            except Exception:
                pass
            return (6, ci, co)  # upcoming

        def _label(booking: dict) -> str:
            ci = str(booking.get("check_in")  or "")
            co = str(booking.get("check_out") or "")
            if ci == today_str: return "Arriving Today"
            if co == today_str: return "Departing Today"
            if ci < today_str and co > today_str:
                try:
                    co_fmt = datetime.strptime(co, "%Y-%m-%d").strftime("%b %-d")
                    return f"Active Stay — Out {co_fmt}"
                except Exception:
                    return "Active Stay"
            # Future arrivals
            try:
                days = (datetime.strptime(ci, "%Y-%m-%d").date() - now.date()).days
                if days == 1:  return "Arriving Tomorrow"
                if days > 1:  return f"Arriving in {days}d"
            except Exception:
                pass
            # Future departures (confirmed, not yet arrived)
            try:
                dep_days = (datetime.strptime(co, "%Y-%m-%d").date() - now.date()).days
                if dep_days == 1: return "Departing Tomorrow"
            except Exception:
                pass
            return "Upcoming"

        def _is_eligible_for_early_checkout(booking: dict) -> bool:
            """True if booking is active/checked_in and early checkout not completed."""
            st = str(booking.get("status") or "").lower()
            ec = str(booking.get("early_checkout_status") or "none").lower()
            return st in ("active", "checked_in") and ec != "completed"

        all_bookings.sort(key=_urgency)

        out = []
        for b in all_bookings:
            pid       = b.get("property_id") or ""
            ec_status = b.get("early_checkout_status") or "none"
            # Use check_in/check_out for dates; map to start_date/end_date for frontend compat
            out.append({
                "booking_id":              b.get("booking_id"),
                "property_id":             pid,
                "property_name":           prop_name_map.get(pid) or pid,
                "guest_name":              b.get("guest_name") or "Guest",
                "start_date":              b.get("check_in"),    # alias for frontend compat
                "end_date":                b.get("check_out"),   # alias for frontend compat
                "check_in":                b.get("check_in"),
                "check_out":               b.get("check_out"),
                "status":                  b.get("status"),
                "source":                  b.get("source"),
                "urgency_label":           _label(b),
                "early_checkout_status":   ec_status,
                "early_checkout_eligible": _is_eligible_for_early_checkout(b),
            })

        return JSONResponse(status_code=200, content={"bookings": out, "total": len(out)})

    except Exception as exc:
        logger.exception("manager_stream_bookings error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)
# Phase 1033 — GET /manager/team
# Team overview: workers, task load, coverage gaps per property+lane
# ===========================================================================


@router.get(
    "/manager/team",
    summary="Manager team overview — worker load + coverage gaps (Phase 1033)",
)
async def manager_team(
    task_kind: Optional[str] = None,   # Phase 1035: filter workers by task compatibility
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    GET /manager/team

    Phase 1033: uses jwt_identity.
    Phase 1035: optional ?task_kind= param filters workers by lane compatibility.
       CLEANING        → workers with 'cleaner' in worker_roles
       CHECKIN_PREP    → workers with 'checkin' in worker_roles
       CHECKOUT_VERIFY → workers with 'checkout' in worker_roles
       MAINTENANCE     → workers with 'maintenance' in worker_roles
       Combined tasks  → workers whose roles cover all required lanes

    task_kind compatibility map:
       CLEANING / GENERAL_CLEANING → lane CLEANING
       CHECKIN_PREP / GUEST_WELCOME / SELF_CHECKIN_FOLLOWUP → lane CHECKIN_CHECKOUT
       CHECKOUT_VERIFY → lane CHECKIN_CHECKOUT
       MAINTENANCE → lane MAINTENANCE
       (null / unknown) → all workers returned unfiltered
    """
    try:
        db = client if client is not None else _get_db()
        caller_role = str(identity.get("role", "worker")).strip()
        caller_user_id = str(identity.get("user_id") or identity.get("tenant_id", "")).strip()

        if caller_role not in _TAKEOVER_AUTHORIZED_ROLES:
            return make_error_response(
                403, ErrorCode.VALIDATION_ERROR,
                extra={"detail": "Only managers and admins can view team overview."},
            )

        prop_ids: Optional[List[str]] = None
        if caller_role == "manager":
            prop_ids = _get_manager_property_ids(db, caller_user_id)

        # Guard: if manager has no assigned properties, return empty immediately.
        # Must come BEFORE the .in_() DB call — passing an empty list to
        # supabase-py's .in_() generates invalid PostgREST syntax and crashes.
        if prop_ids is not None and len(prop_ids) == 0:
            return JSONResponse(status_code=200, content={
                "manager_id": caller_user_id,
                "role": caller_role,
                "properties": [],
                "total_workers": 0,
            })

        # ── Fetch all worker-property assignments in scope ──────────────────
        # Table: staff_property_assignments (user_id, property_id, priority)
        # No operational_lane column — lane is derived from worker_roles in tenant_permissions.
        q_assignments = db.table("staff_property_assignments").select(
            "user_id, property_id, priority"
        )
        if prop_ids is not None:
            q_assignments = q_assignments.in_("property_id", prop_ids)
        all_assignments = (q_assignments.execute()).data or []

        # Collect unique worker IDs
        worker_ids = list({r["user_id"] for r in all_assignments if r.get("user_id")})
        scope_props = list({r["property_id"] for r in all_assignments if r.get("property_id")})

        # ── Fetch property names ─────────────────────────────────────────────
        property_names: Dict[str, str] = {}
        if scope_props:
            try:
                prop_res = (
                    db.table("properties")
                    .select("id, display_name")
                    .in_("id", scope_props)
                    .execute()
                )
                for row in (prop_res.data or []):
                    property_names[row["id"]] = row.get("display_name") or row["id"]
            except Exception:
                pass

        # ── Fetch worker permission records (display_name, role, worker_roles, comm_preference) ─
        # worker_roles is a list like ["cleaner"], ["checkin", "checkout"], ["maintenance"]
        # This is the canonical lane source — no operational_lane column exists.
        worker_data: Dict[str, Dict] = {}
        if worker_ids:
            try:
                perm_res = (
                    db.table("tenant_permissions")
                    .select("user_id, display_name, role, worker_roles, comm_preference, is_active")
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

        # ── Worker-role → canonical lane mapping ────────────────────────────
        ROLE_TO_LANE = {
            "cleaner": "CLEANING",
            "maintenance": "MAINTENANCE",
            "checkin": "CHECKIN_CHECKOUT",
            "checkout": "CHECKIN_CHECKOUT",
        }

        # ── Build per-property output ────────────────────────────────────────
        lanes = ["CLEANING", "MAINTENANCE", "CHECKIN_CHECKOUT"]

        # Group assignments by property
        prop_workers: Dict[str, List[Dict]] = {p: [] for p in scope_props}
        for row in all_assignments:
            prop_workers.setdefault(row["property_id"], []).append(row)

        properties_out = []
        for p in scope_props:
            workers_in_prop = prop_workers.get(p, [])

            # Expand each assignment into per-lane rows using worker_roles
            expanded: List[Dict] = []
            for row in workers_in_prop:
                uid = row.get("user_id") or ""
                prio = row.get("priority") or 99
                winfo = worker_data.get(uid, {})
                w_roles: List[str] = winfo.get("worker_roles") or []
                lanes_for_worker = list({ROLE_TO_LANE[r] for r in w_roles if r in ROLE_TO_LANE})
                if not lanes_for_worker:
                    lanes_for_worker = ["UNKNOWN"]
                for wlane in lanes_for_worker:
                    expanded.append({"user_id": uid, "property_id": p, "priority": prio, "lane": wlane})

            # Build lane coverage map: lane → {priority: user_id}
            lane_coverage: Dict[str, Dict[int, str]] = {lane: {} for lane in lanes}
            for row in expanded:
                lane = row.get("lane") or ""
                prio = row.get("priority") or 99
                uid = row.get("user_id") or ""
                if lane in lane_coverage:
                    lane_coverage[lane][prio] = uid

            coverage_gaps = [
                lane for lane in lanes
                if 1 not in lane_coverage.get(lane, {})
            ]

            # Build worker list for this property (one row per worker+lane combination)
            workers_out = []
            seen_workers: set = set()
            for row in sorted(expanded, key=lambda r: (r.get("lane") or "", r.get("priority") or 99)):
                uid = row.get("user_id") or ""
                lane = row.get("lane") or ""
                prio = row.get("priority") or 99
                winfo = worker_data.get(uid, {})
                comm = winfo.get("comm_preference") or {}
                open_tasks = (task_counts.get(uid) or {}).get(p, 0)
                designation = "Primary" if prio == 1 else ("Backup" if prio == 2 else f"Backup {prio - 1}")

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
                        "open_tasks": open_tasks,
                        "open_tasks_on_property": open_tasks,
                        "contact": {
                            "line": comm.get("line_id") or comm.get("line") or "",
                            "phone": comm.get("phone") or "",
                            "email": comm.get("email") or "",
                        },
                    })

            # Phase 1035: filter by task_kind compatibility if requested
            # TASK_KIND → required lanes mapping
            _KIND_TO_LANES = {
                "CLEANING": {"CLEANING"},
                "GENERAL_CLEANING": {"CLEANING"},
                "CHECKIN_PREP": {"CHECKIN_CHECKOUT"},
                "GUEST_WELCOME": {"CHECKIN_CHECKOUT"},
                "SELF_CHECKIN_FOLLOWUP": {"CHECKIN_CHECKOUT"},
                "CHECKOUT_VERIFY": {"CHECKIN_CHECKOUT"},
                "MAINTENANCE": {"MAINTENANCE"},
            }
            if task_kind and task_kind.upper() in _KIND_TO_LANES:
                required_lanes = _KIND_TO_LANES[task_kind.upper()]
                workers_out = [
                    w for w in workers_out
                    if w.get("lane") in required_lanes
                ]

            properties_out.append({
                "property_id": p,
                "property_name": property_names.get(p) or p,
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
            "manager_id": caller_user_id,
            "role": caller_role,
            "properties": properties_out,
            "total_workers": total_workers,
            "total_properties": len(properties_out),
        })

    except Exception as exc:
        logger.exception("manager_team error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)
