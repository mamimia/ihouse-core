"""
Phase 71 — Contract tests for GET /bookings/{booking_id}

Uses FastAPI TestClient + patch on _get_supabase_client — no live DB required.
Mirrors the financial_router test pattern exactly.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app(tenant_id: str = "tenant-a") -> TestClient:
    """Minimal FastAPI app with bookings_router registered and jwt_auth stubbed."""
    from api.bookings_router import router
    from api.auth import jwt_auth

    app = FastAPI()

    async def _stub_auth() -> str:
        return tenant_id

    app.dependency_overrides[jwt_auth] = _stub_auth
    app.include_router(router)
    return TestClient(app)


def _mock_db(data: list) -> MagicMock:
    db = MagicMock()
    (
        db.table.return_value
        .select.return_value
        .eq.return_value
        .eq.return_value
        .limit.return_value
        .execute.return_value
    ) = MagicMock(data=data)
    return db


def _row(
    booking_id: str = "bookingcom_res1",
    tenant_id: str = "tenant-a",
    status: str = "active",
    check_in: str | None = "2026-10-01",
    check_out: str | None = "2026-10-05",
    version: int = 1,
) -> dict:
    return {
        "booking_id": booking_id,
        "tenant_id": tenant_id,
        "source": "bookingcom",
        "reservation_ref": "res1",
        "property_id": "prop1",
        "status": status,
        "check_in": check_in,
        "check_out": check_out,
        "version": version,
        "created_at": "2026-10-01T00:00:00Z",
        "updated_at": "2026-10-01T00:00:00Z",
    }


# ---------------------------------------------------------------------------
# 200 — Happy path
# ---------------------------------------------------------------------------

class TestGetBooking200:

    def test_200_when_booking_found(self) -> None:
        db = _mock_db([_row()])
        with patch("api.bookings_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/bookings/bookingcom_res1")
        assert resp.status_code == 200

    def test_200_booking_id_in_response(self) -> None:
        db = _mock_db([_row()])
        with patch("api.bookings_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/bookings/bookingcom_res1")
        assert resp.json()["booking_id"] == "bookingcom_res1"

    def test_200_all_fields_present(self) -> None:
        db = _mock_db([_row()])
        with patch("api.bookings_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/bookings/bookingcom_res1")
        body = resp.json()
        for field in ("booking_id", "tenant_id", "source", "reservation_ref",
                      "property_id", "status", "check_in", "check_out",
                      "version", "created_at", "updated_at"):
            assert field in body, f"Missing field: {field}"

    def test_200_status_active(self) -> None:
        db = _mock_db([_row(status="active")])
        with patch("api.bookings_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/bookings/bookingcom_res1")
        assert resp.json()["status"] == "active"

    def test_200_status_canceled(self) -> None:
        db = _mock_db([_row(status="canceled")])
        with patch("api.bookings_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/bookings/bookingcom_res1")
        assert resp.json()["status"] == "canceled"

    def test_200_check_in_check_out_present(self) -> None:
        db = _mock_db([_row(check_in="2026-11-01", check_out="2026-11-05")])
        with patch("api.bookings_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/bookings/bookingcom_res1")
        body = resp.json()
        assert body["check_in"] == "2026-11-01"
        assert body["check_out"] == "2026-11-05"

    def test_200_check_in_none_when_absent(self) -> None:
        db = _mock_db([_row(check_in=None, check_out=None)])
        with patch("api.bookings_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/bookings/bookingcom_res1")
        body = resp.json()
        assert body["check_in"] is None
        assert body["check_out"] is None

    def test_200_version_returned(self) -> None:
        db = _mock_db([_row(version=3)])
        with patch("api.bookings_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/bookings/bookingcom_res1")
        assert resp.json()["version"] == 3

    def test_200_reads_booking_state_table(self) -> None:
        """Verifies the endpoint queries booking_state, not event_log."""
        db = _mock_db([_row()])
        with patch("api.bookings_router._get_supabase_client", return_value=db):
            _make_app().get("/bookings/bookingcom_res1")
        db.table.assert_called_with("booking_state")


# ---------------------------------------------------------------------------
# 404 — Not found / tenant isolation
# ---------------------------------------------------------------------------

class TestGetBooking404:

    def test_404_when_booking_not_found(self) -> None:
        db = _mock_db([])
        with patch("api.bookings_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/bookings/nonexistent")
        assert resp.status_code == 404

    def test_404_body_error_code(self) -> None:
        db = _mock_db([])
        with patch("api.bookings_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/bookings/nonexistent")
        assert resp.json()["error"] == "BOOKING_NOT_FOUND"

    def test_404_body_includes_booking_id(self) -> None:
        db = _mock_db([])
        with patch("api.bookings_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/bookings/bookingcom_res999")
        assert resp.json()["booking_id"] == "bookingcom_res999"

    def test_404_cross_tenant_returns_404_not_403(self) -> None:
        """Tenant isolation: cross-tenant reads return 404, not 403."""
        # DB returns empty because DB-level .eq("tenant_id", ...) filters out other tenant
        db = _mock_db([])
        with patch("api.bookings_router._get_supabase_client", return_value=db):
            resp = _make_app(tenant_id="wrong-tenant").get("/bookings/bookingcom_res1")
        assert resp.status_code == 404
        assert resp.status_code != 403


# ---------------------------------------------------------------------------
# 401 — Auth failure
# ---------------------------------------------------------------------------

class TestGetBooking401:

    def test_401_when_auth_rejects(self) -> None:
        """jwt_auth raises 403 on missing/invalid token."""
        from api.bookings_router import router
        from api.auth import jwt_auth

        app = FastAPI()

        async def _reject_auth():
            raise HTTPException(status_code=403, detail="AUTH_FAILED")

        app.dependency_overrides[jwt_auth] = _reject_auth
        app.include_router(router)
        client = TestClient(app)

        resp = client.get("/bookings/bookingcom_res1")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 500 — Internal error
# ---------------------------------------------------------------------------

class TestGetBooking500:

    def test_500_on_db_exception(self) -> None:
        db = MagicMock()
        db.table.side_effect = RuntimeError("connection lost")
        with patch("api.bookings_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/bookings/bookingcom_res1")
        assert resp.status_code == 500

    def test_500_body_contains_internal_error(self) -> None:
        db = MagicMock()
        db.table.side_effect = RuntimeError("connection lost")
        with patch("api.bookings_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/bookings/bookingcom_res1")
        assert resp.json()["error"] == "INTERNAL_ERROR"
