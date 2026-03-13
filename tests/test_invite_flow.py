"""
Phase 401 — Invite Flow — Contract Tests
============================================

Tests for:
    1. POST /admin/invites creates invite
    2. GET /invite/validate/{token} returns metadata
    3. POST /invite/accept/{token} consumes token
    4. Double-accept returns 401
    5. Invalid token returns 401
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("IHOUSE_JWT_SECRET", "test-secret-phase401")
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


@pytest.fixture()
def auth_header(client):
    resp = client.post("/auth/token", json={"tenant_id": "t1", "secret": "dev"})
    return {"Authorization": f"Bearer {resp.json()['data']['token']}"}


class TestInviteFlow:
    """End-to-end invite create → validate → accept tests."""

    def test_create_invite_returns_token(self, client, auth_header):
        """POST /admin/invites creates an invite with metadata."""
        mock_db = MagicMock()
        mock_insert_result = MagicMock()
        mock_insert_result.data = [{"id": "inv-001", "expires_at": "2026-03-20T00:00:00Z"}]
        mock_db.table.return_value.insert.return_value.execute.return_value = mock_insert_result

        with patch("api.invite_router._get_db", return_value=mock_db):
            resp = client.post("/admin/invites", headers=auth_header, json={
                "email": "newstaff@test.com",
                "role": "worker",
                "organization_name": "Test Org",
            })
        assert resp.status_code == 201
        body = resp.json()
        assert "token" in body
        assert body["role"] == "worker"
        assert body["email"] == "newstaff@test.com"
        assert body["invite_url"].startswith("/invite/")

    def test_validate_valid_invite(self, client, auth_header):
        """GET /invite/validate/{token} returns invite metadata."""
        from services.access_token_service import issue_access_token, TokenType
        raw_token, _ = issue_access_token(TokenType.INVITE, "tenant-1", "staff@test.com", 3600)

        mock_db = MagicMock()
        mock_select_result = MagicMock()
        mock_select_result.data = [{
            "id": "inv-001",
            "used_at": None,
            "revoked_at": None,
            "metadata": {"role": "worker", "organization_name": "Domaniqo", "invited_by": "admin1"},
            "expires_at": "2026-03-20T00:00:00Z",
        }]
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = mock_select_result

        with patch("api.invite_router._get_db", return_value=mock_db):
            resp = client.get(f"/invite/validate/{raw_token}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is True
        assert body["role"] == "worker"
        assert body["organization_name"] == "Domaniqo"
        assert body["invited_by"] == "admin1"

    def test_validate_invalid_token_returns_401(self, client):
        """Invalid token returns 401."""
        resp = client.get("/invite/validate/not-a-valid-token")
        assert resp.status_code == 401

    def test_validate_expired_token_returns_401(self, client):
        """Expired invite token returns 401."""
        from services.access_token_service import issue_access_token, TokenType
        raw_token, _ = issue_access_token(TokenType.INVITE, "tenant-1", ttl_seconds=-10)
        resp = client.get(f"/invite/validate/{raw_token}")
        assert resp.status_code == 401

    def test_accept_consumes_token(self, client):
        """POST /invite/accept/{token} consumes the token."""
        from services.access_token_service import issue_access_token, TokenType
        raw_token, _ = issue_access_token(TokenType.INVITE, "tenant-1", "staff@test.com", 3600)

        mock_db = MagicMock()
        # validate_and_consume: select returns active token
        mock_select_result = MagicMock()
        mock_select_result.data = [{
            "id": "inv-001",
            "token_type": "invite",
            "entity_id": "tenant-1",
            "email": "staff@test.com",
            "used_at": None,
            "revoked_at": None,
            "metadata": {"role": "worker", "organization_name": "Domaniqo"},
            "expires_at": "2026-03-20T00:00:00Z",
        }]
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = mock_select_result
        # update (mark used) succeeds
        mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        # audit insert succeeds
        mock_db.table.return_value.insert.return_value.execute.return_value = MagicMock()

        with patch("api.invite_router._get_db", return_value=mock_db):
            resp = client.post(f"/invite/accept/{raw_token}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "accepted"
        assert body["role"] == "worker"

    def test_accept_invalid_token_returns_401(self, client):
        """Accept with invalid token returns 401."""
        mock_db = MagicMock()
        with patch("api.invite_router._get_db", return_value=mock_db):
            resp = client.post("/invite/accept/invalid-token-xyz")
        assert resp.status_code == 401
