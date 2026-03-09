"""
Contract Tests — Task Writer (Phase 115)

Tests for src/tasks/task_writer.py.

Architecture:
- All tests use MagicMock for the Supabase client (no live DB required).
- Tests verify: write path, cancel path, reschedule path, idempotency via upsert,
  best-effort error swallowing, and service.py wiring.

Groups:
  A — write_tasks_for_booking_created (happy path, idempotency, error swallow)
  B — cancel_tasks_for_booking_canceled (happy path, no pending, error swallow)
  C — reschedule_tasks_for_booking_amended (happy path, no change needed, error swallow)
  D — _task_to_row shape validation
  E — service.py wiring (task_writer called after APPLIED events)
"""
from __future__ import annotations

import sys
import os
import importlib
from datetime import date
from unittest.mock import MagicMock, patch, call

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tasks.task_writer import (
    write_tasks_for_booking_created,
    cancel_tasks_for_booking_canceled,
    reschedule_tasks_for_booking_amended,
    _task_to_row,
)
from tasks.task_model import (
    Task,
    TaskKind,
    TaskPriority,
    TaskStatus,
    WorkerRole,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_db(upsert_data=None, select_data=None, update_data=None):
    """Build a MagicMock Supabase client with chainable query builder."""
    db = MagicMock()

    # upsert
    upsert_result = MagicMock()
    upsert_result.data = upsert_data or []
    db.table.return_value.upsert.return_value.execute.return_value = upsert_result

    # select
    select_result = MagicMock()
    select_result.data = select_data or []
    (
        db.table.return_value
        .select.return_value
        .eq.return_value
        .eq.return_value
        .eq.return_value
        .execute.return_value
    ) = select_result

    # update
    update_result = MagicMock()
    update_result.data = update_data or []
    (
        db.table.return_value
        .update.return_value
        .eq.return_value
        .eq.return_value
        .eq.return_value
        .execute.return_value
    ) = update_result

    return db


def _make_task(
    kind=TaskKind.CLEANING,
    status=TaskStatus.PENDING,
    due_date="2026-04-01",
    booking_id="bookingcom_R001",
    tenant_id="t1",
    property_id="prop_001",
) -> Task:
    return Task(
        task_id="aabbccdd11223344",
        kind=kind,
        status=status,
        priority=TaskPriority.MEDIUM,
        urgency="normal",
        worker_role=WorkerRole.CLEANER,
        ack_sla_minutes=60,
        tenant_id=tenant_id,
        booking_id=booking_id,
        property_id=property_id,
        due_date=due_date,
        title="Test task",
        created_at="2026-03-09T12:00:00+00:00",
        updated_at="2026-03-09T12:00:00+00:00",
    )


# ---------------------------------------------------------------------------
# Group A — write_tasks_for_booking_created
# ---------------------------------------------------------------------------

class TestWriteTasksForBookingCreated:

    def test_a1_returns_task_count_on_success(self):
        """A1: Returns 2 on successful write of CHECKIN_PREP + CLEANING."""
        db = MagicMock()
        upsert_result = MagicMock()
        upsert_result.data = [{"task_id": "aa"}, {"task_id": "bb"}]
        db.table.return_value.upsert.return_value.execute.return_value = upsert_result

        count = write_tasks_for_booking_created(
            tenant_id="t1",
            booking_id="bookingcom_R001",
            property_id="prop_001",
            check_in="2026-04-01",
            provider="bookingcom",
            client=db,
        )
        assert count == 2

    def test_a2_upsert_called_with_two_rows(self):
        """A2: upsert receives exactly 2 rows."""
        db = MagicMock()
        upsert_result = MagicMock()
        upsert_result.data = [{"task_id": "aa"}, {"task_id": "bb"}]
        db.table.return_value.upsert.return_value.execute.return_value = upsert_result

        write_tasks_for_booking_created(
            tenant_id="t1",
            booking_id="bookingcom_R001",
            property_id="prop_001",
            check_in="2026-04-10",
            client=db,
        )
        rows = db.table.return_value.upsert.call_args[0][0]
        assert len(rows) == 2

    def test_a3_upsert_uses_on_conflict_task_id(self):
        """A3: upsert is called with on_conflict='task_id' for idempotency."""
        db = MagicMock()
        upsert_result = MagicMock()
        upsert_result.data = [{"task_id": "aa"}, {"task_id": "bb"}]
        db.table.return_value.upsert.return_value.execute.return_value = upsert_result

        write_tasks_for_booking_created(
            tenant_id="t1",
            booking_id="bookingcom_R001",
            property_id="prop_001",
            check_in="2026-04-10",
            client=db,
        )
        kwargs = db.table.return_value.upsert.call_args[1]
        assert kwargs.get("on_conflict") == "task_id"

    def test_a4_rows_have_correct_kinds(self):
        """A4: Written rows contain CHECKIN_PREP and CLEANING."""
        db = MagicMock()
        upsert_result = MagicMock()
        upsert_result.data = [{"task_id": "aa"}, {"task_id": "bb"}]
        db.table.return_value.upsert.return_value.execute.return_value = upsert_result

        write_tasks_for_booking_created(
            tenant_id="t1",
            booking_id="bookingcom_R001",
            property_id="prop_001",
            check_in="2026-04-10",
            client=db,
        )
        rows = db.table.return_value.upsert.call_args[0][0]
        kinds = {r["kind"] for r in rows}
        assert kinds == {"CHECKIN_PREP", "CLEANING"}

    def test_a5_rows_have_correct_due_date(self):
        """A5: due_date on all rows matches check_in."""
        db = MagicMock()
        upsert_result = MagicMock()
        upsert_result.data = [{"task_id": "aa"}, {"task_id": "bb"}]
        db.table.return_value.upsert.return_value.execute.return_value = upsert_result

        write_tasks_for_booking_created(
            tenant_id="t1",
            booking_id="bookingcom_R001",
            property_id="prop_001",
            check_in="2026-04-15",
            client=db,
        )
        rows = db.table.return_value.upsert.call_args[0][0]
        assert all(r["due_date"] == "2026-04-15" for r in rows)

    def test_a6_error_swallowed_returns_zero(self):
        """A6: DB error is swallowed, returns 0 (best-effort pattern)."""
        db = MagicMock()
        db.table.return_value.upsert.side_effect = RuntimeError("DB down")

        count = write_tasks_for_booking_created(
            tenant_id="t1",
            booking_id="bookingcom_R001",
            property_id="prop_001",
            check_in="2026-04-10",
            client=db,
        )
        assert count == 0

    def test_a7_rows_have_tenant_id(self):
        """A7: tenant_id is set correctly on written rows."""
        db = MagicMock()
        upsert_result = MagicMock()
        upsert_result.data = [{"task_id": "aa"}, {"task_id": "bb"}]
        db.table.return_value.upsert.return_value.execute.return_value = upsert_result

        write_tasks_for_booking_created(
            tenant_id="tenant_xyz",
            booking_id="bookingcom_R001",
            property_id="prop_001",
            check_in="2026-04-10",
            client=db,
        )
        rows = db.table.return_value.upsert.call_args[0][0]
        assert all(r["tenant_id"] == "tenant_xyz" for r in rows)

    def test_a8_rows_have_status_pending(self):
        """A8: All written tasks have status PENDING."""
        db = MagicMock()
        upsert_result = MagicMock()
        upsert_result.data = [{"task_id": "aa"}, {"task_id": "bb"}]
        db.table.return_value.upsert.return_value.execute.return_value = upsert_result

        write_tasks_for_booking_created(
            tenant_id="t1",
            booking_id="bookingcom_R001",
            property_id="prop_001",
            check_in="2026-04-10",
            client=db,
        )
        rows = db.table.return_value.upsert.call_args[0][0]
        assert all(r["status"] == "PENDING" for r in rows)

    def test_a9_checkin_prep_priority_high(self):
        """A9: CHECKIN_PREP task has priority HIGH."""
        db = MagicMock()
        upsert_result = MagicMock()
        upsert_result.data = [{"task_id": "aa"}, {"task_id": "bb"}]
        db.table.return_value.upsert.return_value.execute.return_value = upsert_result

        write_tasks_for_booking_created(
            tenant_id="t1",
            booking_id="bookingcom_R001",
            property_id="prop_001",
            check_in="2026-04-10",
            client=db,
        )
        rows = db.table.return_value.upsert.call_args[0][0]
        checkin = next(r for r in rows if r["kind"] == "CHECKIN_PREP")
        assert checkin["priority"] == "HIGH"

    def test_a10_cleaning_priority_medium(self):
        """A10: CLEANING task has priority MEDIUM."""
        db = MagicMock()
        upsert_result = MagicMock()
        upsert_result.data = [{"task_id": "aa"}, {"task_id": "bb"}]
        db.table.return_value.upsert.return_value.execute.return_value = upsert_result

        write_tasks_for_booking_created(
            tenant_id="t1",
            booking_id="bookingcom_R001",
            property_id="prop_001",
            check_in="2026-04-10",
            client=db,
        )
        rows = db.table.return_value.upsert.call_args[0][0]
        cleaning = next(r for r in rows if r["kind"] == "CLEANING")
        assert cleaning["priority"] == "MEDIUM"


# ---------------------------------------------------------------------------
# Group B — cancel_tasks_for_booking_canceled
# ---------------------------------------------------------------------------

class TestCancelTasksForBookingCanceled:

    def _db_with_pending(self, pending_ids):
        """Build a mock DB that returns pending tasks and accepts updates."""
        db = MagicMock()

        # SELECT chain
        select_result = MagicMock()
        select_result.data = [{"task_id": tid} for tid in pending_ids]

        q = db.table.return_value
        q.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = select_result

        # UPDATE chain
        update_result = MagicMock()
        update_result.data = []
        q.update.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = update_result

        return db

    def test_b1_returns_count_equal_to_pending_tasks(self):
        """B1: Returns number of canceled tasks."""
        db = self._db_with_pending(["t1", "t2"])
        count = cancel_tasks_for_booking_canceled("bookingcom_R001", "tenant_1", client=db)
        assert count == 2

    def test_b2_returns_zero_when_no_pending_tasks(self):
        """B2: Returns 0 if no PENDING tasks found."""
        db = self._db_with_pending([])
        count = cancel_tasks_for_booking_canceled("bookingcom_R001", "tenant_1", client=db)
        assert count == 0

    def test_b3_update_called_per_task(self):
        """B3: update() is called once per pending task_id."""
        db = self._db_with_pending(["ta", "tb", "tc"])
        cancel_tasks_for_booking_canceled("bookingcom_R001", "tenant_1", client=db)
        assert db.table.return_value.update.call_count == 3

    def test_b4_update_sets_status_canceled(self):
        """B4: update() payload contains status=CANCELED."""
        db = self._db_with_pending(["ta"])
        cancel_tasks_for_booking_canceled("bookingcom_R001", "tenant_1", client=db)
        update_dict = db.table.return_value.update.call_args[0][0]
        assert update_dict["status"] == "CANCELED"

    def test_b5_update_sets_canceled_reason(self):
        """B5: update() payload includes canceled_reason."""
        db = self._db_with_pending(["ta"])
        cancel_tasks_for_booking_canceled("bookingcom_R001", "tenant_1", client=db)
        update_dict = db.table.return_value.update.call_args[0][0]
        assert "canceled_reason" in update_dict
        assert update_dict["canceled_reason"]  # non-empty

    def test_b6_custom_reason_propagated(self):
        """B6: Custom cancellation reason is passed through."""
        db = self._db_with_pending(["ta"])
        cancel_tasks_for_booking_canceled(
            "bookingcom_R001", "tenant_1", reason="Guest no-show", client=db
        )
        update_dict = db.table.return_value.update.call_args[0][0]
        assert update_dict["canceled_reason"] == "Guest no-show"

    def test_b7_error_swallowed_returns_zero(self):
        """B7: DB error is swallowed, returns 0."""
        db = MagicMock()
        db.table.side_effect = RuntimeError("connection error")
        count = cancel_tasks_for_booking_canceled("bookingcom_R001", "tenant_1", client=db)
        assert count == 0

    def test_b8_no_update_if_no_pending(self):
        """B8: update() never called if no pending tasks."""
        db = self._db_with_pending([])
        cancel_tasks_for_booking_canceled("bookingcom_R001", "tenant_1", client=db)
        db.table.return_value.update.assert_not_called()


# ---------------------------------------------------------------------------
# Group C — reschedule_tasks_for_booking_amended
# ---------------------------------------------------------------------------

class TestRescheduleTasksForBookingAmended:

    def _make_row(self, kind="CLEANING", due_date="2026-04-01", status="PENDING"):
        return {
            "task_id": "aabbccdd11223344",
            "kind": kind,
            "status": status,
            "priority": "MEDIUM",
            "urgency": "normal",
            "worker_role": "CLEANER",
            "ack_sla_minutes": 60,
            "tenant_id": "t1",
            "booking_id": "bookingcom_R001",
            "property_id": "prop_001",
            "due_date": due_date,
            "title": "Test",
            "description": None,
            "notes": [],
            "canceled_reason": None,
            "created_at": "2026-03-09T12:00:00+00:00",
            "updated_at": "2026-03-09T12:00:00+00:00",
        }

    def _db_with_rows(self, rows):
        db = MagicMock()
        select_result = MagicMock()
        select_result.data = rows

        # Flexible chained mock for SELECT
        q = db.table.return_value
        q.select.return_value.eq.return_value.eq.return_value.in_.return_value.not_.in_.return_value.execute.return_value = select_result

        # UPDATE chain
        update_result = MagicMock()
        update_result.data = []
        q.update.return_value.eq.return_value.eq.return_value.execute.return_value = update_result

        return db

    def test_c1_returns_reschedule_count(self):
        """C1: Returns count of rescheduled tasks."""
        rows = [self._make_row("CLEANING", "2026-04-01"), self._make_row("CHECKIN_PREP", "2026-04-01")]
        db = self._db_with_rows(rows)
        count = reschedule_tasks_for_booking_amended("bookingcom_R001", "2026-04-10", "t1", client=db)
        assert count == 2

    def test_c2_returns_zero_when_no_rows(self):
        """C2: Returns 0 if no active tasks in DB."""
        db = self._db_with_rows([])
        count = reschedule_tasks_for_booking_amended("bookingcom_R001", "2026-04-10", "t1", client=db)
        assert count == 0

    def test_c3_returns_zero_when_due_date_unchanged(self):
        """C3: Returns 0 if new_check_in equals existing due_date (no change needed)."""
        rows = [self._make_row("CLEANING", "2026-04-10")]
        db = self._db_with_rows(rows)
        count = reschedule_tasks_for_booking_amended("bookingcom_R001", "2026-04-10", "t1", client=db)
        assert count == 0

    def test_c4_update_sets_new_due_date(self):
        """C4: update() payload contains new due_date."""
        rows = [self._make_row("CLEANING", "2026-04-01")]
        db = self._db_with_rows(rows)
        reschedule_tasks_for_booking_amended("bookingcom_R001", "2026-04-15", "t1", client=db)
        update_dict = db.table.return_value.update.call_args[0][0]
        assert update_dict["due_date"] == "2026-04-15"

    def test_c5_error_swallowed_returns_zero(self):
        """C5: DB error is swallowed, returns 0."""
        db = MagicMock()
        db.table.side_effect = RuntimeError("connection error")
        count = reschedule_tasks_for_booking_amended("bookingcom_R001", "2026-04-10", "t1", client=db)
        assert count == 0


# ---------------------------------------------------------------------------
# Group D — _task_to_row shape validation
# ---------------------------------------------------------------------------

class TestTaskToRow:

    def test_d1_all_required_fields_present(self):
        """D1: _task_to_row output contains all 17 required column fields."""
        task = _make_task()
        row = _task_to_row(task)
        required = {
            "task_id", "tenant_id", "kind", "status", "priority", "urgency",
            "worker_role", "ack_sla_minutes", "booking_id", "property_id",
            "due_date", "title", "description", "created_at", "updated_at",
            "notes", "canceled_reason",
        }
        assert required.issubset(set(row.keys()))

    def test_d2_enum_values_are_strings(self):
        """D2: Enum fields are serialized as string values (not enum objects)."""
        task = _make_task()
        row = _task_to_row(task)
        assert isinstance(row["kind"], str)
        assert isinstance(row["status"], str)
        assert isinstance(row["priority"], str)
        assert isinstance(row["worker_role"], str)

    def test_d3_notes_default_empty_list(self):
        """D3: notes field defaults to empty list when Task.notes is empty."""
        task = _make_task()
        row = _task_to_row(task)
        assert row["notes"] == []

    def test_d4_kind_value_matches_enum(self):
        """D4: kind field value matches TaskKind.value."""
        task = _make_task(kind=TaskKind.CHECKIN_PREP)
        row = _task_to_row(task)
        assert row["kind"] == "CHECKIN_PREP"

    def test_d5_status_value_matches_enum(self):
        """D5: status field value matches TaskStatus.value."""
        task = _make_task(status=TaskStatus.ACKNOWLEDGED)
        row = _task_to_row(task)
        assert row["status"] == "ACKNOWLEDGED"


# ---------------------------------------------------------------------------
# Group E — service.py wiring
# ---------------------------------------------------------------------------

class TestServiceWiring:

    def test_e1_write_tasks_called_on_booking_created_applied(self):
        """E1: write_tasks_for_booking_created is called when BOOKING_CREATED returns APPLIED."""
        from adapters.ota import service

        envelope = MagicMock()
        envelope.type = "BOOKING_CREATED"
        envelope.idempotency_key = "key1"
        envelope.occurred_at = "2026-03-09T10:00:00Z"
        envelope.payload = {}

        apply_result = {"status": "APPLIED"}
        skill_result = MagicMock()
        skill_result.events_to_emit = [
            MagicMock(type="BOOKING_CREATED", payload={"booking_id": "bcom_R001", "property_id": "p1"})
        ]
        raw_payload = {
            "check_in": "2026-04-10",
            "reservation_id": "R001",
            "tenant_id": "t1",
        }

        with (
            patch.object(service, "process_ota_event", return_value=envelope),
            patch("tasks.task_writer.write_tasks_for_booking_created") as mock_write,
            patch("adapters.ota.financial_extractor.extract_financial_facts", return_value=None),
            patch("adapters.ota.ordering_trigger.trigger_ordered_replay"),
        ):
            service.ingest_provider_event_with_dlq(
                provider="bookingcom",
                payload=raw_payload,
                tenant_id="t1",
                apply_fn=lambda e, em: apply_result,
                skill_fn=lambda p: skill_result,
            )
            # task_writer should have been called
            mock_write.assert_called_once()

    def test_e2_cancel_tasks_called_on_booking_canceled_applied(self):
        """E2: cancel_tasks_for_booking_canceled is called when BOOKING_CANCELED returns APPLIED."""
        from adapters.ota import service

        envelope = MagicMock()
        envelope.type = "BOOKING_CANCELED"
        envelope.idempotency_key = "key2"
        envelope.occurred_at = "2026-03-09T10:00:00Z"
        envelope.payload = {}

        apply_result = {"status": "APPLIED"}
        skill_result = MagicMock()
        skill_result.events_to_emit = [
            MagicMock(type="BOOKING_CANCELED", payload={"booking_id": "bcom_R001"})
        ]

        with (
            patch.object(service, "process_ota_event", return_value=envelope),
            patch("tasks.task_writer.cancel_tasks_for_booking_canceled") as mock_cancel,
        ):
            service.ingest_provider_event_with_dlq(
                provider="bookingcom",
                payload={"reservation_id": "R001"},
                tenant_id="t1",
                apply_fn=lambda e, em: apply_result,
                skill_fn=lambda p: skill_result,
            )
            mock_cancel.assert_called_once()

    def test_e3_task_writer_not_called_when_not_applied(self):
        """E3: write_tasks is NOT called when status is not APPLIED (e.g. ALREADY_APPLIED)."""
        from adapters.ota import service

        envelope = MagicMock()
        envelope.type = "BOOKING_CREATED"
        envelope.idempotency_key = "key3"
        envelope.occurred_at = "2026-03-09T10:00:00Z"
        envelope.payload = {}

        apply_result = {"status": "ALREADY_APPLIED"}
        skill_result = MagicMock()
        skill_result.events_to_emit = [
            MagicMock(type="BOOKING_CREATED", payload={"booking_id": "bcom_R001", "property_id": "p1"})
        ]

        with (
            patch.object(service, "process_ota_event", return_value=envelope),
            patch("tasks.task_writer.write_tasks_for_booking_created") as mock_write,
        ):
            service.ingest_provider_event_with_dlq(
                provider="bookingcom",
                payload={"check_in": "2026-04-10"},
                tenant_id="t1",
                apply_fn=lambda e, em: apply_result,
                skill_fn=lambda p: skill_result,
            )
            mock_write.assert_not_called()

    def test_e4_task_writer_error_does_not_block_response(self):
        """E4: Exception in write_tasks does not propagate — best-effort pattern."""
        from adapters.ota import service

        envelope = MagicMock()
        envelope.type = "BOOKING_CREATED"
        envelope.idempotency_key = "key4"
        envelope.occurred_at = "2026-03-09T10:00:00Z"
        envelope.payload = {}

        apply_result = {"status": "APPLIED"}
        skill_result = MagicMock()
        skill_result.events_to_emit = [
            MagicMock(type="BOOKING_CREATED", payload={"booking_id": "bcom_R001", "property_id": "p1"})
        ]

        with (
            patch.object(service, "process_ota_event", return_value=envelope),
            patch("tasks.task_writer.write_tasks_for_booking_created", side_effect=RuntimeError("crash")),
            patch("adapters.ota.financial_extractor.extract_financial_facts", return_value=None),
            patch("adapters.ota.ordering_trigger.trigger_ordered_replay"),
        ):
            # Should not raise
            result = service.ingest_provider_event_with_dlq(
                provider="bookingcom",
                payload={"check_in": "2026-04-10"},
                tenant_id="t1",
                apply_fn=lambda e, em: apply_result,
                skill_fn=lambda p: skill_result,
            )
            assert result.get("status") == "APPLIED"
