"""
Phase 112 — Task Automation from Booking Events contract tests.

Tests task_automator.py:
  - tasks_for_booking_created(...)     → [CHECKIN_PREP, CLEANING]
  - actions_for_booking_canceled(...)  → [TaskCancelAction, ...]
  - actions_for_booking_amended(...)   → [TaskRescheduleAction, ...]

Groups:
  A — BOOKING_CREATED: correct task types and count
  B — BOOKING_CREATED: field values (tenant_id, booking_id, due_date, status)
  C — BOOKING_CREATED: deterministic task_ids, priority, urgency
  D — BOOKING_CANCELED: cancels pending tasks
  E — BOOKING_CANCELED: skips empty list, reason field
  F — BOOKING_AMENDED: reschedules CHECKIN_PREP and CLEANING when date changes
  G — BOOKING_AMENDED: no action if date unchanged
  H — BOOKING_AMENDED: skips terminal tasks
  I — BOOKING_AMENDED: only affects CHECKIN_PREP and CLEANING (not MAINTENANCE)
  J — Pure-function invariants (no DB, no side effects, idempotent)
"""
from __future__ import annotations

from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task(kind_str, booking_id="bookingcom_R001", due_date="2026-04-05",
               status_str="PENDING", tenant_id="t1", property_id="prop_001"):
    from tasks.task_model import Task, TaskKind, TaskStatus
    import dataclasses
    task = Task.build(
        kind=TaskKind[kind_str],
        tenant_id=tenant_id,
        booking_id=booking_id,
        property_id=property_id,
        due_date=due_date,
        title=f"{kind_str} task",
        created_at="2026-03-09T10:00:00+00:00",
    )
    if status_str != "PENDING":
        task = dataclasses.replace(task, status=TaskStatus[status_str])
    return task


# ---------------------------------------------------------------------------
# Group A — BOOKING_CREATED: task types and count
# ---------------------------------------------------------------------------

class TestBookingCreatedTaskTypes:

    def test_returns_two_tasks(self):
        from tasks.task_automator import tasks_for_booking_created
        tasks = tasks_for_booking_created(
            tenant_id="t1",
            booking_id="bookingcom_R001",
            property_id="prop_001",
            check_in="2026-04-05",
        )
        assert len(tasks) == 2

    def test_first_task_is_checkin_prep(self):
        from tasks.task_automator import tasks_for_booking_created
        from tasks.task_model import TaskKind
        tasks = tasks_for_booking_created("t1", "bookingcom_R001", "prop_001", "2026-04-05")
        assert tasks[0].kind == TaskKind.CHECKIN_PREP

    def test_second_task_is_cleaning(self):
        from tasks.task_automator import tasks_for_booking_created
        from tasks.task_model import TaskKind
        tasks = tasks_for_booking_created("t1", "bookingcom_R001", "prop_001", "2026-04-05")
        assert tasks[1].kind == TaskKind.CLEANING

    def test_returns_list_type(self):
        from tasks.task_automator import tasks_for_booking_created
        result = tasks_for_booking_created("t1", "bookingcom_R001", "prop_001", "2026-04-05")
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Group B — BOOKING_CREATED: field values
# ---------------------------------------------------------------------------

class TestBookingCreatedFields:

    def _tasks(self):
        from tasks.task_automator import tasks_for_booking_created
        return tasks_for_booking_created(
            tenant_id="tenant_A",
            booking_id="bookingcom_R001",
            property_id="prop_X",
            check_in="2026-04-10",
            created_at="2026-03-09T10:00:00+00:00",
        )

    def test_tenant_id_set_on_all_tasks(self):
        for task in self._tasks():
            assert task.tenant_id == "tenant_A"

    def test_booking_id_set_on_all_tasks(self):
        for task in self._tasks():
            assert task.booking_id == "bookingcom_R001"

    def test_property_id_set_on_all_tasks(self):
        for task in self._tasks():
            assert task.property_id == "prop_X"

    def test_due_date_equals_check_in_for_all_tasks(self):
        for task in self._tasks():
            assert task.due_date == "2026-04-10"

    def test_all_tasks_start_pending(self):
        from tasks.task_model import TaskStatus
        for task in self._tasks():
            assert task.status == TaskStatus.PENDING

    def test_created_at_equals_updated_at(self):
        for task in self._tasks():
            assert task.created_at == task.updated_at

    def test_titles_contain_booking_id(self):
        for task in self._tasks():
            assert "bookingcom_R001" in task.title


# ---------------------------------------------------------------------------
# Group C — BOOKING_CREATED: determinism, priority, urgency
# ---------------------------------------------------------------------------

