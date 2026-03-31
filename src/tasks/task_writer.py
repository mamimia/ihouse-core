"""
Task Writer — Phase 115

Persists Task objects emitted by task_automator.py into the Supabase `tasks` table.

Architecture constraints:
- This module is WRITE-ONLY to the `tasks` table. It never reads from
  booking_state, event_log, or booking_financial_facts.
- All writes are IDEMPOTENT: INSERT ... ON CONFLICT (task_id) DO NOTHING
  (or DO UPDATE for reschedule/cancel). Deterministic task_id guarantees safety.
- All public functions are best-effort: errors are logged to stderr but
  never raised. Caller must never block on this module's failure.
- This module follows the same best-effort, non-blocking pattern established
  by financial_writer.py (Phase 66) and ordering_trigger.py (Phase 45).

Entry points:
  write_tasks_for_booking_created(tenant_id, booking_id, property_id, check_in, provider, client)
  cancel_tasks_for_booking_canceled(booking_id, tenant_id, client)
  reschedule_tasks_for_booking_amended(booking_id, new_check_in, tenant_id, client)

Integration:
  Called from service.py after APPLIED status for each relevant event type.
  Never called directly from OTA adapters.

Invariant (Phase 115):
  This module NEVER writes to booking_state, event_log, or booking_financial_facts.
  It writes ONLY to the `tasks` table.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from tasks.task_automator import (
    TaskCancelAction,
    TaskRescheduleAction,
    actions_for_booking_amended,
    actions_for_booking_canceled,
    tasks_for_booking_created,
)
from tasks.task_model import Task, TaskStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Supabase client
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Serialization helper
# ---------------------------------------------------------------------------

def _task_to_row(task: Task) -> dict:
    """Convert a Task dataclass to a Supabase-insertable dict."""
    return {
        "task_id": task.task_id,
        "tenant_id": task.tenant_id,
        "kind": task.kind.value,
        "status": task.status.value,
        "priority": task.priority.value,
        "urgency": task.urgency,
        "worker_role": task.worker_role.value,
        "ack_sla_minutes": task.ack_sla_minutes,
        "booking_id": task.booking_id,
        "property_id": task.property_id,
        "due_date": task.due_date,
        "title": task.title,
        "description": task.description,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "assigned_to": task.assigned_to,
        "notes": task.notes if task.notes else [],
        "canceled_reason": task.canceled_reason,
    }


# ---------------------------------------------------------------------------
# BOOKING_CREATED → write CHECKIN_PREP + CLEANING tasks
# ---------------------------------------------------------------------------

def write_tasks_for_booking_created(
    tenant_id: str,
    booking_id: str,
    property_id: str,
    check_in: str,
    provider: str = "unknown",
    client: Optional[Any] = None,
    check_out: Optional[str] = None,
) -> int:
    """
    Generate and persist tasks for a BOOKING_CREATED event.

    Creates two tasks (CHECKIN_PREP + CLEANING) using task_automator.
    Uses upsert with on_conflict='task_id' to ensure idempotency —
    duplicate BOOKING_CREATED events (DLQ replay) do not create duplicate tasks.

    Phase 1027a — FUTURE-ONLY CUTOFF:
    (Touches logic originally introduced in Phase 888 / task_automator Phase 112.)
    Operational tasks (CHECKIN_PREP, CLEANING, CHECKOUT_VERIFY) must NEVER be
    generated for bookings whose check_in date is in the past. This prevents
    iCal imports from generating ghost tasks for historical bookings.

    Rule: if check_in < today (server date UTC), skip all task creation.
    The booking is still imported for reference — only operational tasks are gated.

    Returns:
        Number of tasks successfully written (0 on error or skipped, expected 2-3 on success).

    Raises:
        Never. All errors are logged and swallowed (best-effort pattern).
    """
    try:
        from datetime import date as _date  # noqa: PLC0415
        _today = _date.today().isoformat()

        # ── Future-only cutoff (Phase 1027a) ────────────────────────────────
        # Determine the latest operational date for this booking.
        # If the booking's check_in is already in the past, no actionable
        # tasks can be created — the operational window has closed.
        #
        # Special case: if there is a check_out and it is today or future,
        # we still generate a CHECKOUT_VERIFY task (the guest may still need
        # to check out today). CHECKIN_PREP is skipped if check_in is past.
        _checkin_past = bool(check_in) and check_in < _today
        _checkout_future = bool(check_out) and check_out >= _today

        if _checkin_past and not _checkout_future:
            # Both check_in and check_out are past — skip all tasks.
            logger.info(
                "task_writer: skipping task generation for past booking "
                "booking_id=%s check_in=%s check_out=%s (future-only cutoff)",
                booking_id, check_in, check_out,
            )
            return 0
        # ─────────────────────────────────────────────────────────────────────

        db = client or _get_supabase_client()
        created_at = datetime.now(tz=timezone.utc).isoformat()

        tasks = tasks_for_booking_created(
            tenant_id=tenant_id,
            booking_id=booking_id,
            property_id=property_id,
            check_in=check_in,
            source=provider,
            created_at=created_at,
            check_out=check_out,
        )

        try:
            # Phase 1030: Deterministic Primary/Backup task assignment.
            # Query staff_property_assignments ORDER BY priority ASC so that
            # priority=1 (Primary) always wins. Replaces the accidental heap-order
            # first-match behavior from Phase 842.
            result_assign = (
                db.table("staff_property_assignments")
                .select("user_id, priority")
                .eq("tenant_id", tenant_id)
                .eq("property_id", property_id)
                .order("priority", desc=False)  # PRIMARY FIRST — deterministic
                .execute()
            )
            assigned_rows = result_assign.data or []
            # Preserve priority order: primaries first, backups last
            assigned_user_ids = [r["user_id"] for r in assigned_rows]

            assignment_map = {}
            if assigned_user_ids:
                result_perms = (
                    db.table("tenant_permissions")
                    .select("user_id, worker_roles")
                    .eq("tenant_id", tenant_id)
                    .in_("user_id", assigned_user_ids)
                    .execute()
                )
                user_roles_map = {r["user_id"]: (r.get("worker_roles") or []) for r in (result_perms.data or [])}

                # For each needed role, pick the lowest-priority (Primary) user that has it.
                # assigned_user_ids is already sorted by priority ASC from the DB query,
                # so the first match is always the canonical Primary for that work lane.
                roles_needed = {t.worker_role.value for t in tasks}
                for role_val in roles_needed:
                    role_normalized = role_val.lower()
                    for uid in assigned_user_ids:  # already priority-ordered
                        if role_normalized in user_roles_map.get(uid, []):
                            assignment_map[role_val] = uid
                            break  # Primary found — Backup workers are NOT assigned here.

            for t in tasks:
                t.assigned_to = assignment_map.get(t.worker_role.value)
                # Phase 1030-guard: Warn loudly when a task has no assigned worker.
                # A task with assigned_to=None is operationally invisible — no one receives it.
                # This is NOT a silent best-effort: it must be surfaced in logs for ops to act.
                if t.assigned_to is None:
                    logger.warning(
                        "task_writer: NO PRIMARY WORKER found for role=%s "
                        "property_id=%s booking_id=%s task_id=%s — task will be UNASSIGNED. "
                        "Ensure a worker with this role is assigned to the property.",
                        t.worker_role.value, property_id, booking_id, t.task_id,
                    )
        except Exception as _exc:
            logger.warning("task_writer: Failed to auto-assign tasks booking_id=%s: %s", booking_id, _exc)

        rows = [_task_to_row(t) for t in tasks]
        result = db.table("tasks").upsert(rows, on_conflict="task_id").execute()
        count = len(result.data) if result.data else 0
        logger.info(
            "task_writer: wrote %d tasks for BOOKING_CREATED booking_id=%s",
            count, booking_id,
        )
        return count

    except Exception as exc:  # noqa: BLE001
        logger.error(
            "task_writer: write_tasks_for_booking_created failed booking_id=%s: %s",
            booking_id, exc,
        )
        return 0


# ---------------------------------------------------------------------------
# BOOKING_CANCELED → cancel all PENDING tasks for this booking
# ---------------------------------------------------------------------------

def cancel_tasks_for_booking_canceled(
    booking_id: str,
    tenant_id: str,
    reason: str = "Booking canceled",
    client: Optional[Any] = None,
) -> int:
    """
    Cancel all PENDING tasks for a canceled booking.

    Flow:
      1. SELECT task_id FROM tasks WHERE booking_id=... AND tenant_id=... AND status='PENDING'
      2. actions_for_booking_canceled(booking_id, pending_task_ids)
      3. UPDATE tasks SET status='CANCELED', canceled_reason=..., updated_at=now()
         WHERE task_id IN (...) AND tenant_id=... AND status='PENDING'

    Step 3 is scoped to PENDING only — a task already IN_PROGRESS is not
    auto-canceled here (it remains for the worker to complete or manually cancel).

    Returns:
        Number of tasks successfully canceled (0 on error).

    Raises:
        Never. All errors are logged and swallowed (best-effort pattern).
    """
    try:
        db = client or _get_supabase_client()

        # Fetch PENDING task_ids for this booking
        result = (
            db.table("tasks")
            .select("task_id")
            .eq("booking_id", booking_id)
            .eq("tenant_id", tenant_id)
            .eq("status", TaskStatus.PENDING.value)
            .execute()
        )
        pending_rows = result.data or []
        if not pending_rows:
            logger.info(
                "task_writer: no PENDING tasks to cancel for booking_id=%s", booking_id
            )
            return 0

        pending_task_ids = [row["task_id"] for row in pending_rows]
        actions: list[TaskCancelAction] = actions_for_booking_canceled(
            booking_id=booking_id,
            pending_task_ids=pending_task_ids,
            reason=reason,
        )

        now = datetime.now(tz=timezone.utc).isoformat()
        canceled = 0
        for action in actions:
            db.table("tasks").update(
                {
                    "status": TaskStatus.CANCELED.value,
                    "canceled_reason": action.reason,
                    "updated_at": now,
                }
            ).eq("task_id", action.task_id).eq("tenant_id", tenant_id).eq(
                "status", TaskStatus.PENDING.value
            ).execute()
            canceled += 1

        logger.info(
            "task_writer: canceled %d tasks for BOOKING_CANCELED booking_id=%s",
            canceled, booking_id,
        )
        return canceled

    except Exception as exc:  # noqa: BLE001
        logger.error(
            "task_writer: cancel_tasks_for_booking_canceled failed booking_id=%s: %s",
            booking_id, exc,
        )
        return 0


# ---------------------------------------------------------------------------
# BOOKING_AMENDED → reschedule CHECKIN_PREP + CLEANING due_date
# ---------------------------------------------------------------------------

def reschedule_tasks_for_booking_amended(
    booking_id: str,
    new_check_in: str,
    tenant_id: str,
    client: Optional[Any] = None,
) -> int:
    """
    Update due_date on CHECKIN_PREP and CLEANING tasks when check_in date changes.

    Flow:
      1. SELECT * FROM tasks WHERE booking_id=... AND tenant_id=...
         AND kind IN ('CHECKIN_PREP', 'CLEANING') AND status NOT IN ('COMPLETED', 'CANCELED')
      2. actions_for_booking_amended(booking_id, new_check_in, existing_tasks)
      3. UPDATE tasks SET due_date=new_check_in, updated_at=now()
         WHERE task_id=... AND tenant_id=...

    Returns:
        Number of tasks successfully rescheduled (0 on error or if no change needed).

    Raises:
        Never. All errors are logged and swallowed (best-effort pattern).
    """
    try:
        db = client or _get_supabase_client()

        # Fetch active CHECKIN_PREP and CLEANING tasks for this booking
        result = (
            db.table("tasks")
            .select("*")
            .eq("booking_id", booking_id)
            .eq("tenant_id", tenant_id)
            .in_("kind", ["CHECKIN_PREP", "CLEANING"])
            .not_.in_("status", [TaskStatus.COMPLETED.value, TaskStatus.CANCELED.value])
            .execute()
        )
        rows = result.data or []
        if not rows:
            logger.info(
                "task_writer: no active tasks to reschedule for booking_id=%s new_check_in=%s",
                booking_id, new_check_in,
            )
            return 0

        # Reconstruct Task objects from DB rows for task_automator
        from tasks.task_model import TaskKind, TaskPriority, TaskStatus as TS, WorkerRole
        existing_tasks: list[Task] = []
        for row in rows:
            existing_tasks.append(
                Task(
                    task_id=row["task_id"],
                    kind=TaskKind(row["kind"]),
                    status=TS(row["status"]),
                    priority=TaskPriority(row["priority"]),
                    urgency=row["urgency"],
                    worker_role=WorkerRole(row["worker_role"]),
                    ack_sla_minutes=row["ack_sla_minutes"],
                    tenant_id=row["tenant_id"],
                    booking_id=row["booking_id"],
                    property_id=row["property_id"],
                    due_date=row["due_date"],
                    title=row["title"],
                    description=row.get("description"),
                    assigned_to=row.get("assigned_to"),
                    notes=row.get("notes") or [],
                    canceled_reason=row.get("canceled_reason"),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
            )

        actions: list[TaskRescheduleAction] = actions_for_booking_amended(
            booking_id=booking_id,
            new_check_in=new_check_in,
            existing_tasks=existing_tasks,
        )

        if not actions:
            logger.info(
                "task_writer: no reschedule needed for booking_id=%s (new_check_in=%s already matches)",
                booking_id, new_check_in,
            )
            return 0

        now = datetime.now(tz=timezone.utc).isoformat()
        rescheduled = 0

        # Phase 1030-guard: If any rescheduled task has no assigned worker,
        # try to heal the assignment using the current Primary for this property.
        assignment_map = {}
        unassigned_tasks = [t for t in existing_tasks if not t.assigned_to and t.task_id in {a.task_id for a in actions}]
        if unassigned_tasks:
            try:
                property_id = existing_tasks[0].property_id
                result_assign = (
                    db.table("staff_property_assignments")
                    .select("user_id, priority")
                    .eq("tenant_id", tenant_id)
                    .eq("property_id", property_id)
                    .order("priority", desc=False)
                    .execute()
                )
                assigned_user_ids = [r["user_id"] for r in (result_assign.data or [])]
                if assigned_user_ids:
                    result_perms = (
                        db.table("tenant_permissions")
                        .select("user_id, worker_roles")
                        .eq("tenant_id", tenant_id)
                        .in_("user_id", assigned_user_ids)
                        .execute()
                    )
                    user_roles_map = {r["user_id"]: (r.get("worker_roles") or []) for r in (result_perms.data or [])}
                    roles_needed = {t.worker_role.value for t in unassigned_tasks}
                    for role_val in roles_needed:
                        role_normalized = role_val.lower()
                        for uid in assigned_user_ids:
                            if role_normalized in user_roles_map.get(uid, []):
                                assignment_map[role_val] = uid
                                break
            except Exception as _exc:
                logger.warning("task_writer: failed to build healing assignment_map for amended booking_id=%s: %s", booking_id, _exc)

        for action in actions:
            update_payload = {"due_date": action.new_due_date, "updated_at": now}
            
            task_obj = next((t for t in existing_tasks if t.task_id == action.task_id), None)
            if task_obj and not task_obj.assigned_to:
                healed_worker = assignment_map.get(task_obj.worker_role.value)
                if healed_worker:
                    update_payload["assigned_to"] = healed_worker
                    logger.info("task_writer: healed unassigned task=%s (role=%s) during amendment", action.task_id, task_obj.worker_role.value)

            db.table("tasks").update(
                update_payload
            ).eq("task_id", action.task_id).eq("tenant_id", tenant_id).execute()
            rescheduled += 1

        logger.info(
            "task_writer: rescheduled %d tasks for BOOKING_AMENDED booking_id=%s new_check_in=%s",
            rescheduled, booking_id, new_check_in,
        )
        return rescheduled

    except Exception as exc:  # noqa: BLE001
        logger.error(
            "task_writer: reschedule_tasks_for_booking_amended failed booking_id=%s: %s",
            booking_id, exc,
        )
        return 0
