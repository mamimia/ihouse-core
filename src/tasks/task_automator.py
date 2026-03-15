"""
Task Automator — Phase 112

Rule engine that automatically emits Tasks from booking lifecycle events.

Architecture constraints:
- This module is READ-ONLY from the booking perspective. It reads
  booking data passed by the caller and emits Task objects.
- It NEVER writes to booking_state, event_log, or any Supabase table.
- It NEVER reads from the database directly — all input is passed by the caller.
- Task creation is deterministic: same input always produces the same task_id.
  (sha256(kind:booking_id:property_id)[:16] — inherited from task_model)

Automation rules (locked at Phase 112, enhanced Phase 634):

  BOOKING_CREATED:
    → CHECKIN_PREP task      (priority: HIGH,   due: check_in date)
    → CLEANING task          (priority: MEDIUM, due: check_in date, for turnover prep)
    → CHECKOUT_VERIFY task   (priority: MEDIUM, due: check_out date) [Phase 634]

  BOOKING_CANCELED:
    → Cancel all PENDING tasks for this booking_id
      Returns TaskCancelAction for each task_id that should be canceled.
      (Caller is responsible for persisting the cancellation — this module
      only declares intent via TaskCancelAction.)

  BOOKING_AMENDED (dates changed):
    → If check_in changed: reschedule CHECKIN_PREP + CLEANING due_date
    → If check_out changed: reschedule CHECKOUT_VERIFY due_date [Phase 634]
      Returns TaskRescheduleAction for each affected task.
      Only emitted if new date differs from current task due_date.

Entry points:
  tasks_for_booking_created(payload) -> List[Task]
  actions_for_booking_canceled(booking_id, pending_task_ids) -> List[TaskCancelAction]
  actions_for_booking_amended(payload, existing_tasks) -> List[TaskRescheduleAction]
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from tasks.task_model import (
    Task,
    TaskKind,
    TaskPriority,
    TaskStatus,
)


# ---------------------------------------------------------------------------
# Supporting action types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TaskCancelAction:
    """
    Declares that a task should be canceled due to BOOKING_CANCELED.

    The caller (task router / worker / scheduler) applies the actual
    status transition. This module only produces the action.
    """
    task_id: str
    booking_id: str
    reason: str = "Booking canceled"


@dataclass(frozen=True)
class TaskRescheduleAction:
    """
    Declares that a task's due_date should be updated due to BOOKING_AMENDED.

    The caller applies the actual update. This module only declares intent.
    """
    task_id: str
    booking_id: str
    kind: TaskKind
    old_due_date: str
    new_due_date: str


# ---------------------------------------------------------------------------
# Rule: BOOKING_CREATED
# ---------------------------------------------------------------------------

def tasks_for_booking_created(
    tenant_id: str,
    booking_id: str,
    property_id: str,
    check_in: str,
    source: str = "unknown",
    created_at: Optional[str] = None,
    check_out: Optional[str] = None,
) -> List[Task]:
    """
    Emit tasks for a BOOKING_CREATED event.

    Rules (locked Phase 112, enhanced Phase 634):
      - CHECKIN_PREP task:    priority HIGH,   due_date = check_in
      - CLEANING task:        priority MEDIUM, due_date = check_in
      - CHECKOUT_VERIFY task: priority MEDIUM, due_date = check_out [Phase 634]

    Args:
        tenant_id:   Owning tenant.
        booking_id:  Canonical booking_id (e.g. "bookingcom_R001").
        property_id: Property this booking applies to.
        check_in:    ISO 8601 date string for check_in (YYYY-MM-DD).
        source:      OTA provider name (for title context).
        created_at:  ISO 8601 UTC timestamp. Defaults to now.
        check_out:   ISO 8601 date string for check_out (YYYY-MM-DD). If None,
                     CHECKOUT_VERIFY task is not created.

    Returns:
        List of Tasks: [CHECKIN_PREP, CLEANING, CHECKOUT_VERIFY*], in this order.
        *CHECKOUT_VERIFY only if check_out is provided.
    """
    # Guard: iCal-sourced bookings are low-confidence signals (observed/blocked).
    # Do not auto-create tasks — they may not be real confirmed bookings.
    if source == "ical":
        return []

    if created_at is None:
        created_at = datetime.now(tz=timezone.utc).isoformat()

    checkin_prep = Task.build(
        kind=TaskKind.CHECKIN_PREP,
        tenant_id=tenant_id,
        booking_id=booking_id,
        property_id=property_id,
        due_date=check_in,
        title=f"Check-in prep for {booking_id}",
        created_at=created_at,
        priority=TaskPriority.HIGH,
    )

    cleaning = Task.build(
        kind=TaskKind.CLEANING,
        tenant_id=tenant_id,
        booking_id=booking_id,
        property_id=property_id,
        due_date=check_in,
        title=f"Pre-arrival cleaning for {booking_id}",
        created_at=created_at,
        priority=TaskPriority.MEDIUM,
    )

    tasks = [checkin_prep, cleaning]

    # Phase 634 — CHECKOUT_VERIFY task
    if check_out:
        checkout_verify = Task.build(
            kind=TaskKind.CHECKOUT_VERIFY,
            tenant_id=tenant_id,
            booking_id=booking_id,
            property_id=property_id,
            due_date=check_out,
            title=f"Checkout verification for {booking_id}",
            created_at=created_at,
            priority=TaskPriority.MEDIUM,
        )
        tasks.append(checkout_verify)

    return tasks


# ---------------------------------------------------------------------------
# Rule: BOOKING_CANCELED
# ---------------------------------------------------------------------------

def actions_for_booking_canceled(
    booking_id: str,
    pending_task_ids: List[str],
    reason: str = "Booking canceled",
) -> List[TaskCancelAction]:
    """
    Emit cancel actions for all PENDING tasks belonging to a canceled booking.

    Only PENDING tasks should be canceled. ACKNOWLEDGED, IN_PROGRESS, COMPLETED,
    and already CANCELED tasks are not affected — the caller is responsible for
    filtering before passing pending_task_ids.

    Args:
        booking_id:       The booking that was canceled.
        pending_task_ids: task_ids of all PENDING tasks for this booking.
        reason:           Cancellation reason string (default: "Booking canceled").

    Returns:
        One TaskCancelAction per task_id in pending_task_ids.
        Returns empty list if pending_task_ids is empty.
    """
    return [
        TaskCancelAction(
            task_id=tid,
            booking_id=booking_id,
            reason=reason,
        )
        for tid in pending_task_ids
    ]


# ---------------------------------------------------------------------------
# Rule: BOOKING_AMENDED
# ---------------------------------------------------------------------------

def actions_for_booking_amended(
    booking_id: str,
    new_check_in: str,
    existing_tasks: List[Task],
    new_check_out: Optional[str] = None,
) -> List[TaskRescheduleAction]:
    """
    Emit reschedule actions when booking dates change.

    Phase 112 (locked): CHECKIN_PREP + CLEANING rescheduled when check_in changes.
    Phase 634: CHECKOUT_VERIFY rescheduled when check_out changes.

    Only affects tasks whose status is not terminal (COMPLETED or CANCELED)
    and whose due_date differs from the new date.

    Args:
        booking_id:     The booking that was amended.
        new_check_in:   The new check_in date (YYYY-MM-DD).
        existing_tasks: All existing Task objects for this booking.
        new_check_out:  The new check_out date (YYYY-MM-DD). Optional.

    Returns:
        TaskRescheduleAction for each affected task.
        Returns empty list if no rescheduling is needed.
    """
    checkin_kinds = {TaskKind.CHECKIN_PREP, TaskKind.CLEANING}
    actions = []

    for task in existing_tasks:
        if task.booking_id != booking_id:
            continue
        if task.is_terminal():
            continue

        # Check-in related tasks
        if task.kind in checkin_kinds and task.due_date != new_check_in:
            actions.append(
                TaskRescheduleAction(
                    task_id=task.task_id,
                    booking_id=booking_id,
                    kind=task.kind,
                    old_due_date=task.due_date,
                    new_due_date=new_check_in,
                )
            )

        # Phase 634 — Check-out related tasks
        if (
            task.kind == TaskKind.CHECKOUT_VERIFY
            and new_check_out
            and task.due_date != new_check_out
        ):
            actions.append(
                TaskRescheduleAction(
                    task_id=task.task_id,
                    booking_id=booking_id,
                    kind=task.kind,
                    old_due_date=task.due_date,
                    new_due_date=new_check_out,
                )
            )

    return actions
