"""
Phase 402 — Onboard Token Flow — Contract Tests
===================================================

Tests for:
    1. GET /onboard/validate/{token} returns 200 for valid token
    2. GET /onboard/validate/{token} returns 401 for invalid/expired
    3. POST /onboard/submit creates property (mocked DB)
    4. POST /onboard/submit rejects invalid token
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("IHOUSE_JWT_SECRET", "test-secret-phase402")
    monkeypatch.setenv("IHOUSE_ACCESS_TOKEN_SECRET", "access-token-secret-32-bytes-ok")
    monkeypatch.setenv("IHOUSE_DEV_MODE", "true")
    monkeypatch.setenv("IHOUSE_DEV_PASSWORD", "dev")
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-key")


@pytest.fixture()
def client():
    from main import app
    from fastapi.testclient import TestClient
    return TestClient(app, raise_server_exceptions=False)


def _issue_onboard_token():
    from services.access_token_service import issue_access_token, TokenType
    return issue_access_token(TokenType.ONBOARD, "tenant-abc", "owner@test.com", 3600)


class TestOnboardTokenFlow:

    def test_validate_valid_onboard_token(self, client):
        """Valid onboard token returns 200."""
        raw_token, _ = _issue_onboard_token()

        mock_db = MagicMock()
        mock_select_result = MagicMock()
        mock_select_result.data = [{"id": "tok-1", "used_at": None, "revoked_at": None}]
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = mock_select_result

        with patch("api.onboard_token_router._get_db", return_value=mock_db):
            resp = client.get(f"/onboard/validate/{raw_token}")
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    def test_validate_invalid_token_returns_401(self, client):
        """Invalid token returns 401."""
        resp = client.get("/onboard/validate/not-valid-token")
        assert resp.status_code == 401

    def test_validate_expired_token_returns_401(self, client):
        """Expired token returns 401."""
        from services.access_token_service import issue_access_token, TokenType
        raw_token, _ = issue_access_token(TokenType.ONBOARD, "t", ttl_seconds=-10)
        resp = client.get(f"/onboard/validate/{raw_token}")
        assert resp.status_code == 401

    def test_submit_creates_property(self, client):
        """POST /onboard/submit consumes token and creates property."""
        raw_token, _ = _issue_onboard_token()

        mock_db = MagicMock()
        # validate_and_consume: select returns active token
        mock_select_result = MagicMock()
        mock_select_result.data = [{
            "id": "tok-1",
            "token_type": "onboard",
            "entity_id": "tenant-abc",
            "email": "owner@test.com",
            "used_at": None,
            "revoked_at": None,
            "metadata": {},
            "expires_at": "2026-03-20T00:00:00Z",
        }]
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = mock_select_result
        # update (mark used) succeeds
        mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        # property insert
        mock_prop_result = MagicMock()
        mock_prop_result.data = [{"property_id": "p-001", "name": "Villa Sunset"}]
        mock_db.table.return_value.insert.return_value.execute.return_value = mock_prop_result

        with patch("api.onboard_token_router._get_db", return_value=mock_db):
            resp = client.post("/onboard/submit", json={
                "token": raw_token,
                "property_name": "Villa Sunset",
                "property_type": "villa",
                "address": "123 Beach Rd",
                "capacity": "6",
                "contact_name": "Nati",
                "contact_phone": "+66 80 111",
                "contact_email": "owner@test.com",
                "wifi_name": "VillaSunset_5G",
                "wifi_password": "sunset2026",
                "house_rules": "No smoking\nQuiet after 10pm",
                "special_notes": "Pool gate code: 1234",
            })
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "submitted"
        assert body["property_name"] == "Villa Sunset"

    def test_submit_invalid_token_returns_401(self, client):
        """Invalid token rejected on submit."""
        mock_db = MagicMock()
        with patch("api.onboard_token_router._get_db", return_value=mock_db):
            resp = client.post("/onboard/submit", json={
                "token": "invalid-token",
                "property_name": "Test",
            })
        assert resp.status_code == 401

    def test_wrong_token_type_rejected(self, client):
        """Invite token rejected for onboard validate."""
        from services.access_token_service import issue_access_token, TokenType
        invite_token, _ = issue_access_token(TokenType.INVITE, "t", "x@test.com", 3600)
        resp = client.get(f"/onboard/validate/{invite_token}")
        assert resp.status_code == 401
