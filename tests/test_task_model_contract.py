"""
Phase 111 — Task System Foundation contract tests.

Tests the task_model.py module:
  - TaskKind enum (5 values)
  - TaskStatus enum (5 values)
  - TaskPriority enum (4 values)
  - WorkerRole enum (8 values — 5 original + CHECKIN, CHECKOUT, MAINTENANCE)
  - Canonical mapping tables (urgency, ack_sla_minutes, roles, priorities, transitions)
  - Task.build() factory
  - Task.is_terminal(), can_transition_to(), with_status()
  - task_id determinism

Groups:
  A — Enum completeness
  B — Canonical mapping tables
  C — Task.build() factory (field derivation, defaults, overrides)
  D — task_id determinism
  E — Lifecycle helpers (is_terminal, can_transition_to, allowed_next_statuses)
  F — Task.with_status() (transitions, canceled_reason handling)
  G — CRITICAL ACK SLA is exactly 5 minutes (locked invariant)
  H — Urgency label derivation
  I — Terminal status invariants
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# Group A — Enum completeness
# ---------------------------------------------------------------------------

class TestEnumCompleteness:

    def test_task_kind_has_5_values(self):
        from tasks.task_model import TaskKind
        assert len(TaskKind) == 6  # +GUEST_WELCOME (Phase 206)

    def test_task_kind_values(self):
        from tasks.task_model import TaskKind
        expected = {"CLEANING", "CHECKIN_PREP", "CHECKOUT_VERIFY", "MAINTENANCE", "GENERAL", "GUEST_WELCOME"}
        actual = {k.value for k in TaskKind}
        assert actual == expected

    def test_task_status_has_5_values(self):
        from tasks.task_model import TaskStatus
        assert len(TaskStatus) == 5

    def test_task_status_values(self):
        from tasks.task_model import TaskStatus
        expected = {"PENDING", "ACKNOWLEDGED", "IN_PROGRESS", "COMPLETED", "CANCELED"}
        actual = {s.value for s in TaskStatus}
        assert actual == expected

    def test_task_priority_has_4_values(self):
        from tasks.task_model import TaskPriority
        assert len(TaskPriority) == 4

    def test_task_priority_values(self):
        from tasks.task_model import TaskPriority
        expected = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        actual = {p.value for p in TaskPriority}
        assert actual == expected

    def test_worker_role_has_8_values(self):
        from tasks.task_model import WorkerRole
        assert len(WorkerRole) == 8

    def test_worker_role_values(self):
        from tasks.task_model import WorkerRole
        expected = {"CLEANER", "PROPERTY_MANAGER", "MAINTENANCE_TECH", "INSPECTOR", "GENERAL_STAFF", "CHECKIN", "CHECKOUT", "MAINTENANCE"}
        actual = {r.value for r in WorkerRole}
        assert actual == expected

    def test_enums_are_str_subclass(self):
        """All enums inherit from str — they serialize cleanly to JSON."""
        from tasks.task_model import TaskKind, TaskStatus, TaskPriority, WorkerRole
        for enum_cls in (TaskKind, TaskStatus, TaskPriority, WorkerRole):
            for member in enum_cls:
                assert isinstance(member, str), f"{enum_cls.__name__}.{member.name} is not str"


# ---------------------------------------------------------------------------
# Group B — Canonical mapping tables
# ---------------------------------------------------------------------------

class TestMappingTables:

    def test_priority_urgency_covers_all_priorities(self):
        from tasks.task_model import TaskPriority, PRIORITY_URGENCY
        for p in TaskPriority:
            assert p in PRIORITY_URGENCY, f"PRIORITY_URGENCY missing {p}"

    def test_priority_ack_sla_covers_all_priorities(self):
        from tasks.task_model import TaskPriority, PRIORITY_ACK_SLA_MINUTES
        for p in TaskPriority:
            assert p in PRIORITY_ACK_SLA_MINUTES, f"PRIORITY_ACK_SLA_MINUTES missing {p}"

    def test_kind_default_worker_role_covers_all_kinds(self):
        from tasks.task_model import TaskKind, KIND_DEFAULT_WORKER_ROLE
        for k in TaskKind:
            assert k in KIND_DEFAULT_WORKER_ROLE, f"KIND_DEFAULT_WORKER_ROLE missing {k}"

    def test_kind_default_priority_covers_all_kinds(self):
        from tasks.task_model import TaskKind, KIND_DEFAULT_PRIORITY
        for k in TaskKind:
            assert k in KIND_DEFAULT_PRIORITY, f"KIND_DEFAULT_PRIORITY missing {k}"

    def test_valid_transitions_covers_all_statuses(self):
        from tasks.task_model import TaskStatus, VALID_TASK_TRANSITIONS
        for s in TaskStatus:
            assert s in VALID_TASK_TRANSITIONS, f"VALID_TASK_TRANSITIONS missing {s}"

    def test_terminal_statuses_are_completed_and_canceled(self):
        from tasks.task_model import TaskStatus, TERMINAL_STATUSES
        assert TaskStatus.COMPLETED in TERMINAL_STATUSES
        assert TaskStatus.CANCELED in TERMINAL_STATUSES
        assert len(TERMINAL_STATUSES) == 2

    def test_terminal_statuses_have_no_transitions(self):
        from tasks.task_model import TaskStatus, VALID_TASK_TRANSITIONS
        for ts in (TaskStatus.COMPLETED, TaskStatus.CANCELED):
            assert VALID_TASK_TRANSITIONS[ts] == frozenset()

    def test_urgency_labels_are_valid_strings(self):
        from tasks.task_model import PRIORITY_URGENCY
        valid = {"normal", "urgent", "critical"}
        for label in PRIORITY_URGENCY.values():
            assert label in valid, f"Unexpected urgency label: {label!r}"

    def test_ack_sla_minutes_are_positive_integers(self):
        from tasks.task_model import PRIORITY_ACK_SLA_MINUTES
        for priority, minutes in PRIORITY_ACK_SLA_MINUTES.items():
            assert isinstance(minutes, int), f"{priority} SLA is not int"
            assert minutes > 0, f"{priority} SLA is not positive"


# ---------------------------------------------------------------------------
# Group C — Task.build() factory
# ---------------------------------------------------------------------------

class TestTaskBuild:

    def _build(self, kind=None, priority=None, worker_role=None):
        from tasks.task_model import Task, TaskKind
        return Task.build(
            kind=kind or TaskKind.CLEANING,
            tenant_id="tenant_test",
            booking_id="bookingcom_R001",
            property_id="prop_001",
            due_date="2026-04-05",
            title="Clean property before check-in",
            created_at="2026-03-09T10:00:00+00:00",
            priority=priority,
            worker_role=worker_role,
        )

    def test_build_returns_task(self):
        from tasks.task_model import Task
        task = self._build()
        assert isinstance(task, Task)

    def test_initial_status_is_pending(self):
        from tasks.task_model import TaskStatus
        task = self._build()
        assert task.status == TaskStatus.PENDING

    def test_default_priority_for_cleaning_is_medium(self):
        from tasks.task_model import TaskPriority, TaskKind
        task = self._build(kind=TaskKind.CLEANING)
        assert task.priority == TaskPriority.MEDIUM

    def test_default_priority_for_checkin_prep_is_high(self):
        from tasks.task_model import TaskPriority, TaskKind
        task = self._build(kind=TaskKind.CHECKIN_PREP)
        assert task.priority == TaskPriority.HIGH

    def test_default_worker_role_for_cleaning_is_cleaner(self):
        from tasks.task_model import WorkerRole, TaskKind
        task = self._build(kind=TaskKind.CLEANING)
        assert task.worker_role == WorkerRole.CLEANER

    def test_default_worker_role_for_checkin_prep_is_checkin(self):
        from tasks.task_model import WorkerRole, TaskKind
        task = self._build(kind=TaskKind.CHECKIN_PREP)
        assert task.worker_role == WorkerRole.CHECKIN

    def test_default_worker_role_for_checkout_verify_is_checkout(self):
        from tasks.task_model import WorkerRole, TaskKind
        task = self._build(kind=TaskKind.CHECKOUT_VERIFY)
        assert task.worker_role == WorkerRole.CHECKOUT

    def test_override_priority_respected(self):
        from tasks.task_model import TaskPriority
        task = self._build(priority=TaskPriority.CRITICAL)
        assert task.priority == TaskPriority.CRITICAL

    def test_override_worker_role_respected(self):
        from tasks.task_model import WorkerRole
        task = self._build(worker_role=WorkerRole.MAINTENANCE_TECH)
        assert task.worker_role == WorkerRole.MAINTENANCE_TECH

    def test_task_id_is_non_empty_hex(self):
        task = self._build()
        assert len(task.task_id) == 16
        int(task.task_id, 16)  # must be parseable as hex

    def test_urgency_derived_from_priority(self):
        from tasks.task_model import TaskPriority, PRIORITY_URGENCY
        task = self._build(priority=TaskPriority.HIGH)
        assert task.urgency == PRIORITY_URGENCY[TaskPriority.HIGH]
        assert task.urgency == "urgent"

    def test_ack_sla_minutes_derived_from_priority(self):
        from tasks.task_model import TaskPriority, PRIORITY_ACK_SLA_MINUTES
        task = self._build(priority=TaskPriority.MEDIUM)
        assert task.ack_sla_minutes == PRIORITY_ACK_SLA_MINUTES[TaskPriority.MEDIUM]

    def test_tenant_booking_property_set_correctly(self):
        task = self._build()
        assert task.tenant_id == "tenant_test"
        assert task.booking_id == "bookingcom_R001"
        assert task.property_id == "prop_001"

    def test_due_date_and_title_set(self):
        task = self._build()
        assert task.due_date == "2026-04-05"
        assert task.title == "Clean property before check-in"

    def test_created_at_and_updated_at_equal_on_build(self):
        task = self._build()
        assert task.created_at == task.updated_at

    def test_notes_defaults_to_empty_list(self):
        task = self._build()
        assert task.notes == []

    def test_canceled_reason_defaults_to_none(self):
        task = self._build()
        assert task.canceled_reason is None


# ---------------------------------------------------------------------------
# Group D — task_id determinism
# ---------------------------------------------------------------------------

class TestTaskIdDeterminism:

    def test_same_inputs_produce_same_task_id(self):
        from tasks.task_model import Task, TaskKind
        kwargs = dict(
            kind=TaskKind.CLEANING,
            tenant_id="t1",
            booking_id="bookingcom_R001",
            property_id="prop_001",
            due_date="2026-04-05",
            title="Clean",
            created_at="2026-03-09T10:00:00+00:00",
        )
        t1 = Task.build(**kwargs)
        t2 = Task.build(**kwargs)
        assert t1.task_id == t2.task_id

    def test_different_kinds_produce_different_ids(self):
        from tasks.task_model import Task, TaskKind
        base = dict(
            tenant_id="t1",
            booking_id="bookingcom_R001",
            property_id="prop_001",
            due_date="2026-04-05",
            title="X",
            created_at="2026-03-09T10:00:00+00:00",
        )
        t_clean = Task.build(kind=TaskKind.CLEANING, **base)
        t_checkin = Task.build(kind=TaskKind.CHECKIN_PREP, **base)
        assert t_clean.task_id != t_checkin.task_id

    def test_different_booking_ids_produce_different_task_ids(self):
        from tasks.task_model import Task, TaskKind
        base = dict(
            kind=TaskKind.CLEANING,
            tenant_id="t1",
            property_id="prop_001",
            due_date="2026-04-05",
            title="X",
            created_at="2026-03-09T10:00:00+00:00",
        )
        t1 = Task.build(booking_id="bookingcom_R001", **base)
        t2 = Task.build(booking_id="bookingcom_R002", **base)
        assert t1.task_id != t2.task_id

    def test_task_id_length_is_16(self):
        from tasks.task_model import Task, TaskKind
        task = Task.build(
            kind=TaskKind.MAINTENANCE,
            tenant_id="t1",
            booking_id="b1",
            property_id="p1",
            due_date="2026-04-05",
            title="X",
            created_at="2026-03-09T10:00:00+00:00",
        )
        assert len(task.task_id) == 16


# ---------------------------------------------------------------------------
# Group E — Lifecycle helpers
# ---------------------------------------------------------------------------

class TestLifecycleHelpers:

    def _pending_task(self):
        from tasks.task_model import Task, TaskKind
        return Task.build(
            kind=TaskKind.CHECKIN_PREP,
            tenant_id="t1",
            booking_id="bookingcom_R001",
            property_id="prop_001",
            due_date="2026-04-05",
            title="Prep",
            created_at="2026-03-09T10:00:00+00:00",
        )

    def test_pending_is_not_terminal(self):
        task = self._pending_task()
        assert task.is_terminal() is False

    def test_completed_is_terminal(self):
        from tasks.task_model import TaskStatus
        import dataclasses
        task = dataclasses.replace(self._pending_task(), status=TaskStatus.COMPLETED)
        assert task.is_terminal() is True

    def test_canceled_is_terminal(self):
        from tasks.task_model import TaskStatus
        import dataclasses
        task = dataclasses.replace(self._pending_task(), status=TaskStatus.CANCELED)
        assert task.is_terminal() is True

    def test_in_progress_is_not_terminal(self):
        from tasks.task_model import TaskStatus
        import dataclasses
        task = dataclasses.replace(self._pending_task(), status=TaskStatus.IN_PROGRESS)
        assert task.is_terminal() is False

    def test_pending_can_transition_to_acknowledged(self):
        from tasks.task_model import TaskStatus
        task = self._pending_task()
        assert task.can_transition_to(TaskStatus.ACKNOWLEDGED) is True

    def test_pending_can_transition_to_canceled(self):
        from tasks.task_model import TaskStatus
        task = self._pending_task()
        assert task.can_transition_to(TaskStatus.CANCELED) is True

    def test_pending_cannot_transition_to_completed(self):
        from tasks.task_model import TaskStatus
        task = self._pending_task()
        assert task.can_transition_to(TaskStatus.COMPLETED) is False

    def test_pending_cannot_transition_to_in_progress(self):
        from tasks.task_model import TaskStatus
        task = self._pending_task()
        assert task.can_transition_to(TaskStatus.IN_PROGRESS) is False

    def test_completed_cannot_transition_to_anything(self):
        from tasks.task_model import TaskStatus
        import dataclasses
        task = dataclasses.replace(self._pending_task(), status=TaskStatus.COMPLETED)
        for s in TaskStatus:
            assert task.can_transition_to(s) is False

    def test_canceled_cannot_transition_to_anything(self):
        from tasks.task_model import TaskStatus
        import dataclasses
        task = dataclasses.replace(self._pending_task(), status=TaskStatus.CANCELED)
        for s in TaskStatus:
            assert task.can_transition_to(s) is False

    def test_allowed_next_statuses_for_pending(self):
        from tasks.task_model import TaskStatus
        task = self._pending_task()
        allowed = task.allowed_next_statuses()
        assert TaskStatus.ACKNOWLEDGED in allowed
        assert TaskStatus.CANCELED in allowed
        assert TaskStatus.COMPLETED not in allowed
        assert TaskStatus.IN_PROGRESS not in allowed


# ---------------------------------------------------------------------------
# Group F — Task.with_status()
# ---------------------------------------------------------------------------

class TestWithStatus:

    def _pending_task(self):
        from tasks.task_model import Task, TaskKind
        return Task.build(
            kind=TaskKind.CLEANING,
            tenant_id="t1",
            booking_id="bookingcom_R001",
            property_id="prop_001",
            due_date="2026-04-05",
            title="Clean",
            created_at="2026-03-09T10:00:00+00:00",
        )

    def test_with_status_returns_new_task(self):
        from tasks.task_model import TaskStatus
        task = self._pending_task()
        new_task = task.with_status(TaskStatus.ACKNOWLEDGED, "2026-03-09T11:00:00+00:00")
        assert new_task is not task

    def test_with_status_updates_status(self):
        from tasks.task_model import TaskStatus
        task = self._pending_task()
        new_task = task.with_status(TaskStatus.ACKNOWLEDGED, "2026-03-09T11:00:00+00:00")
        assert new_task.status == TaskStatus.ACKNOWLEDGED

    def test_with_status_updates_updated_at(self):
        from tasks.task_model import TaskStatus
        task = self._pending_task()
        ts = "2026-03-09T11:00:00+00:00"
        new_task = task.with_status(TaskStatus.ACKNOWLEDGED, ts)
        assert new_task.updated_at == ts

    def test_with_status_preserves_other_fields(self):
        from tasks.task_model import TaskStatus
        task = self._pending_task()
        new_task = task.with_status(TaskStatus.ACKNOWLEDGED, "2026-03-09T11:00:00+00:00")
        assert new_task.task_id == task.task_id
        assert new_task.booking_id == task.booking_id
        assert new_task.tenant_id == task.tenant_id
        assert new_task.kind == task.kind

    def test_with_status_canceled_sets_canceled_reason(self):
        from tasks.task_model import TaskStatus
        task = self._pending_task()
        new_task = task.with_status(TaskStatus.CANCELED, "2026-03-09T11:00:00+00:00",
                                     canceled_reason="Booking canceled")
        assert new_task.canceled_reason == "Booking canceled"
        assert new_task.status == TaskStatus.CANCELED

    def test_with_status_non_canceled_does_not_set_canceled_reason(self):
        from tasks.task_model import TaskStatus
        task = self._pending_task()
        new_task = task.with_status(TaskStatus.ACKNOWLEDGED, "2026-03-09T11:00:00+00:00",
                                     canceled_reason="ignored")
        assert new_task.canceled_reason is None

    def test_with_status_does_not_enforce_transition_validity(self):
        """with_status is dumb — validation is caller's responsibility."""
        from tasks.task_model import TaskStatus
        import dataclasses
        task = dataclasses.replace(self._pending_task(), status=TaskStatus.COMPLETED)
        # Should not raise — validation is external
        new_task = task.with_status(TaskStatus.PENDING, "2026-03-09T11:00:00+00:00")
        assert new_task.status == TaskStatus.PENDING


