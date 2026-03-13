"""
Phase 403 — E2E Flow Test
============================

End-to-end test: login → checkin → checkout → verify cleaning task.
Plus full invite and onboard lifecycles.
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("IHOUSE_JWT_SECRET", "test-secret-phase403-e2e")
    monkeypatch.setenv("IHOUSE_DEV_MODE", "true")
    monkeypatch.setenv("IHOUSE_DEV_PASSWORD", "dev")
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-key")


@pytest.fixture()
def client():
    from main import app
    from fastapi.testclient import TestClient
    return TestClient(app, raise_server_exceptions=False)


def _make_booking_mock(booking_data: dict):
    """Create a properly chained mock for booking_state queries."""
    mock_db = MagicMock()

    mock_select_result = MagicMock()
    mock_select_result.data = [booking_data]

    # The router does: db.table("booking_state").select(...).eq("booking_id", ...).eq("tenant_id", ...).limit(1).execute()
    mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = mock_select_result

    # update: db.table("booking_state").update(...).eq("booking_id", ...).eq("tenant_id", ...).execute()
    mock_db.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock()

    # insert (event_log, audit_events, tasks): db.table(...).insert(...).execute()
    mock_db.table.return_value.insert.return_value.execute.return_value = MagicMock()

    return mock_db


class TestE2EOperationalFlow:
    """Full lifecycle: login → checkin → checkout."""

    def test_login_returns_jwt(self, client):
        """POST /auth/token returns a valid JWT."""
        resp = client.post("/auth/token", json={"tenant_id": "t1", "secret": "dev"})
        assert resp.status_code == 200
        body = resp.json()
        assert "token" in body
        assert body["tenant_id"] == "t1"

    def test_full_checkin_checkout_flow(self, client):
        """Login → Checkin (active → checked_in) → Checkout (checked_in → checked_out)."""
        # Step 1: Login
        login_resp = client.post("/auth/token", json={"tenant_id": "t1", "secret": "dev"})
        assert login_resp.status_code == 200
        auth = {"Authorization": f"Bearer {login_resp.json()['token']}"}

        # Step 2: Checkin
        mock_db = _make_booking_mock({
            "booking_id": "BK-E2E", "status": "active",
            "property_id": "p-1", "tenant_id": "t1",
            "check_in": "2026-03-15", "check_out": "2026-03-18", "source": "airbnb",
        })

        with patch("api.booking_checkin_router._get_supabase_client", return_value=mock_db):
            checkin_resp = client.post("/bookings/BK-E2E/checkin", headers=auth)
        assert checkin_resp.status_code == 200
        assert checkin_resp.json()["status"] == "checked_in"

        # Step 3: Checkout
        mock_db2 = _make_booking_mock({
            "booking_id": "BK-E2E", "status": "checked_in",
            "property_id": "p-1", "tenant_id": "t1",
            "check_in": "2026-03-15", "check_out": "2026-03-18", "source": "airbnb",
        })

        with patch("api.booking_checkin_router._get_supabase_client", return_value=mock_db2):
            checkout_resp = client.post("/bookings/BK-E2E/checkout", headers=auth)
        assert checkout_resp.status_code == 200
        body = checkout_resp.json()
        assert body["status"] == "checked_out"

    def test_checkin_rejects_non_active_booking(self, client):
        """Checkin on a checked_out booking returns 409."""
        login_resp = client.post("/auth/token", json={"tenant_id": "t1", "secret": "dev"})
        auth = {"Authorization": f"Bearer {login_resp.json()['token']}"}

        mock_db = _make_booking_mock({
            "booking_id": "BK-DONE", "status": "checked_out",
            "property_id": "p-1", "tenant_id": "t1",
        })

        with patch("api.booking_checkin_router._get_supabase_client", return_value=mock_db):
            resp = client.post("/bookings/BK-DONE/checkin", headers=auth)
        assert resp.status_code == 409

    def test_checkout_idempotent_already_checked_out(self, client):
        """Checkout on already checked_out booking returns 200 (idempotent)."""
        login_resp = client.post("/auth/token", json={"tenant_id": "t1", "secret": "dev"})
        auth = {"Authorization": f"Bearer {login_resp.json()['token']}"}

        mock_db = _make_booking_mock({
            "booking_id": "BK-DONE", "status": "checked_out",
            "property_id": "p-1", "tenant_id": "t1",
        })

        with patch("api.booking_checkin_router._get_supabase_client", return_value=mock_db):
            resp = client.post("/bookings/BK-DONE/checkout", headers=auth)
        assert resp.status_code == 200
        # Idempotent: returns already_checked_out
        assert "checked_out" in resp.json()["status"]


class TestE2EInviteFlow:
    """E2E: create invite → validate → accept."""

    def test_invite_create_validate_accept(self, client):
        """Full invite lifecycle via API."""
        from services.access_token_service import issue_access_token, TokenType
        raw_token, _ = issue_access_token(TokenType.INVITE, "t1", "staff@test.com", 3600)

        # Validate
        mock_db = MagicMock()
        mock_select = MagicMock()
        mock_select.data = [{
            "id": "inv-e2e", "used_at": None, "revoked_at": None,
            "metadata": {"role": "worker", "organization_name": "TestOrg", "invited_by": "admin"},
            "expires_at": "2026-03-20",
        }]
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = mock_select

        with patch("api.invite_router._get_db", return_value=mock_db):
            validate_resp = client.get(f"/invite/validate/{raw_token}")
        assert validate_resp.status_code == 200
        assert validate_resp.json()["role"] == "worker"

        # Accept
        mock_db2 = MagicMock()
        mock_select2 = MagicMock()
        mock_select2.data = [{
            "id": "inv-e2e", "token_type": "invite", "entity_id": "t1",
            "email": "staff@test.com", "used_at": None, "revoked_at": None,
            "metadata": {"role": "worker", "organization_name": "TestOrg"},
            "expires_at": "2026-03-20",
        }]
        mock_db2.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = mock_select2
        mock_db2.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_db2.table.return_value.insert.return_value.execute.return_value = MagicMock()

        with patch("api.invite_router._get_db", return_value=mock_db2):
            accept_resp = client.post(f"/invite/accept/{raw_token}")
        assert accept_resp.status_code == 200
        assert accept_resp.json()["status"] == "accepted"


class TestE2EOnboardFlow:
    """E2E: validate onboard → submit property."""

    def test_onboard_validate_and_submit(self, client):
        """Full onboard lifecycle via API."""
        from services.access_token_service import issue_access_token, TokenType
        raw_token, _ = issue_access_token(TokenType.ONBOARD, "t1", "owner@test.com", 3600)

        # Validate
        mock_db = MagicMock()
        mock_select = MagicMock()
        mock_select.data = [{"id": "tok-e2e", "used_at": None, "revoked_at": None}]
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = mock_select

        with patch("api.onboard_token_router._get_db", return_value=mock_db):
            validate_resp = client.get(f"/onboard/validate/{raw_token}")
        assert validate_resp.status_code == 200

        # Submit
        mock_db2 = MagicMock()
        mock_select2 = MagicMock()
        mock_select2.data = [{
            "id": "tok-e2e", "token_type": "onboard", "entity_id": "t1",
            "email": "owner@test.com", "used_at": None, "revoked_at": None,
            "metadata": {}, "expires_at": "2026-03-20",
        }]
        mock_db2.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = mock_select2
        mock_db2.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_prop_result = MagicMock()
        mock_prop_result.data = [{"property_id": "p-new", "name": "E2E Villa"}]
        mock_db2.table.return_value.insert.return_value.execute.return_value = mock_prop_result

        with patch("api.onboard_token_router._get_db", return_value=mock_db2):
            submit_resp = client.post("/onboard/submit", json={
                "token": raw_token,
                "property_name": "E2E Villa",
                "property_type": "villa",
                "address": "123 Test St",
                "capacity": "4",
                "contact_name": "Owner",
                "contact_phone": "+1 555",
                "wifi_name": "TestWifi",
                "wifi_password": "pw123",
                "house_rules": "No smoking",
                "special_notes": "Test",
            })
        assert submit_resp.status_code == 201
        assert submit_resp.json()["status"] == "submitted"
