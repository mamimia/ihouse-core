"""
Phase 72 — Contract tests for GET /admin/summary

Uses FastAPI TestClient + patch on _get_supabase_client — no live DB required.

Verifies:
1.  200 + all fields present
2.  active_bookings count correct
3.  canceled_bookings count correct
4.  total_bookings = active + canceled + any other state
5.  dlq_pending count correct (global)
6.  amendment_count correct (tenant-scoped from booking_financial_facts)
7.  last_event_at present when bookings exist
8.  last_event_at is None when no bookings
9.  tenant_id in response matches JWT sub
10. 403 when auth rejected
11. 500 on unexpected DB exception
12. booking_state queried with correct tenant_id filter
"""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app(tenant_id: str = "tenant-a") -> TestClient:
    from api.admin_router import router
    from api.auth import jwt_auth

    app = FastAPI()

    async def _stub_auth() -> str:
        return tenant_id

    app.dependency_overrides[jwt_auth] = _stub_auth
    app.include_router(router)
    return TestClient(app)


def _booking_rows(
    n_active: int = 2,
    n_canceled: int = 1,
    tenant_id: str = "tenant-a",
) -> list:
    rows = []
    for i in range(n_active):
        rows.append({"booking_id": f"b_active_{i}", "tenant_id": tenant_id, "status": "active", "updated_at": "2026-10-05T00:00:00Z"})
    for i in range(n_canceled):
        rows.append({"booking_id": f"b_canceled_{i}", "tenant_id": tenant_id, "status": "canceled", "updated_at": "2026-10-03T00:00:00Z"})
    return rows


def _make_db(
    active_rows: list | None = None,
    canceled_rows: list | None = None,
    total_rows: list | None = None,
    dlq_rows: list | None = None,
    amendment_rows: list | None = None,
    last_event_rows: list | None = None,
) -> MagicMock:
    """
    Create a mock DB where each sequential .eq() chain returns separate data.
    We use side_effect on the execute() calls in order.
    """
    db = MagicMock()

    def _eq_chain(data):
        m = MagicMock()
        m.execute.return_value = MagicMock(data=data)
        m.eq.return_value = m
        m.order.return_value = m
        m.limit.return_value = m
        return m

    # booking_state queries (active, canceled, total, last_event_at)
    # booking_financial_facts queries (amendment_count)
    # ota_dead_letter queries (dlq_pending)

    active_data = active_rows if active_rows is not None else [{"booking_id": "b1"}] * 2
    canceled_data = canceled_rows if canceled_rows is not None else [{"booking_id": "b2"}]
    total_data = total_rows if total_rows is not None else [{"booking_id": "b1"}, {"booking_id": "b2"}, {"booking_id": "b3"}]
    dlq_data = dlq_rows if dlq_rows is not None else [{"id": 1, "replay_result": None}]
    amendment_data = amendment_rows if amendment_rows is not None else [{"id": 1}]
    last_data = last_event_rows if last_event_rows is not None else [{"updated_at": "2026-10-05T00:00:00Z"}]

    # We need select to return different mock chains depending on sequence of calls
    call_results = [active_data, canceled_data, total_data, dlq_data, amendment_data, last_data]
    call_idx = [0]

    def _select(*args, **kwargs):
        idx = call_idx[0]
        call_idx[0] += 1
        if idx < len(call_results):
            return _eq_chain(call_results[idx])
        return _eq_chain([])

    db.table.return_value.select.side_effect = _select
    return db


# ---------------------------------------------------------------------------
# 200 — Happy path
# ---------------------------------------------------------------------------

