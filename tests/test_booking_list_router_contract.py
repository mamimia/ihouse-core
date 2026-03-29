"""
Phase 106 — Booking List Query API Contract Tests

GET /bookings — list bookings from booking_state with optional filters.

Uses FastAPI TestClient + mocked Supabase — no live DB required.
Pattern: identical to test_bookings_router_contract.py (Phase 71).

Structure:
  Group A — Happy path: 200, list returned
  Group B — Filter by status=active / canceled
  Group C — Filter by property_id
  Group D — limit query param (clamp, default)
  Group E — Invalid status → 400
  Group F — Auth (403), tenant isolation
  Group G — 500 error handling
  Group H — Empty results (tenant has no bookings)
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.auth import jwt_auth
from api.bookings_router import router


# ---------------------------------------------------------------------------
# Test app factories
# ---------------------------------------------------------------------------

def _make_app(tenant: str = "tenant_test") -> TestClient:
    app = FastAPI()

    async def _stub():
        return tenant

    app.dependency_overrides[jwt_auth] = _stub
    app.include_router(router)
    return TestClient(app)


def _reject_app() -> TestClient:
    app = FastAPI()

    async def _reject():
        raise HTTPException(status_code=403, detail="AUTH_FAILED")

    app.dependency_overrides[jwt_auth] = _reject
    app.include_router(router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Booking row fixture
# ---------------------------------------------------------------------------

def _booking_row(
    booking_id: str = "bookingcom_BK-001",
    tenant_id: str = "tenant_test",
    source: str = "bookingcom",
    property_id: str = "prop-001",
    status: str = "active",
    check_in: str = "2026-07-01",
    check_out: str = "2026-07-07",
    version: int = 1,
    reservation_ref: str = "BK-001",
    created_at: str = "2026-06-01T10:00:00+00:00",
    updated_at: str = "2026-06-01T10:00:01+00:00",
) -> dict:
    return {
        "booking_id": booking_id,
        "tenant_id": tenant_id,
        "source": source,
        "reservation_ref": reservation_ref,
        "property_id": property_id,
        "status": status,
        "check_in": check_in,
        "check_out": check_out,
        "version": version,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def _mock_db(rows: list) -> MagicMock:
    """Mock returning the given rows for .execute()."""
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=rows)
    for method in ['select', 'eq', 'limit', 'order', 'or_']:
        getattr(chain, method).return_value = chain
    mock_db = MagicMock()
    mock_db.table.return_value = chain
    return mock_db


# ---------------------------------------------------------------------------
# Group A — Happy path
# ---------------------------------------------------------------------------

class TestGroupAHappyPath:

    def test_a1_returns_200(self) -> None:
        rows = [_booking_row()]
        mock_db = _mock_db(rows)
        client = _make_app()
        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/bookings")
        assert resp.status_code == 200

    def test_a2_response_has_bookings_key(self) -> None:
        rows = [_booking_row()]
        mock_db = _mock_db(rows)
        client = _make_app()
        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            body = client.get("/bookings").json()["data"]
        assert "bookings" in body

    def test_a3_response_has_count(self) -> None:
        rows = [_booking_row(), _booking_row(booking_id="bookingcom_BK-002")]
        mock_db = _mock_db(rows)
        client = _make_app()
        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            body = client.get("/bookings").json()["data"]
        assert body["count"] == 2

    def test_a4_response_has_tenant_id(self) -> None:
        mock_db = _mock_db([_booking_row()])
        client = _make_app(tenant="tenant_xyz")
        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            body = client.get("/bookings").json()["data"]
        assert body["tenant_id"] == "tenant_xyz"

    def test_a5_response_has_limit(self) -> None:
        mock_db = _mock_db([_booking_row()])
        client = _make_app()
        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            body = client.get("/bookings").json()["data"]
        assert "limit" in body

    def test_a6_booking_entry_has_booking_id(self) -> None:
        mock_db = _mock_db([_booking_row(booking_id="bookingcom_BK-001")])
        client = _make_app()
        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            body = client.get("/bookings").json()["data"]
        assert body["bookings"][0]["booking_id"] == "bookingcom_BK-001"

    def test_a7_booking_entry_has_status(self) -> None:
        mock_db = _mock_db([_booking_row(status="active")])
        client = _make_app()
        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            body = client.get("/bookings").json()["data"]
        assert body["bookings"][0]["status"] == "active"

    def test_a8_booking_entry_has_property_id(self) -> None:
        mock_db = _mock_db([_booking_row(property_id="prop-99")])
        client = _make_app()
        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            body = client.get("/bookings").json()["data"]
        assert body["bookings"][0]["property_id"] == "prop-99"

    def test_a9_booking_entry_has_check_in_check_out(self) -> None:
        mock_db = _mock_db([_booking_row(check_in="2026-08-01", check_out="2026-08-07")])
        client = _make_app()
        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            body = client.get("/bookings").json()["data"]
        entry = body["bookings"][0]
        assert entry["check_in"] == "2026-08-01"
        assert entry["check_out"] == "2026-08-07"

    def test_a10_all_required_fields_present(self) -> None:
        mock_db = _mock_db([_booking_row()])
        client = _make_app()
        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            body = client.get("/bookings").json()["data"]
        required = {"booking_id", "tenant_id", "source", "reservation_ref",
                    "property_id", "status", "check_in", "check_out",
                    "version", "created_at", "updated_at"}
        assert required.issubset(set(body["bookings"][0].keys()))


# ---------------------------------------------------------------------------
# Group B — Filter by status
# ---------------------------------------------------------------------------

class TestGroupBStatusFilter:

    def test_b1_status_active_returns_200(self) -> None:
        mock_db = _mock_db([_booking_row(status="active")])
        client = _make_app()
        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/bookings?status=active")
        assert resp.status_code == 200

    def test_b2_status_canceled_returns_200(self) -> None:
        mock_db = _mock_db([_booking_row(status="canceled")])
        client = _make_app()
        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/bookings?status=canceled")
        assert resp.status_code == 200

    def test_b3_invalid_status_returns_400(self) -> None:
        mock_db = _mock_db([])
        client = _make_app()
        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/bookings?status=INVALID")
        assert resp.status_code == 400

    def test_b4_invalid_status_code_is_validation_error(self) -> None:
        mock_db = _mock_db([])
        client = _make_app()
        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            body = client.get("/bookings?status=pending").json()
        assert body["error"]["code"] == "VALIDATION_ERROR"

    def test_b5_invalid_status_does_not_hit_db(self) -> None:
        """Validation happens before DB call — client should not be invoked."""
        mock_db = MagicMock()
        client = _make_app()
        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            client.get("/bookings?status=bogus")
        mock_db.table.assert_not_called()


# ---------------------------------------------------------------------------
# Group C — Filter by property_id
# ---------------------------------------------------------------------------

class TestGroupCPropertyFilter:

    def test_c1_property_id_filter_returns_200(self) -> None:
        mock_db = _mock_db([_booking_row(property_id="prop-42")])
        client = _make_app()
        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/bookings?property_id=prop-42")
        assert resp.status_code == 200

    def test_c2_response_bookings_have_matching_property(self) -> None:
        mock_db = _mock_db([_booking_row(property_id="prop-42")])
        client = _make_app()
        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            body = client.get("/bookings?property_id=prop-42").json()["data"]
        assert body["bookings"][0]["property_id"] == "prop-42"

    def test_c3_combined_property_and_status_filter(self) -> None:
        mock_db = _mock_db([_booking_row(property_id="prop-1", status="active")])
        client = _make_app()
        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/bookings?property_id=prop-1&status=active")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Group D — limit param
# ---------------------------------------------------------------------------

class TestGroupDLimit:

    def test_d1_default_limit_is_50(self) -> None:
        mock_db = _mock_db([])
        client = _make_app()
        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            body = client.get("/bookings").json()["data"]
        assert body["limit"] == 50

    def test_d2_custom_limit_reflected_in_response(self) -> None:
        mock_db = _mock_db([_booking_row()])
        client = _make_app()
        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            body = client.get("/bookings?limit=10").json()["data"]
        assert body["limit"] == 10

    def test_d3_limit_clamped_to_100(self) -> None:
        mock_db = _mock_db([])
        client = _make_app()
        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            body = client.get("/bookings?limit=999").json()["data"]
        assert body["limit"] == 100

    def test_d4_limit_clamped_to_minimum_1(self) -> None:
        mock_db = _mock_db([])
        client = _make_app()
        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            body = client.get("/bookings?limit=0").json()["data"]
        assert body["limit"] == 1


# ---------------------------------------------------------------------------
# Group E — Auth
# ---------------------------------------------------------------------------

class TestGroupEAuth:

    def test_e1_no_auth_returns_403(self) -> None:
        resp = _reject_app().get("/bookings")
        assert resp.status_code == 403

    def test_e2_valid_auth_gets_200(self) -> None:
        mock_db = _mock_db([_booking_row()])
        client = _make_app(tenant="my_org")
        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/bookings")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Group F — Empty results
# ---------------------------------------------------------------------------

class TestGroupFEmpty:

    def test_f1_empty_result_returns_200(self) -> None:
        mock_db = _mock_db([])
        client = _make_app()
        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/bookings")
        assert resp.status_code == 200

    def test_f2_empty_result_count_is_zero(self) -> None:
        mock_db = _mock_db([])
        client = _make_app()
        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            body = client.get("/bookings").json()["data"]
        assert body["count"] == 0
        assert body["bookings"] == []


# ---------------------------------------------------------------------------
# Group G — 500 error
# ---------------------------------------------------------------------------

class TestGroupG500:

    def test_g1_db_error_returns_500(self) -> None:
        mock_db = _mock_db([])
        mock_db.table.return_value.execute.side_effect = RuntimeError("connection lost")
        client = _make_app()
        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/bookings")
        assert resp.status_code == 500

    def test_g2_500_code_is_internal_error(self) -> None:
        mock_db = _mock_db([])
        mock_db.table.return_value.execute.side_effect = RuntimeError("timeout")
        client = _make_app()
        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            body = client.get("/bookings").json()
        assert body["error"]["code"] == "INTERNAL_ERROR"