# ---------------------------------------------------------------------------
# Group G — CRITICAL ACK SLA invariant (LOCKED)
# ---------------------------------------------------------------------------

class TestCriticalAckSlaLocked:

    def test_critical_ack_sla_is_exactly_5_minutes(self):
        """
        LOCKED per escalation engine Phase 91.
        This value must never change.
        """
        from tasks.task_model import TaskPriority, PRIORITY_ACK_SLA_MINUTES
        assert PRIORITY_ACK_SLA_MINUTES[TaskPriority.CRITICAL] == 5

    def test_critical_urgency_label_is_critical(self):
        from tasks.task_model import TaskPriority, PRIORITY_URGENCY
        assert PRIORITY_URGENCY[TaskPriority.CRITICAL] == "critical"

    def test_critical_task_has_5_minute_sla_via_build(self):
        from tasks.task_model import Task, TaskKind, TaskPriority
        task = Task.build(
            kind=TaskKind.MAINTENANCE,
            tenant_id="t1",
            booking_id="b1",
            property_id="p1",
            due_date="2026-04-05",
            title="Urgent fix",
            created_at="2026-03-09T10:00:00+00:00",
            priority=TaskPriority.CRITICAL,
        )
        assert task.ack_sla_minutes == 5
        assert task.urgency == "critical"