class TestBookingCreatedDeterminism:

    def test_task_ids_are_deterministic(self):
        from tasks.task_automator import tasks_for_booking_created
        t1 = tasks_for_booking_created("t1", "bookingcom_R001", "prop_001", "2026-04-05")
        t2 = tasks_for_booking_created("t1", "bookingcom_R001", "prop_001", "2026-04-05")
        for a, b in zip(t1, t2):
            assert a.task_id == b.task_id

    def test_checkin_prep_priority_is_high(self):
        from tasks.task_automator import tasks_for_booking_created
        from tasks.task_model import TaskPriority
        tasks = tasks_for_booking_created("t1", "bookingcom_R001", "prop_001", "2026-04-05")
        assert tasks[0].priority == TaskPriority.HIGH

    def test_cleaning_priority_is_medium(self):
        from tasks.task_automator import tasks_for_booking_created
        from tasks.task_model import TaskPriority
        tasks = tasks_for_booking_created("t1", "bookingcom_R001", "prop_001", "2026-04-05")
        assert tasks[1].priority == TaskPriority.MEDIUM

    def test_checkin_prep_urgency_is_urgent(self):
        from tasks.task_automator import tasks_for_booking_created
        tasks = tasks_for_booking_created("t1", "bookingcom_R001", "prop_001", "2026-04-05")
        assert tasks[0].urgency == "urgent"

    def test_cleaning_urgency_is_normal(self):
        from tasks.task_automator import tasks_for_booking_created
        tasks = tasks_for_booking_created("t1", "bookingcom_R001", "prop_001", "2026-04-05")
        assert tasks[1].urgency == "normal"

    def test_two_different_bookings_produce_different_task_ids(self):
        from tasks.task_automator import tasks_for_booking_created
        t1 = tasks_for_booking_created("t1", "bookingcom_R001", "prop_001", "2026-04-05")
        t2 = tasks_for_booking_created("t1", "bookingcom_R002", "prop_001", "2026-04-05")
        for a, b in zip(t1, t2):
            assert a.task_id != b.task_id

    def test_created_at_defaults_to_now_if_not_provided(self):
        from tasks.task_automator import tasks_for_booking_created
        before = datetime.now(tz=timezone.utc)
        tasks = tasks_for_booking_created("t1", "bookingcom_R001", "prop_001", "2026-04-05")
        after = datetime.now(tz=timezone.utc)
        for task in tasks:
            ts = datetime.fromisoformat(task.created_at.replace("Z", "+00:00"))
            assert before <= ts <= after


# ---------------------------------------------------------------------------
# Group D — BOOKING_CANCELED: cancels pending tasks
# ---------------------------------------------------------------------------

class TestBookingCanceled:

    def test_returns_cancel_action_per_pending_task(self):
        from tasks.task_automator import actions_for_booking_canceled
        actions = actions_for_booking_canceled(
            booking_id="bookingcom_R001",
            pending_task_ids=["abc123", "def456"],
        )
        assert len(actions) == 2

    def test_cancel_action_has_correct_task_ids(self):
        from tasks.task_automator import actions_for_booking_canceled
        actions = actions_for_booking_canceled(
            booking_id="bookingcom_R001",
            pending_task_ids=["abc123", "def456"],
        )
        ids = {a.task_id for a in actions}
        assert ids == {"abc123", "def456"}

    def test_cancel_action_has_correct_booking_id(self):
        from tasks.task_automator import actions_for_booking_canceled
        actions = actions_for_booking_canceled(
            booking_id="bookingcom_R001",
            pending_task_ids=["abc123"],
        )
        assert actions[0].booking_id == "bookingcom_R001"

    def test_cancel_action_default_reason(self):
        from tasks.task_automator import actions_for_booking_canceled
        actions = actions_for_booking_canceled("b1", ["t1"])
        assert "canceled" in actions[0].reason.lower()

    def test_cancel_action_custom_reason(self):
        from tasks.task_automator import actions_for_booking_canceled
        actions = actions_for_booking_canceled("b1", ["t1"], reason="Guest no-show")
        assert actions[0].reason == "Guest no-show"


# ---------------------------------------------------------------------------
# Group E — BOOKING_CANCELED: edge cases
# ---------------------------------------------------------------------------

class TestBookingCanceledEdgeCases:

    def test_empty_pending_ids_returns_empty_list(self):
        from tasks.task_automator import actions_for_booking_canceled
        actions = actions_for_booking_canceled("bookingcom_R001", [])
        assert actions == []

    def test_single_pending_task_returns_one_action(self):
        from tasks.task_automator import actions_for_booking_canceled
        actions = actions_for_booking_canceled("bookingcom_R001", ["only_task"])
        assert len(actions) == 1

    def test_cancel_actions_are_frozen(self):
        """TaskCancelAction is frozen=True — immutable."""
        from tasks.task_automator import TaskCancelAction
        action = TaskCancelAction(task_id="t1", booking_id="b1")
        import pytest
        with pytest.raises((AttributeError, TypeError)):
            action.task_id = "new_id"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Group F — BOOKING_AMENDED: reschedules when date changes