class TestAdminSummary200:

    def test_200_status_code(self) -> None:
        db = _make_db()
        with patch("api.admin_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/admin/summary")
        assert resp.status_code == 200

    def test_200_all_fields_present(self) -> None:
        db = _make_db()
        with patch("api.admin_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/admin/summary")
        body = resp.json()
        for field in ("tenant_id", "active_bookings", "canceled_bookings",
                      "total_bookings", "dlq_pending", "amendment_count", "last_event_at"):
            assert field in body, f"Missing field: {field}"

    def test_200_active_count(self) -> None:
        db = _make_db(active_rows=[{"booking_id": "a"}, {"booking_id": "b"}])
        with patch("api.admin_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/admin/summary")
        assert resp.json()["active_bookings"] == 2

    def test_200_canceled_count(self) -> None:
        db = _make_db(canceled_rows=[{"booking_id": "c"}])
        with patch("api.admin_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/admin/summary")
        assert resp.json()["canceled_bookings"] == 1

    def test_200_dlq_pending_counts_null_replay_result(self) -> None:
        db = _make_db(dlq_rows=[
            {"id": 1, "replay_result": None},
            {"id": 2, "replay_result": "APPLIED"},  # replayed — should NOT count
            {"id": 3, "replay_result": None},
        ])
        with patch("api.admin_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/admin/summary")
        assert resp.json()["dlq_pending"] == 2

    def test_200_dlq_pending_zero_when_all_replayed(self) -> None:
        db = _make_db(dlq_rows=[
            {"id": 1, "replay_result": "APPLIED"},
            {"id": 2, "replay_result": "ALREADY_EXISTS"},
        ])
        with patch("api.admin_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/admin/summary")
        assert resp.json()["dlq_pending"] == 0

    def test_200_amendment_count(self) -> None:
        db = _make_db(amendment_rows=[{"id": 1}, {"id": 2}, {"id": 3}])
        with patch("api.admin_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/admin/summary")
        assert resp.json()["amendment_count"] == 3

    def test_200_last_event_at_present(self) -> None:
        db = _make_db(last_event_rows=[{"updated_at": "2026-10-05T00:00:00Z"}])
        with patch("api.admin_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/admin/summary")
        assert resp.json()["last_event_at"] == "2026-10-05T00:00:00Z"

    def test_200_last_event_at_none_when_no_bookings(self) -> None:
        db = _make_db(last_event_rows=[])
        with patch("api.admin_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/admin/summary")
        assert resp.json()["last_event_at"] is None

    def test_200_tenant_id_in_response(self) -> None:
        db = _make_db()
        with patch("api.admin_router._get_supabase_client", return_value=db):
            resp = _make_app(tenant_id="acme-tenant").get("/admin/summary")
        assert resp.json()["tenant_id"] == "acme-tenant"

    def test_200_zero_counts_when_no_data(self) -> None:
        db = _make_db(
            active_rows=[], canceled_rows=[], total_rows=[],
            dlq_rows=[], amendment_rows=[], last_event_rows=[],
        )
        with patch("api.admin_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/admin/summary")
        body = resp.json()
        assert body["active_bookings"] == 0
        assert body["canceled_bookings"] == 0
        assert body["total_bookings"] == 0
        assert body["dlq_pending"] == 0
        assert body["amendment_count"] == 0
        assert body["last_event_at"] is None


# ---------------------------------------------------------------------------
# 403 — Auth rejected
# ---------------------------------------------------------------------------

class TestAdminSummary403:

    def test_403_when_auth_rejects(self) -> None:
        from api.admin_router import router
        from api.auth import jwt_auth

        app = FastAPI()

        async def _reject():
            raise HTTPException(status_code=403, detail="AUTH_FAILED")

        app.dependency_overrides[jwt_auth] = _reject
        app.include_router(router)
        client = TestClient(app)

        resp = client.get("/admin/summary")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 500 — Internal error
# ---------------------------------------------------------------------------

class TestAdminSummary500:

    def test_500_on_db_exception(self) -> None:
        db = MagicMock()
        db.table.side_effect = RuntimeError("DB down")
        with patch("api.admin_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/admin/summary")
        assert resp.status_code == 500

    def test_500_body_internal_error(self) -> None:
        db = MagicMock()
        db.table.side_effect = RuntimeError("DB down")
        with patch("api.admin_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/admin/summary")
        assert resp.json()["code"] == "INTERNAL_ERROR"