# ---------------------------------------------------------------------------
# Group H — Urgency label derivation
# ---------------------------------------------------------------------------

class TestUrgencyDerivation:

    def test_low_priority_urgency_is_normal(self):
        from tasks.task_model import TaskPriority, PRIORITY_URGENCY
        assert PRIORITY_URGENCY[TaskPriority.LOW] == "normal"

    def test_medium_priority_urgency_is_normal(self):
        from tasks.task_model import TaskPriority, PRIORITY_URGENCY
        assert PRIORITY_URGENCY[TaskPriority.MEDIUM] == "normal"

    def test_high_priority_urgency_is_urgent(self):
        from tasks.task_model import TaskPriority, PRIORITY_URGENCY
        assert PRIORITY_URGENCY[TaskPriority.HIGH] == "urgent"

    def test_critical_priority_urgency_is_critical(self):
        from tasks.task_model import TaskPriority, PRIORITY_URGENCY
        assert PRIORITY_URGENCY[TaskPriority.CRITICAL] == "critical"


# ---------------------------------------------------------------------------
# Group I — Terminal status invariants
# ---------------------------------------------------------------------------

class TestTerminalStatusInvariants:

    def test_terminal_statuses_have_empty_transition_sets(self):
        from tasks.task_model import VALID_TASK_TRANSITIONS, TERMINAL_STATUSES
        for ts in TERMINAL_STATUSES:
            assert VALID_TASK_TRANSITIONS[ts] == frozenset(), \
                f"{ts} should have no transitions"

    def test_non_terminal_statuses_have_at_least_one_transition(self):
        from tasks.task_model import TaskStatus, VALID_TASK_TRANSITIONS, TERMINAL_STATUSES
        for s in TaskStatus:
            if s not in TERMINAL_STATUSES:
                assert len(VALID_TASK_TRANSITIONS[s]) >= 1, \
                    f"{s} should have at least one transition"

    def test_completed_not_reachable_from_pending(self):
        """PENDING → COMPLETED is not a valid transition (must go via ACKNOWLEDGED + IN_PROGRESS)."""
        from tasks.task_model import TaskStatus, VALID_TASK_TRANSITIONS
        assert TaskStatus.COMPLETED not in VALID_TASK_TRANSITIONS[TaskStatus.PENDING]

    def test_all_statuses_can_eventually_reach_a_terminal(self):
        """Every non-terminal status must have a path to CANCELED (escape hatch)."""
        from tasks.task_model import TaskStatus, VALID_TASK_TRANSITIONS, TERMINAL_STATUSES

        def can_reach_terminal(status, visited=None):
            if visited is None:
                visited = set()
            if status in visited:
                return False
            if status in TERMINAL_STATUSES:
                return True
            visited.add(status)
            return any(
                can_reach_terminal(next_s, visited.copy())
                for next_s in VALID_TASK_TRANSITIONS[status]
            )

        for s in TaskStatus:
            if s not in TERMINAL_STATUSES:
                assert can_reach_terminal(s), f"{s} cannot reach a terminal state"