# ---------------------------------------------------------------------------

class TestBookingAmendedReschedule:

    def test_reschedules_checkin_prep_when_check_in_changes(self):
        from tasks.task_automator import actions_for_booking_amended
        from tasks.task_model import TaskKind
        tasks = [_make_task("CHECKIN_PREP", due_date="2026-04-05")]
        actions = actions_for_booking_amended(
            booking_id="bookingcom_R001",
            new_check_in="2026-04-12",
            existing_tasks=tasks,
        )
        assert len(actions) == 1
        assert actions[0].kind == TaskKind.CHECKIN_PREP
        assert actions[0].old_due_date == "2026-04-05"
        assert actions[0].new_due_date == "2026-04-12"

    def test_reschedules_cleaning_when_check_in_changes(self):
        from tasks.task_automator import actions_for_booking_amended
        from tasks.task_model import TaskKind
        tasks = [_make_task("CLEANING", due_date="2026-04-05")]
        actions = actions_for_booking_amended(
            booking_id="bookingcom_R001",
            new_check_in="2026-04-12",
            existing_tasks=tasks,
        )
        assert len(actions) == 1
        assert actions[0].kind == TaskKind.CLEANING

    def test_reschedules_both_when_both_present(self):
        from tasks.task_automator import actions_for_booking_amended
        tasks = [
            _make_task("CHECKIN_PREP", due_date="2026-04-05"),
            _make_task("CLEANING", due_date="2026-04-05"),
        ]
        actions = actions_for_booking_amended(
            booking_id="bookingcom_R001",
            new_check_in="2026-04-12",
            existing_tasks=tasks,
        )
        assert len(actions) == 2

    def test_reschedule_action_has_correct_task_id(self):
        from tasks.task_automator import actions_for_booking_amended
        task = _make_task("CHECKIN_PREP", due_date="2026-04-05")
        actions = actions_for_booking_amended("bookingcom_R001", "2026-04-12", [task])
        assert actions[0].task_id == task.task_id

    def test_reschedule_action_has_booking_id(self):
        from tasks.task_automator import actions_for_booking_amended
        task = _make_task("CHECKIN_PREP", due_date="2026-04-05")
        actions = actions_for_booking_amended("bookingcom_R001", "2026-04-12", [task])
        assert actions[0].booking_id == "bookingcom_R001"


# ---------------------------------------------------------------------------
# Group G — BOOKING_AMENDED: no action if date unchanged
# ---------------------------------------------------------------------------

class TestBookingAmendedNoChange:

    def test_no_action_when_due_date_already_matches(self):
        from tasks.task_automator import actions_for_booking_amended
        tasks = [_make_task("CHECKIN_PREP", due_date="2026-04-12")]
        actions = actions_for_booking_amended("bookingcom_R001", "2026-04-12", tasks)
        assert actions == []

    def test_no_action_for_both_tasks_if_dates_match(self):
        from tasks.task_automator import actions_for_booking_amended
        tasks = [
            _make_task("CHECKIN_PREP", due_date="2026-04-12"),
            _make_task("CLEANING", due_date="2026-04-12"),
        ]
        actions = actions_for_booking_amended("bookingcom_R001", "2026-04-12", tasks)
        assert actions == []

    def test_empty_existing_tasks_returns_no_actions(self):
        from tasks.task_automator import actions_for_booking_amended
        actions = actions_for_booking_amended("bookingcom_R001", "2026-04-12", [])
        assert actions == []


# ---------------------------------------------------------------------------
# Group H — BOOKING_AMENDED: skips terminal tasks
# ---------------------------------------------------------------------------

class TestBookingAmendedSkipsTerminal:

    def test_completed_task_not_rescheduled(self):
        from tasks.task_automator import actions_for_booking_amended
        task = _make_task("CHECKIN_PREP", due_date="2026-04-05", status_str="COMPLETED")
        actions = actions_for_booking_amended("bookingcom_R001", "2026-04-12", [task])
        assert actions == []

    def test_canceled_task_not_rescheduled(self):
        from tasks.task_automator import actions_for_booking_amended
        task = _make_task("CHECKIN_PREP", due_date="2026-04-05", status_str="CANCELED")
        actions = actions_for_booking_amended("bookingcom_R001", "2026-04-12", [task])
        assert actions == []

    def test_in_progress_task_is_rescheduled(self):
        """IN_PROGRESS is not terminal — should still be rescheduled."""
        from tasks.task_automator import actions_for_booking_amended
        task = _make_task("CLEANING", due_date="2026-04-05", status_str="IN_PROGRESS")
        actions = actions_for_booking_amended("bookingcom_R001", "2026-04-12", [task])
        assert len(actions) == 1

    def test_acknowledged_task_is_rescheduled(self):
        """ACKNOWLEDGED is not terminal — should be rescheduled."""
        from tasks.task_automator import actions_for_booking_amended
        task = _make_task("CHECKIN_PREP", due_date="2026-04-05", status_str="ACKNOWLEDGED")
        actions = actions_for_booking_amended("bookingcom_R001", "2026-04-12", [task])
        assert len(actions) == 1


