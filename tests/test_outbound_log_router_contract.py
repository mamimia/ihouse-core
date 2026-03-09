"""
Phase 145 — Contract Tests: Outbound Sync Log Inspector API

Groups:
  A — GET /admin/outbound-log: list with no filters
  B — GET /admin/outbound-log: filter by booking_id
  C — GET /admin/outbound-log: filter by provider
  D — GET /admin/outbound-log: filter by status (all 4 valid values)
  E — GET /admin/outbound-log: limit parameter
  F — GET /admin/outbound-log: invalid status → 400
  G — GET /admin/outbound-log/{booking_id}: found
  H — GET /admin/outbound-log/{booking_id}: not found → 404
  I — Tenant isolation (query is scoped by tenant_id)
  J — Router smoke test: routes + methods
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("fastapi")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TENANT_A   = "tenant-A"
TENANT_B   = "tenant-B"
BOOKING_1  = "airbnb_BK001"
BOOKING_2  = "bookingcom_BK002"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_row(
    booking_id:  str = BOOKING_1,
    tenant_id:   str = TENANT_A,
    provider:    str = "airbnb",
    status:      str = "ok",
    http_status: Optional[int] = 200,
    strategy:    str = "api_first",
    external_id: str = "EXT-1",
    message:     str = "ok",
    synced_at:   str = "2026-03-10T01:00:00+00:00",
    row_id:      int = 1,
) -> dict:
    return {
        "id":          row_id,
        "booking_id":  booking_id,
        "tenant_id":   tenant_id,
        "provider":    provider,
        "external_id": external_id,
        "strategy":    strategy,
        "status":      status,
        "http_status": http_status,
        "message":     message,
        "synced_at":   synced_at,
    }


def _make_db(rows: List[dict]) -> MagicMock:
    q = MagicMock()
    q.eq.return_value = q
    q.order.return_value = q
    q.limit.return_value = q
    q.execute.return_value = MagicMock(data=rows)
    db = MagicMock()
    db.table.return_value.select.return_value = q
    return db


def _make_app() -> TestClient:
    from fastapi import FastAPI
    from api.outbound_log_router import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def _get(
    path: str,
    rows: Optional[List[dict]] = None,
    tenant_id: str = TENANT_A,
    params: Optional[dict] = None,
) -> tuple[Any, MagicMock]:
    db = _make_db(rows or [])
    c  = _make_app()
    with (
        patch("api.outbound_log_router._get_supabase_client", return_value=db),
        patch("api.auth.jwt_auth", return_value=tenant_id),
    ):
        resp = c.get(
            path,
            headers={"Authorization": "Bearer fake.jwt"},
            params=params or {},
        )
    return resp, db


# ===========================================================================
# Group A — list with no filters
# ===========================================================================

class TestListNoFilters:

    def test_returns_200(self):
        resp, _ = _get("/admin/outbound-log")
        assert resp.status_code == 200

    def test_response_shape(self):
        rows = [_make_row()]
        resp, _ = _get("/admin/outbound-log", rows=rows)
        body = resp.json()
        assert "tenant_id" in body
        assert "count" in body
        assert "limit" in body
        assert "entries" in body

    def test_count_matches_rows(self):
        rows = [_make_row(row_id=1), _make_row(row_id=2)]
        resp, _ = _get("/admin/outbound-log", rows=rows)
        assert resp.json()["count"] == 2

    def test_empty_list_round_trips(self):
        resp, _ = _get("/admin/outbound-log", rows=[])
        assert resp.json()["entries"] == []
        assert resp.json()["count"] == 0


# ===========================================================================
# Group B — filter by booking_id
# ===========================================================================

class TestFilterBookingId:

    def test_booking_id_rows_returned(self):
        rows = [_make_row(booking_id=BOOKING_1)]
        resp, _ = _get("/admin/outbound-log", rows=rows, params={"booking_id": BOOKING_1})
        assert resp.status_code == 200
        assert resp.json()["entries"][0]["booking_id"] == BOOKING_1

    def test_no_rows_for_unknown_booking(self):
        resp, _ = _get("/admin/outbound-log", rows=[], params={"booking_id": "nonexistent"})
        assert resp.json()["count"] == 0


# ===========================================================================
# Group C — filter by provider
# ===========================================================================

class TestFilterProvider:

    def test_provider_filter_accepted(self):
        rows = [_make_row(provider="bookingcom")]
        resp, _ = _get("/admin/outbound-log", rows=rows, params={"provider": "bookingcom"})
        assert resp.status_code == 200
        assert resp.json()["entries"][0]["provider"] == "bookingcom"


# ===========================================================================
# Group D — filter by status
# ===========================================================================

class TestFilterStatus:

    @pytest.mark.parametrize("status", ["ok", "failed", "dry_run", "skipped"])
    def test_all_valid_statuses_accepted(self, status):
        rows = [_make_row(status=status)]
        resp, _ = _get("/admin/outbound-log", rows=rows, params={"status": status})
        assert resp.status_code == 200

    def test_status_field_in_returned_entry(self):
        rows = [_make_row(status="failed")]
        resp, _ = _get("/admin/outbound-log", rows=rows, params={"status": "failed"})
        assert resp.json()["entries"][0]["status"] == "failed"


# ===========================================================================
# Group E — limit parameter
# ===========================================================================

class TestLimit:

    def test_default_limit_is_50(self):
        resp, _ = _get("/admin/outbound-log", rows=[])
        assert resp.json()["limit"] == 50

    def test_custom_limit_returned(self):
        resp, _ = _get("/admin/outbound-log", rows=[], params={"limit": 100})
        assert resp.json()["limit"] == 100

    def test_max_limit_200_accepted(self):
        resp, _ = _get("/admin/outbound-log", rows=[], params={"limit": 200})
        assert resp.status_code == 200
        assert resp.json()["limit"] == 200

    def test_limit_above_max_returns_422(self):
        resp, _ = _get("/admin/outbound-log", rows=[], params={"limit": 201})
        # FastAPI validates the Query constraint automatically
        assert resp.status_code == 422


# ===========================================================================
# Group F — invalid status → 400
# ===========================================================================

class TestInvalidStatus:

    def test_invalid_status_returns_400(self):
        resp, _ = _get("/admin/outbound-log", rows=[], params={"status": "INVALID"})
        assert resp.status_code == 400

    def test_400_body_has_code_field(self):
        resp, _ = _get("/admin/outbound-log", rows=[], params={"status": "whatever"})
        body = resp.json()
        assert "code" in body


# ===========================================================================
# Group G — GET /admin/outbound-log/{booking_id}: found
# ===========================================================================

class TestGetByBookingIdFound:

    def test_returns_200(self):
        rows = [_make_row(booking_id=BOOKING_1)]
        resp, _ = _get(f"/admin/outbound-log/{BOOKING_1}", rows=rows)
        assert resp.status_code == 200

    def test_response_contains_booking_id(self):
        rows = [_make_row(booking_id=BOOKING_1)]
        resp, _ = _get(f"/admin/outbound-log/{BOOKING_1}", rows=rows)
        assert resp.json()["booking_id"] == BOOKING_1

    def test_response_count_matches_entries(self):
        rows = [_make_row(booking_id=BOOKING_1, row_id=1),
                _make_row(booking_id=BOOKING_1, row_id=2)]
        resp, _ = _get(f"/admin/outbound-log/{BOOKING_1}", rows=rows)
        body = resp.json()
        assert body["count"] == 2
        assert len(body["entries"]) == 2

    def test_entry_has_required_fields(self):
        rows = [_make_row(booking_id=BOOKING_1)]
        resp, _ = _get(f"/admin/outbound-log/{BOOKING_1}", rows=rows)
        entry = resp.json()["entries"][0]
        for field in ("id", "booking_id", "provider", "status", "synced_at"):
            assert field in entry, f"Missing field: {field}"


# ===========================================================================
# Group H — GET /admin/outbound-log/{booking_id}: not found → 404
# ===========================================================================

class TestGetByBookingIdNotFound:

    def test_no_rows_returns_404(self):
        resp, _ = _get("/admin/outbound-log/ghost_booking", rows=[])
        assert resp.status_code == 404

    def test_404_body_has_code_field(self):
        resp, _ = _get("/admin/outbound-log/ghost_booking", rows=[])
        body = resp.json()
        assert "code" in body


# ===========================================================================
# Group I — tenant isolation
# ===========================================================================

class TestTenantIsolation:

    def test_tenant_id_from_jwt_is_used_in_query(self):
        """The tenant_id from jwt_auth is always passed as the first .eq() filter."""
        rows = [_make_row()]
        resp, db = _get("/admin/outbound-log", rows=rows)
        assert resp.status_code == 200

        # The tenant_id in the response body
        response_tenant = resp.json()["tenant_id"]

        # The first eq() call on the Supabase query must use that same tenant_id
        q = db.table.return_value.select.return_value
        first_eq = q.eq.call_args_list[0][0]
        assert first_eq[0] == "tenant_id"
        assert first_eq[1] == response_tenant   # same value JWT returned

    def test_query_always_scopes_by_tenant_not_global(self):
        """The list endpoint requires a tenant_id eq() filter — never queries globally."""
        resp, db = _get("/admin/outbound-log", rows=[])
        assert resp.status_code == 200

        q = db.table.return_value.select.return_value
        eq_fields = [call[0][0] for call in q.eq.call_args_list]
        assert "tenant_id" in eq_fields   # tenant scoping MUST be present


# ===========================================================================
# Group J — router smoke tests
# ===========================================================================

class TestRouterSmoke:

    def test_router_has_list_route(self):
        from api.outbound_log_router import router
        paths = [r.path for r in router.routes]  # type: ignore[attr-defined]
        assert "/admin/outbound-log" in paths

    def test_router_has_booking_detail_route(self):
        from api.outbound_log_router import router
        paths = [r.path for r in router.routes]  # type: ignore[attr-defined]
        assert "/admin/outbound-log/{booking_id}" in paths

    def test_list_route_uses_get(self):
        from api.outbound_log_router import router
        r = next(x for x in router.routes if x.path == "/admin/outbound-log")  # type: ignore[attr-defined]
        assert "GET" in r.methods  # type: ignore[attr-defined]

    def test_detail_route_uses_get(self):
        from api.outbound_log_router import router
        r = next(x for x in router.routes if x.path == "/admin/outbound-log/{booking_id}")  # type: ignore[attr-defined]
        assert "GET" in r.methods  # type: ignore[attr-defined]
