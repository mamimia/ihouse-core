"""
Phase 158 — Contract Tests: Booking Amendment History Endpoint

Tests:
  A — GET /bookings/{id}/amendments: booking not found → 404
  B — GET /bookings/{id}/amendments: found, no amendments → empty list
  C — GET /bookings/{id}/amendments: found, returns amendments
  D — GET /bookings/{id}/amendments: response shape is correct
  E — GET /bookings/{id}/amendments: tenant isolation (other tenant → 404)
  F — GET /bookings/{id}/amendments: limit clamped to max 100
  G — GET /bookings/{id}/amendments: sort order ascending by received_at
  H — GET /bookings/{id}/amendments: 500 on DB error
  I — GET /tasks?booking_id=: filter works (Phase 158 task_router addition)
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.bookings_router import router as bookings_router
from api.auth import jwt_auth

_app = FastAPI()
_app.include_router(bookings_router)
_app.dependency_overrides[jwt_auth] = lambda: "tenant-158"
_client = TestClient(_app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Mock DB factory
# ---------------------------------------------------------------------------

def _mock_db(
    booking_rows: list | None = None,
    event_rows: list | None = None,
    raise_exc: Exception | None = None,
):
    """
    Returns a Supabase-style mock client.
    First call to .execute() → booking_rows (existence check).
    Second call → event_rows (event_log query).
    """
    chain = MagicMock()

    if raise_exc is not None:
        chain.execute.side_effect = raise_exc
    else:
        # Alternate results: first call = booking check, second = events
        results = [
            MagicMock(data=booking_rows if booking_rows is not None else []),
            MagicMock(data=event_rows if event_rows is not None else []),
        ]
        chain.execute.side_effect = results

    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.gte.return_value = chain
    chain.lte.return_value = chain
    chain.or_.return_value = chain

    db = MagicMock()
    db.table.return_value = chain
    return db


def _booking_row(booking_id: str = "bk-158") -> dict:
    return {"booking_id": booking_id, "tenant_id": "tenant-158"}


def _amendment_row(envelope_id: str = "env-001", received_at: str = "2025-06-01T10:00:00Z") -> dict:
    return {
        "envelope_id": envelope_id,
        "booking_id":  "bk-158",
        "tenant_id":   "tenant-158",
        "event_type":  "BOOKING_AMENDED",
        "version":     2,
        "received_at": received_at,
        "payload":     {"check_in": "2025-09-01", "check_out": "2025-09-05"},
    }


# ===========================================================================
# Group A — booking not found → 404
# ===========================================================================

class TestGroupA_BookingNotFound:

    def test_a1_not_found_returns_404(self, monkeypatch):
        db = _mock_db(booking_rows=[], event_rows=[])
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        resp = _client.get("/bookings/does-not-exist/amendments")
        assert resp.status_code == 404

    def test_a2_error_contains_booking_id(self, monkeypatch):
        db = _mock_db(booking_rows=[], event_rows=[])
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        body = _client.get("/bookings/missing-bk/amendments").json()
        assert "missing-bk" in str(body)


# ===========================================================================
# Group B — found, no amendments → empty list
# ===========================================================================

class TestGroupB_NoAmendments:

    def test_b1_empty_amendments_returns_200(self, monkeypatch):
        db = _mock_db(booking_rows=[_booking_row()], event_rows=[])
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        resp = _client.get("/bookings/bk-158/amendments")
        assert resp.status_code == 200

    def test_b2_empty_amendments_count_zero(self, monkeypatch):
        db = _mock_db(booking_rows=[_booking_row()], event_rows=[])
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        data = _client.get("/bookings/bk-158/amendments").json()["data"]
        assert data["count"] == 0
        assert data["amendments"] == []

    def test_b3_booking_id_in_response(self, monkeypatch):
        db = _mock_db(booking_rows=[_booking_row()], event_rows=[])
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        data = _client.get("/bookings/bk-158/amendments").json()["data"]
        assert data["booking_id"] == "bk-158"


# ===========================================================================
# Group C — found, returns amendments
# ===========================================================================

class TestGroupC_WithAmendments:

    def test_c1_two_amendments_returned(self, monkeypatch):
        rows = [
            _amendment_row("env-001", "2025-06-01T10:00:00Z"),
            _amendment_row("env-002", "2025-06-15T12:00:00Z"),
        ]
        db = _mock_db(booking_rows=[_booking_row()], event_rows=rows)
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        data = _client.get("/bookings/bk-158/amendments").json()["data"]
        assert data["count"] == 2
        assert len(data["amendments"]) == 2

    def test_c2_amendment_has_envelope_id(self, monkeypatch):
        db = _mock_db(booking_rows=[_booking_row()], event_rows=[_amendment_row("env-xyz")])
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        data = _client.get("/bookings/bk-158/amendments").json()["data"]
        assert data["amendments"][0]["envelope_id"] == "env-xyz"


# ===========================================================================
# Group D — response shape
# ===========================================================================

class TestGroupD_ResponseShape:

    def test_d1_top_level_fields(self, monkeypatch):
        db = _mock_db(booking_rows=[_booking_row()], event_rows=[_amendment_row()])
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        data = _client.get("/bookings/bk-158/amendments").json()["data"]
        for field in ("booking_id", "tenant_id", "count", "amendments"):
            assert field in data

    def test_d2_amendment_fields(self, monkeypatch):
        db = _mock_db(booking_rows=[_booking_row()], event_rows=[_amendment_row()])
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        data = _client.get("/bookings/bk-158/amendments").json()["data"]
        a = data["amendments"][0]
        for field in ("envelope_id", "booking_id", "tenant_id", "event_type", "received_at"):
            assert field in a

    def test_d3_event_type_is_booking_amended(self, monkeypatch):
        db = _mock_db(booking_rows=[_booking_row()], event_rows=[_amendment_row()])
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        data = _client.get("/bookings/bk-158/amendments").json()["data"]
        assert data["amendments"][0]["event_type"] == "BOOKING_AMENDED"


# ===========================================================================
# Group E — tenant isolation
# ===========================================================================

class TestGroupE_TenantIsolation:

    def test_e1_other_tenant_booking_returns_404(self, monkeypatch):
        # DB returns empty for this tenant's booking_state lookup
        db = _mock_db(booking_rows=[], event_rows=[])
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        resp = _client.get("/bookings/other-tenant-booking/amendments")
        assert resp.status_code == 404


# ===========================================================================
# Group F — limit clamped to max 100
# ===========================================================================

class TestGroupF_LimitClamped:

    def test_f1_limit_above_100_clamped(self, monkeypatch):
        db = _mock_db(booking_rows=[_booking_row()], event_rows=[])
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        resp = _client.get("/bookings/bk-158/amendments?limit=999")
        assert resp.status_code == 200  # clamped, does not error

    def test_f2_limit_zero_clamped_to_one(self, monkeypatch):
        db = _mock_db(booking_rows=[_booking_row()], event_rows=[])
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        resp = _client.get("/bookings/bk-158/amendments?limit=0")
        assert resp.status_code == 200


# ===========================================================================
# Group G — sort order (ascending by received_at)
# ===========================================================================

class TestGroupG_SortOrder:

    def test_g1_older_amendment_first(self, monkeypatch):
        rows = [
            _amendment_row("env-001", "2025-06-01T10:00:00Z"),
            _amendment_row("env-002", "2025-06-15T12:00:00Z"),
        ]
        db = _mock_db(booking_rows=[_booking_row()], event_rows=rows)
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        data = _client.get("/bookings/bk-158/amendments").json()["data"]
        assert data["amendments"][0]["envelope_id"] == "env-001"
        assert data["amendments"][1]["envelope_id"] == "env-002"


# ===========================================================================
# Group H — 500 on DB error (absorbed)
# ===========================================================================

class TestGroupH_InternalError:

    def test_h1_db_exception_returns_500(self, monkeypatch):
        db = _mock_db(raise_exc=Exception("DB connection lost"))
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        resp = _client.get("/bookings/bk-158/amendments")
        assert resp.status_code == 500


# ===========================================================================
# Group I — GET /tasks?booking_id= filter (Phase 158 addition)
# ===========================================================================

class TestGroupI_TaskBookingIdFilter:

    def test_i1_tasks_booking_id_filter_returns_200(self, monkeypatch):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient as TC
        from tasks.task_router import router as task_router
        from api.auth import jwt_auth

        task_app = FastAPI()
        task_app.include_router(task_router)
        task_app.dependency_overrides[jwt_auth] = lambda: "tenant-i"

        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[])
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.limit.return_value = chain
        chain.order.return_value = chain
        task_db = MagicMock()
        task_db.table.return_value = chain

        monkeypatch.setattr("tasks.task_router._get_supabase_client", lambda: task_db)
        tc = TC(task_app, raise_server_exceptions=False)
        resp = tc.get("/tasks?booking_id=bk-filter-test")
        assert resp.status_code == 200

    def test_i2_booking_id_filter_applied_to_query(self, monkeypatch):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient as TC2
        from tasks.task_router import router as task_router2
        from api.auth import jwt_auth as jwt2

        task_app2 = FastAPI()
        task_app2.include_router(task_router2)
        task_app2.dependency_overrides[jwt2] = lambda: "tenant-i"

        chain2 = MagicMock()
        chain2.execute.return_value = MagicMock(data=[])
        chain2.select.return_value = chain2
        chain2.eq.return_value = chain2
        chain2.limit.return_value = chain2
        chain2.order.return_value = chain2
        task_db2 = MagicMock()
        task_db2.table.return_value = chain2

        monkeypatch.setattr("tasks.task_router._get_supabase_client", lambda: task_db2)
        tc2 = TC2(task_app2, raise_server_exceptions=False)
        tc2.get("/tasks?booking_id=bk-specific")
        # Verify .eq was called with "booking_id" somewhere in the chain
        calls = [str(c) for c in chain2.eq.call_args_list]
        assert any("bk-specific" in c for c in calls)