# ---------------------------------------------------------------------------
# Group I — BOOKING_AMENDED: only CHECKIN_PREP and CLEANING affected
# ---------------------------------------------------------------------------

class TestBookingAmendedKindFilter:

    def test_maintenance_task_not_rescheduled(self):
        from tasks.task_automator import actions_for_booking_amended
        task = _make_task("MAINTENANCE", due_date="2026-04-05")
        actions = actions_for_booking_amended("bookingcom_R001", "2026-04-12", [task])
        assert actions == []

    def test_general_task_not_rescheduled(self):
        from tasks.task_automator import actions_for_booking_amended
        task = _make_task("GENERAL", due_date="2026-04-05")
        actions = actions_for_booking_amended("bookingcom_R001", "2026-04-12", [task])
        assert actions == []

    def test_checkout_verify_not_rescheduled(self):
        from tasks.task_automator import actions_for_booking_amended
        task = _make_task("CHECKOUT_VERIFY", due_date="2026-04-05")
        actions = actions_for_booking_amended("bookingcom_R001", "2026-04-12", [task])
        assert actions == []

    def test_mixed_tasks_only_affected_kinds_rescheduled(self):
        from tasks.task_automator import actions_for_booking_amended
        from tasks.task_model import TaskKind
        tasks = [
            _make_task("CHECKIN_PREP", due_date="2026-04-05"),
            _make_task("MAINTENANCE", due_date="2026-04-05"),
            _make_task("CLEANING", due_date="2026-04-05"),
            _make_task("GENERAL", due_date="2026-04-05"),
        ]
        actions = actions_for_booking_amended("bookingcom_R001", "2026-04-12", tasks)
        assert len(actions) == 2
        kinds = {a.kind for a in actions}
        assert TaskKind.CHECKIN_PREP in kinds
        assert TaskKind.CLEANING in kinds

    def test_tasks_for_different_booking_not_rescheduled(self):
        from tasks.task_automator import actions_for_booking_amended
        task = _make_task("CHECKIN_PREP", booking_id="airbnb_A999", due_date="2026-04-05")
        actions = actions_for_booking_amended(
            booking_id="bookingcom_R001",  # different booking
            new_check_in="2026-04-12",
            existing_tasks=[task],
        )
        assert actions == []


# ---------------------------------------------------------------------------
# Group J — Pure-function invariants
# ---------------------------------------------------------------------------

class TestPureFunctionInvariants:

    def test_booking_created_does_not_mutate_input(self):
        """The function must not have side effects on its string arguments."""
        from tasks.task_automator import tasks_for_booking_created
        bid = "bookingcom_R001"
        tasks_for_booking_created("t1", bid, "prop_001", "2026-04-05")
        assert bid == "bookingcom_R001"

    def test_booking_created_returns_fresh_objects_each_call(self):
        from tasks.task_automator import tasks_for_booking_created
        t1 = tasks_for_booking_created("t1", "bookingcom_R001", "prop_001", "2026-04-05",
                                        created_at="2026-03-09T10:00:00+00:00")
        t2 = tasks_for_booking_created("t1", "bookingcom_R001", "prop_001", "2026-04-05",
                                        created_at="2026-03-09T10:00:00+00:00")
        # Different list objects even if contents are equal
        assert t1 is not t2

    def test_booking_canceled_does_not_mutate_input_list(self):
        from tasks.task_automator import actions_for_booking_canceled
        ids = ["abc", "def"]
        actions_for_booking_canceled("b1", ids)
        assert ids == ["abc", "def"]

    def test_booking_amended_does_not_mutate_existing_tasks(self):
        from tasks.task_automator import actions_for_booking_amended
        task = _make_task("CHECKIN_PREP", due_date="2026-04-05")
        original_due = task.due_date
        actions_for_booking_amended("bookingcom_R001", "2026-04-12", [task])
        assert task.due_date == original_due  # unchanged

    def test_all_functions_callable_with_empty_inputs(self):
        """Functions with list inputs must not crash on empty lists."""
        from tasks.task_automator import (
            actions_for_booking_canceled,
            actions_for_booking_amended,
        )
        assert actions_for_booking_canceled("b1", []) == []
        assert actions_for_booking_amended("b1", "2026-04-12", []) == []
