"""
Task System Model — Phase 111

Defines the core data model for the iHouse Core task system.

Architecture constraints:
- This module is a pure data model — no DB reads/writes, no external calls.
- Tasks are used to communicate work items to field workers (cleaning, check-in
  prep, checkout verification, maintenance). External channel delivery
  (WhatsApp / LINE / Telegram / SMS) is deferred to future phases.
- Task creation is driven by booking lifecycle events (Phase 112).
  This module only defines the model; it never reads from booking_state.

Task lifecycle:
    PENDING → ACKNOWLEDGED → IN_PROGRESS → COMPLETED
    PENDING → CANCELED
    ACKNOWLEDGED → CANCELED
    IN_PROGRESS → COMPLETED | CANCELED

From worker-communication-layer.md (locked):
  - Every task has an ackowledgement SLA (ack_sla_minutes).
  - CRITICAL tasks have a fixed 5-minute ACK SLA (per escalation engine spec).
  - task_id is deterministic: sha256(kind:booking_id:property_id)[:16]
  - Each task has a single assigned worker_role.
  - urgency is a string label ("normal" / "urgent" / "critical") used
    for display; TaskPriority is the canonical machine-readable equivalent.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TaskKind(str, Enum):
    """
    Classification of work items that can be assigned to field workers.

    Each kind denotes the type of operational action required at a property.
    """

    CLEANING = "CLEANING"
    """
    Property cleaning required between or before a booking.
    Typical trigger: BOOKING_CANCELED (early) or BOOKING_CREATED (turnover prep).
    """

    CHECKIN_PREP = "CHECKIN_PREP"
    """
    Pre-arrival property preparation: keys ready, amenities stocked, etc.
    Typical trigger: BOOKING_CREATED.
    """

    CHECKOUT_VERIFY = "CHECKOUT_VERIFY"
    """
    Post-departure inspection: check for damage, missing items, property state.
    Typical trigger: check_out date reached.
    """

    MAINTENANCE = "MAINTENANCE"
    """
    Ad-hoc maintenance task (repair, replacement, inspection).
    Typically created manually or from a maintenance flag.
    """

    GENERAL = "GENERAL"
    """
    General or miscellaneous task not covered by other kinds.
    Used as a catch-all for operator-created tasks.
    """

    GUEST_WELCOME = "GUEST_WELCOME"
    """
    Pre-arrival guest welcome preparation, informed by the linked guest profile.
    Includes personalized title/description from guest name and special_requests.
    Typical trigger: manual operator action or booking with linked guest (Phase 206).
    """


class TaskStatus(str, Enum):
    """
    Lifecycle state of a task.

    Valid transitions (enforced at Phase 113 write endpoint):
        PENDING → ACKNOWLEDGED → IN_PROGRESS → COMPLETED
        PENDING → CANCELED
        ACKNOWLEDGED → CANCELED
        IN_PROGRESS → COMPLETED | CANCELED
    """

    PENDING = "PENDING"
    """Task created, not yet acknowledged by a worker."""

    ACKNOWLEDGED = "ACKNOWLEDGED"
    """Worker has confirmed receipt of the task."""

    IN_PROGRESS = "IN_PROGRESS"
    """Worker has started executing the task."""

    COMPLETED = "COMPLETED"
    """Task has been completed. Terminal state."""

    CANCELED = "CANCELED"
    """Task was canceled (e.g., booking canceled). Terminal state."""


class TaskPriority(str, Enum):
    """
    Priority level for a task.

    Maps to display urgency labels per worker-communication-layer.md:
        LOW     → "normal"
        MEDIUM  → "normal"
        HIGH    → "urgent"
        CRITICAL → "critical"

    Note: CRITICAL tasks have a fixed 5-minute ACK SLA per the escalation
    engine specification locked in Phase 91.
    """

    LOW = "LOW"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    CRITICAL = "CRITICAL"


class WorkerRole(str, Enum):
    """
    Role designation for workers who receive task assignments.

    Worker roles determine which communication channel and SLA apply.
    """

    CLEANER = "CLEANER"
    """Housekeeping / cleaning staff."""

    PROPERTY_MANAGER = "PROPERTY_MANAGER"
    """On-site or remote property manager."""

    MAINTENANCE_TECH = "MAINTENANCE_TECH"
    """Maintenance technician for repairs and upkeep."""

    INSPECTOR = "INSPECTOR"
    """Quality inspector for checkout verification."""

    GENERAL_STAFF = "GENERAL_STAFF"
    """General operations staff for miscellaneous tasks."""


# ---------------------------------------------------------------------------
# Priority → urgency label map (locked)
# ---------------------------------------------------------------------------

#: Canonical display urgency label for each TaskPriority.
#: Locked per worker-communication-layer.md.
PRIORITY_URGENCY: dict[TaskPriority, str] = {
    TaskPriority.LOW: "normal",
    TaskPriority.MEDIUM: "normal",
    TaskPriority.HIGH: "urgent",
    TaskPriority.CRITICAL: "critical",
}

#: Acknowledgement SLA in minutes per priority (locked per escalation spec Phase 91).
#: CRITICAL is fixed at 5 minutes per the SLA escalation engine.
PRIORITY_ACK_SLA_MINUTES: dict[TaskPriority, int] = {
    TaskPriority.LOW: 240,       # 4 hours
    TaskPriority.MEDIUM: 60,     # 1 hour
    TaskPriority.HIGH: 15,       # 15 minutes
    TaskPriority.CRITICAL: 5,    # 5 minutes — LOCKED, do not change
}

#: Default worker role for each task kind.
KIND_DEFAULT_WORKER_ROLE: dict[TaskKind, WorkerRole] = {
    TaskKind.CLEANING: WorkerRole.CLEANER,
    TaskKind.CHECKIN_PREP: WorkerRole.PROPERTY_MANAGER,
    TaskKind.CHECKOUT_VERIFY: WorkerRole.INSPECTOR,
    TaskKind.MAINTENANCE: WorkerRole.MAINTENANCE_TECH,
    TaskKind.GENERAL: WorkerRole.GENERAL_STAFF,
    TaskKind.GUEST_WELCOME: WorkerRole.PROPERTY_MANAGER,
}

#: Default priority for each task kind.
KIND_DEFAULT_PRIORITY: dict[TaskKind, TaskPriority] = {
    TaskKind.CLEANING: TaskPriority.MEDIUM,
    TaskKind.CHECKIN_PREP: TaskPriority.HIGH,
    TaskKind.CHECKOUT_VERIFY: TaskPriority.MEDIUM,
    TaskKind.MAINTENANCE: TaskPriority.MEDIUM,
    TaskKind.GENERAL: TaskPriority.LOW,
    TaskKind.GUEST_WELCOME: TaskPriority.HIGH,
}

#: Valid status transitions. Key = current state, value = allowed next states.
VALID_TASK_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.PENDING: frozenset({TaskStatus.ACKNOWLEDGED, TaskStatus.CANCELED}),
    TaskStatus.ACKNOWLEDGED: frozenset({TaskStatus.IN_PROGRESS, TaskStatus.CANCELED}),
    TaskStatus.IN_PROGRESS: frozenset({TaskStatus.COMPLETED, TaskStatus.CANCELED}),
    TaskStatus.COMPLETED: frozenset(),     # terminal
    TaskStatus.CANCELED: frozenset(),      # terminal
}

#: Terminal statuses — no further transitions allowed.
TERMINAL_STATUSES: frozenset[TaskStatus] = frozenset({
    TaskStatus.COMPLETED,
    TaskStatus.CANCELED,
})


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------

def _make_task_id(kind: TaskKind, booking_id: str, property_id: str) -> str:
    """
    Generate a deterministic task_id from kind + booking_id + property_id.

    Uses the first 16 hex characters of SHA-256(kind:booking_id:property_id).
    Deterministic: same inputs always produce the same task_id.
    Not a security hash — used for deduplication and display only.
    """
    raw = f"{kind.value}:{booking_id}:{property_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Core Task dataclass
# ---------------------------------------------------------------------------

@dataclass
class Task:
    """
    A single work item assigned to a field worker.

    Fields:
        task_id         Deterministic 16-char hex: sha256(kind:booking_id:property_id)[:16]
        kind            What type of work is needed (TaskKind)
        status          Current lifecycle state (TaskStatus)
        priority        Urgency level (TaskPriority)
        urgency         Display label derived from priority ("normal"/"urgent"/"critical")
        worker_role     Which worker role should receive this task (WorkerRole)
        ack_sla_minutes How many minutes the worker has to acknowledge (int)
        tenant_id       The tenant that owns this task
        booking_id      The booking that triggered this task (canonical booking_id format)
        property_id     The property this task applies to
        due_date        ISO 8601 date the task should be completed by (YYYY-MM-DD)
        title           Short human-readable task title
        description     Optional detailed task description
        created_at      ISO 8601 UTC timestamp when the task was created
        updated_at      ISO 8601 UTC timestamp of last status change
        notes           Optional list of operator/worker notes (append-only in spirit)
        canceled_reason Optional cancellation reason (set when status → CANCELED)
    """

    task_id: str
    kind: TaskKind
    status: TaskStatus
    priority: TaskPriority
    urgency: str
    worker_role: WorkerRole
    ack_sla_minutes: int
    tenant_id: str
    booking_id: str
    property_id: str
    due_date: str
    title: str
    created_at: str
    updated_at: str
    description: Optional[str] = None
    notes: List[str] = field(default_factory=list)
    canceled_reason: Optional[str] = None

    @classmethod
    def build(
        cls,
        kind: TaskKind,
        tenant_id: str,
        booking_id: str,
        property_id: str,
        due_date: str,
        title: str,
        created_at: str,
        priority: Optional[TaskPriority] = None,
        worker_role: Optional[WorkerRole] = None,
        description: Optional[str] = None,
    ) -> "Task":
        """
        Factory method. Auto-derives:
        - task_id from kind + booking_id + property_id
        - priority from KIND_DEFAULT_PRIORITY if not provided
        - worker_role from KIND_DEFAULT_WORKER_ROLE if not provided
        - urgency from PRIORITY_URGENCY canonical map
        - ack_sla_minutes from PRIORITY_ACK_SLA_MINUTES canonical map

        Initial status is always PENDING.
        """
        resolved_priority = priority if priority is not None else KIND_DEFAULT_PRIORITY[kind]
        resolved_role = worker_role if worker_role is not None else KIND_DEFAULT_WORKER_ROLE[kind]

        return cls(
            task_id=_make_task_id(kind, booking_id, property_id),
            kind=kind,
            status=TaskStatus.PENDING,
            priority=resolved_priority,
            urgency=PRIORITY_URGENCY[resolved_priority],
            worker_role=resolved_role,
            ack_sla_minutes=PRIORITY_ACK_SLA_MINUTES[resolved_priority],
            tenant_id=tenant_id,
            booking_id=booking_id,
            property_id=property_id,
            due_date=due_date,
            title=title,
            created_at=created_at,
            updated_at=created_at,
            description=description,
        )

    def is_terminal(self) -> bool:
        """Return True if this task is in a terminal state (COMPLETED or CANCELED)."""
        return self.status in TERMINAL_STATUSES

    def allowed_next_statuses(self) -> frozenset[TaskStatus]:
        """Return the set of valid next statuses from the current status."""
        return VALID_TASK_TRANSITIONS.get(self.status, frozenset())

    def can_transition_to(self, next_status: TaskStatus) -> bool:
        """Return True if transitioning to next_status is allowed from current status."""
        return next_status in self.allowed_next_statuses()

    def with_status(self, new_status: TaskStatus, updated_at: str,
                    canceled_reason: Optional[str] = None) -> "Task":
        """
        Return a new Task with updated status and updated_at timestamp.

        Does NOT enforce transition validity — the caller must check
        can_transition_to() before calling this method.
        """
        import dataclasses
        return dataclasses.replace(
            self,
            status=new_status,
            updated_at=updated_at,
            canceled_reason=canceled_reason if new_status == TaskStatus.CANCELED else self.canceled_reason,
        )
