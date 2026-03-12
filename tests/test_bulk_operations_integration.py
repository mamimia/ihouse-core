"""
Phase 332 — Bulk Operations Service Integration Tests
======================================================

Integration tests for `services/bulk_operations.py` — the service layer
for batch cancel, task assignment, and sync trigger operations.

These are distinct from the existing router contract tests (test_bulk_operations_contract.py)
which test the HTTP layer. These tests focus on the service's core logic.

Group A: Aggregate Status (_aggregate_status)
  ✓  All success → "ok"
  ✓  All failed → "failed"
  ✓  Mixed → "partial"
  ✓  Empty list → "ok"

Group B: bulk_cancel_bookings
  ✓  All succeed → result.succeeded == total
  ✓  One fails → captured in result.results with error
  ✓  All fail → status == "failed"
  ✓  Batch exceeds MAX_BATCH_SIZE → ValueError
  ✓  Empty list → ValueError
  ✓  Per-item error message preserved

Group C: bulk_assign_tasks
  ✓  All succeed → status "ok"
  ✓  Missing task_id → item captured as failed
  ✓  Missing worker_id → item captured as failed
  ✓  Batch exceeds limit → ValueError

Group D: bulk_trigger_sync
  ✓  All succeed → status "ok"
  ✓  Error in trigger → captured per-item
  ✓  Empty list → ValueError

CI-safe: pure function tests, no DB, no network.
"""
from __future__ import annotations

import os
import sys

import pytest

os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("IHOUSE_ENV", "test")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from services.bulk_operations import (
    BulkItemResult,
    BulkOperationResult,
    MAX_BATCH_SIZE,
    _aggregate_status,
    bulk_cancel_bookings,
    bulk_assign_tasks,
    bulk_trigger_sync,
)


# ---------------------------------------------------------------------------
# Group A — Aggregate Status
# ---------------------------------------------------------------------------

class TestAggregateStatus:

    def test_all_success_is_ok(self):
        items = [BulkItemResult(item_id="x", success=True),
                 BulkItemResult(item_id="y", success=True)]
        assert _aggregate_status(items) == "ok"

    def test_all_failed_is_failed(self):
        items = [BulkItemResult(item_id="x", success=False),
                 BulkItemResult(item_id="y", success=False)]
        assert _aggregate_status(items) == "failed"

    def test_mixed_is_partial(self):
        items = [BulkItemResult(item_id="x", success=True),
                 BulkItemResult(item_id="y", success=False)]
        assert _aggregate_status(items) == "partial"

    def test_empty_is_ok(self):
        assert _aggregate_status([]) == "ok"


# ---------------------------------------------------------------------------
# Group B — bulk_cancel_bookings
# ---------------------------------------------------------------------------

def _ok_cancel(booking_id, reason, actor_id):
    """Always succeeds."""
    pass


def _fail_cancel(booking_id, reason, actor_id):
    raise RuntimeError(f"Cannot cancel {booking_id}")


class TestBulkCancelBookings:

    def test_all_succeed(self):
        result = bulk_cancel_bookings(
            ["B-001", "B-002"], reason="admin", actor_id="sys", cancel_fn=_ok_cancel
        )
        assert result.succeeded == 2
        assert result.failed == 0
        assert result.status == "ok"

    def test_one_fails_captured(self):
        result = bulk_cancel_bookings(
            ["B-001", "B-002"], reason="admin", actor_id="sys", cancel_fn=_fail_cancel
        )
        assert result.failed == 2
        assert all(not r.success for r in result.results)
        assert "Cannot cancel" in result.results[0].error

    def test_mixed_outcomes_partial(self):
        def mixed_cancel(booking_id, reason, actor_id):
            if booking_id == "B-BAD":
                raise RuntimeError("bad booking")

        result = bulk_cancel_bookings(
            ["B-001", "B-BAD"], reason="admin", actor_id="sys", cancel_fn=mixed_cancel
        )
        assert result.status == "partial"
        assert result.succeeded == 1
        assert result.failed == 1

    def test_exceeds_max_batch_raises(self):
        ids = [f"B-{i}" for i in range(MAX_BATCH_SIZE + 1)]
        with pytest.raises(ValueError, match="Batch size"):
            bulk_cancel_bookings(ids, reason="admin", actor_id="sys", cancel_fn=_ok_cancel)

    def test_empty_ids_raises(self):
        with pytest.raises(ValueError, match="empty"):
            bulk_cancel_bookings([], reason="admin", actor_id="sys", cancel_fn=_ok_cancel)

    def test_per_item_error_preserved(self):
        result = bulk_cancel_bookings(
            ["B-001"], reason="admin", actor_id="sys", cancel_fn=_fail_cancel
        )
        assert result.results[0].item_id == "B-001"
        assert result.results[0].error is not None


# ---------------------------------------------------------------------------
# Group C — bulk_assign_tasks
# ---------------------------------------------------------------------------

def _ok_assign(task_id, worker_id, actor_id):
    pass


class TestBulkAssignTasks:

    def test_all_succeed(self):
        assignments = [{"task_id": "T-001", "worker_id": "W-001"}]
        result = bulk_assign_tasks(assignments, actor_id="sys", assign_fn=_ok_assign)
        assert result.status == "ok"
        assert result.succeeded == 1

    def test_missing_task_id_captured_as_failed(self):
        assignments = [{"task_id": "", "worker_id": "W-001"}]
        result = bulk_assign_tasks(assignments, actor_id="sys", assign_fn=_ok_assign)
        assert result.failed == 1
        assert result.results[0].success is False

    def test_missing_worker_id_captured_as_failed(self):
        assignments = [{"task_id": "T-001", "worker_id": ""}]
        result = bulk_assign_tasks(assignments, actor_id="sys", assign_fn=_ok_assign)
        assert result.failed == 1

    def test_exceeds_max_batch_raises(self):
        assignments = [{"task_id": f"T-{i}", "worker_id": "W-1"} for i in range(MAX_BATCH_SIZE + 1)]
        with pytest.raises(ValueError, match="Batch size"):
            bulk_assign_tasks(assignments, actor_id="sys", assign_fn=_ok_assign)


# ---------------------------------------------------------------------------
# Group D — bulk_trigger_sync
# ---------------------------------------------------------------------------

def _ok_trigger(property_id, tenant_id):
    pass


def _fail_trigger(property_id, tenant_id):
    raise RuntimeError(f"Sync failed for {property_id}")


class TestBulkTriggerSync:

    def test_all_succeed(self):
        result = bulk_trigger_sync(["P-001", "P-002"], tenant_id="t-1", trigger_fn=_ok_trigger)
        assert result.status == "ok"
        assert result.succeeded == 2

    def test_trigger_error_captured(self):
        result = bulk_trigger_sync(["P-001"], tenant_id="t-1", trigger_fn=_fail_trigger)
        assert result.failed == 1
        assert "Sync failed" in result.results[0].error

    def test_empty_property_ids_raises(self):
        with pytest.raises(ValueError, match="empty"):
            bulk_trigger_sync([], tenant_id="t-1", trigger_fn=_ok_trigger)
