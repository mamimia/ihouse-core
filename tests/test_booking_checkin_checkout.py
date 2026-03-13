"""
Phase 398 — Booking Check-in / Check-out — Contract Tests
===========================================================

Tests that:
    1. POST /bookings/{id}/checkin returns correct states
    2. POST /bookings/{id}/checkout returns correct states
    3. Booking not found returns 404
    4. Invalid state transitions return 409
    5. Idempotent operations succeed
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("IHOUSE_JWT_SECRET", "test-secret-for-checkin")
    monkeypatch.setenv("IHOUSE_DEV_MODE", "true")
    monkeypatch.setenv("IHOUSE_DEV_PASSWORD", "dev")
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-key")


@pytest.fixture()
def client():
    from main import app
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def auth_header(client):
    """Get a valid auth token header."""
    resp = client.post("/auth/token", json={"tenant_id": "t1", "secret": "dev"})
    return {"Authorization": f"Bearer {resp.json()['data']['token']}"}


def _mock_booking(status="active"):
    """Create a mock booking row."""
    return {
        "booking_id": "bk-001",
        "tenant_id": "dev-tenant",
        "status": status,
        "property_id": "prop-1",
        "check_in": "2025-03-15",
        "check_out": "2025-03-18",
        "source": "airbnb",
    }


class TestCheckinEndpoint:
    """Tests for POST /bookings/{booking_id}/checkin."""

    def test_checkin_returns_404_without_booking(self, client, auth_header):
        """Non-existent booking should return 404."""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = mock_result

        with patch("api.booking_checkin_router._get_supabase_client", return_value=mock_db):
            resp = client.post("/bookings/bk-999/checkin", headers=auth_header)
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "BOOKING_NOT_FOUND"

    def test_checkin_active_booking_succeeds(self, client, auth_header):
        """Active booking should transition to checked_in."""
        mock_db = MagicMock()
        # _get_booking returns an active booking
        mock_select_result = MagicMock()
        mock_select_result.data = [_mock_booking("active")]
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = mock_select_result
        # update returns success
        mock_db.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock()
        # audit inserts succeed
        mock_db.table.return_value.insert.return_value.execute.return_value = MagicMock()

        with patch("api.booking_checkin_router._get_supabase_client", return_value=mock_db):
            resp = client.post("/bookings/bk-001/checkin", headers=auth_header)
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["status"] == "checked_in"
        assert body["noop"] is False

    def test_checkin_already_checked_in_is_idempotent(self, client, auth_header):
        """Already checked-in booking should return 200 with noop=True."""
        mock_db = MagicMock()
        mock_select_result = MagicMock()
        mock_select_result.data = [_mock_booking("checked_in")]
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = mock_select_result

        with patch("api.booking_checkin_router._get_supabase_client", return_value=mock_db):
            resp = client.post("/bookings/bk-001/checkin", headers=auth_header)
        assert resp.status_code == 200
        assert resp.json()["data"]["noop"] is True

    def test_checkin_canceled_booking_returns_409(self, client, auth_header):
        """Canceled booking should not be checkable-in."""
        mock_db = MagicMock()
        mock_select_result = MagicMock()
        mock_select_result.data = [_mock_booking("canceled")]
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = mock_select_result

        with patch("api.booking_checkin_router._get_supabase_client", return_value=mock_db):
            resp = client.post("/bookings/bk-001/checkin", headers=auth_header)
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "INVALID_STATE"


class TestCheckoutEndpoint:
    """Tests for POST /bookings/{booking_id}/checkout."""

    def test_checkout_returns_404_without_booking(self, client, auth_header):
        """Non-existent booking should return 404."""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = mock_result

        with patch("api.booking_checkin_router._get_supabase_client", return_value=mock_db):
            resp = client.post("/bookings/bk-999/checkout", headers=auth_header)
        assert resp.status_code == 404

    def test_checkout_checked_in_booking_succeeds(self, client, auth_header):
        """Checked-in booking should transition to checked_out."""
        mock_db = MagicMock()
        mock_select_result = MagicMock()
        mock_select_result.data = [_mock_booking("checked_in")]
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = mock_select_result
        mock_db.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_db.table.return_value.insert.return_value.execute.return_value = MagicMock()

        with patch("api.booking_checkin_router._get_supabase_client", return_value=mock_db):
            with patch("tasks.task_writer.write_tasks_for_booking_created", return_value=1):
                resp = client.post("/bookings/bk-001/checkout", headers=auth_header)
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["status"] == "checked_out"
        assert body["noop"] is False

    def test_checkout_already_checked_out_is_idempotent(self, client, auth_header):
        """Already checked-out booking should return 200 with noop=True."""
        mock_db = MagicMock()
        mock_select_result = MagicMock()
        mock_select_result.data = [_mock_booking("checked_out")]
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = mock_select_result

        with patch("api.booking_checkin_router._get_supabase_client", return_value=mock_db):
            resp = client.post("/bookings/bk-001/checkout", headers=auth_header)
        assert resp.status_code == 200
        assert resp.json()["data"]["noop"] is True

    def test_checkout_canceled_booking_returns_409(self, client, auth_header):
        """Canceled booking cannot be checked out."""
        mock_db = MagicMock()
        mock_select_result = MagicMock()
        mock_select_result.data = [_mock_booking("canceled")]
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = mock_select_result

        with patch("api.booking_checkin_router._get_supabase_client", return_value=mock_db):
            resp = client.post("/bookings/bk-001/checkout", headers=auth_header)
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "INVALID_STATE"

    def test_checkin_endpoint_exists(self, client, auth_header):
        """Check-in endpoint exists and is reachable with auth."""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = mock_result
        with patch("api.booking_checkin_router._get_supabase_client", return_value=mock_db):
            resp = client.post("/bookings/bk-001/checkin", headers=auth_header)
        # Should get 404 (booking not found), NOT 405 (method not allowed)
        assert resp.status_code == 404

    def test_checkout_endpoint_exists(self, client, auth_header):
        """Check-out endpoint exists and is reachable with auth."""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = mock_result
        with patch("api.booking_checkin_router._get_supabase_client", return_value=mock_db):
            resp = client.post("/bookings/bk-001/checkout", headers=auth_header)
        assert resp.status_code == 404
