"""
Phase 259 — Bulk Operations API Contract Tests
===============================================

Tests: 18 across 6 groups.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app, raise_server_exceptions=False)

_AUTH = {"Authorization": "Bearer test-token"}


# ---------------------------------------------------------------------------
# Group A — POST /admin/bulk/cancel
# ---------------------------------------------------------------------------

class TestGroupABulkCancel:
    """Batch cancel bookings."""

    def test_a1_all_valid_returns_ok_status(self):
        resp = client.post(
            "/admin/bulk/cancel",
            json={"booking_ids": ["BK-1", "BK-2", "BK-3"], "reason": "test"},
            headers=_AUTH,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["total"] == 3
        assert body["succeeded"] == 3
        assert body["failed"] == 0

    def test_a2_partial_failure_returns_partial_status(self):
        resp = client.post(
            "/admin/bulk/cancel",
            json={"booking_ids": ["BK-1", "INVALID-2", "BK-3"]},
            headers=_AUTH,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "partial"
        assert body["succeeded"] == 2
        assert body["failed"] == 1

    def test_a3_all_invalid_returns_failed_status(self):
        resp = client.post(
            "/admin/bulk/cancel",
            json={"booking_ids": ["INVALID-1", "INVALID-2"]},
            headers=_AUTH,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "failed"

    def test_a4_results_contain_per_item_outcome(self):
        resp = client.post(
            "/admin/bulk/cancel",
            json={"booking_ids": ["BK-1", "INVALID-2"]},
            headers=_AUTH,
        )
        results = resp.json()["results"]
        assert len(results) == 2
        assert any(r["item_id"] == "BK-1" and r["success"] for r in results)
        assert any(r["item_id"] == "INVALID-2" and not r["success"] for r in results)

    def test_a5_empty_list_returns_422(self):
        resp = client.post(
            "/admin/bulk/cancel",
            json={"booking_ids": []},
            headers=_AUTH,
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Group B — POST /admin/bulk/tasks/assign
# ---------------------------------------------------------------------------

class TestGroupBBulkTaskAssign:
    """Batch assign tasks to workers."""

    def test_b1_all_valid_returns_ok(self):
        resp = client.post(
            "/admin/bulk/tasks/assign",
            json={"assignments": [
                {"task_id": "T-1", "worker_id": "W-1"},
                {"task_id": "T-2", "worker_id": "W-2"},
            ]},
            headers=_AUTH,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        assert resp.json()["succeeded"] == 2

    def test_b2_partial_failure(self):
        resp = client.post(
            "/admin/bulk/tasks/assign",
            json={"assignments": [
                {"task_id": "T-1", "worker_id": "W-1"},
                {"task_id": "INVALID-T", "worker_id": "W-2"},
            ]},
            headers=_AUTH,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "partial"

    def test_b3_empty_assignments_returns_422(self):
        resp = client.post(
            "/admin/bulk/tasks/assign",
            json={"assignments": []},
            headers=_AUTH,
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Group C — POST /admin/bulk/sync/trigger
# ---------------------------------------------------------------------------

class TestGroupCBulkSyncTrigger:
    """Batch sync trigger."""

    def test_c1_all_valid_returns_ok(self):
        resp = client.post(
            "/admin/bulk/sync/trigger",
            json={"property_ids": ["PROP-1", "PROP-2"], "tenant_id": "tenant-x"},
            headers=_AUTH,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_c2_partial_failure(self):
        resp = client.post(
            "/admin/bulk/sync/trigger",
            json={"property_ids": ["PROP-1", "INVALID-PROP"], "tenant_id": "tenant-x"},
            headers=_AUTH,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "partial"

    def test_c3_empty_property_ids_returns_422(self):
        resp = client.post(
            "/admin/bulk/sync/trigger",
            json={"property_ids": [], "tenant_id": "tenant-x"},
            headers=_AUTH,
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Group D — Service layer unit tests
# ---------------------------------------------------------------------------

class TestGroupDServiceLayer:
    """Direct service function tests (no HTTP)."""

    def test_d1_bulk_cancel_raises_on_oversized_batch(self):
        from services.bulk_operations import bulk_cancel_bookings
        with pytest.raises(ValueError, match="exceeds maximum"):
            bulk_cancel_bookings(
                booking_ids=[f"BK-{i}" for i in range(51)],
                reason="test",
                actor_id="actor",
                cancel_fn=lambda *a: None,
            )

    def test_d2_bulk_cancel_raises_on_empty(self):
        from services.bulk_operations import bulk_cancel_bookings
        with pytest.raises(ValueError):
            bulk_cancel_bookings(
                booking_ids=[],
                reason="test",
                actor_id="actor",
                cancel_fn=lambda *a: None,
            )

    def test_d3_all_succeed_aggregate_status_is_ok(self):
        from services.bulk_operations import bulk_cancel_bookings
        result = bulk_cancel_bookings(
            booking_ids=["A", "B", "C"],
            reason="test",
            actor_id="actor",
            cancel_fn=lambda *a: None,
        )
        assert result.status == "ok"
        assert result.succeeded == 3

    def test_d4_mixed_results_status_is_partial(self):
        from services.bulk_operations import bulk_cancel_bookings

        def _fn(bid, reason, actor):
            if bid == "B":
                raise RuntimeError("fail")

        result = bulk_cancel_bookings(
            booking_ids=["A", "B", "C"],
            reason="test",
            actor_id="actor",
            cancel_fn=_fn,
        )
        assert result.status == "partial"
        assert result.succeeded == 2
        assert result.failed == 1

    def test_d5_all_fail_aggregate_status_is_failed(self):
        from services.bulk_operations import bulk_cancel_bookings
        result = bulk_cancel_bookings(
            booking_ids=["A", "B"],
            reason="test",
            actor_id="actor",
            cancel_fn=lambda *a: (_ for _ in ()).throw(RuntimeError("fail")),
        )
        assert result.status == "failed"
        assert result.failed == 2
