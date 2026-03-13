"""
Phase 399 — Access Token System — Contract Tests
===================================================

Tests for:
    1. Token generation + cryptographic verification
    2. Token expiry enforcement
    3. Token type discrimination
    4. API endpoints: issue, list, revoke, validate
"""
from __future__ import annotations

import time
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("IHOUSE_JWT_SECRET", "test-secret-for-tokens-399")
    monkeypatch.setenv("IHOUSE_ACCESS_TOKEN_SECRET", "access-token-secret-32-bytes-ok")
    monkeypatch.setenv("IHOUSE_DEV_MODE", "true")
    monkeypatch.setenv("IHOUSE_DEV_PASSWORD", "dev")
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-key")


# ---------------------------------------------------------------------------
# Unit tests for the service
# ---------------------------------------------------------------------------

class TestAccessTokenService:
    """Pure crypto tests — no DB needed."""

    def test_issue_and_verify_invite(self):
        from services.access_token_service import issue_access_token, verify_access_token, TokenType
        raw_token, exp = issue_access_token(TokenType.INVITE, "tenant-abc", "staff@test.com", 3600)
        assert raw_token
        assert exp > int(time.time())

        claims = verify_access_token(raw_token, expected_type=TokenType.INVITE)
        assert claims is not None
        assert claims["token_type"] == "invite"
        assert claims["entity_id"] == "tenant-abc"
        assert claims["email"] == "staff@test.com"

    def test_issue_and_verify_onboard(self):
        from services.access_token_service import issue_access_token, verify_access_token, TokenType
        raw_token, exp = issue_access_token(TokenType.ONBOARD, "prop-xyz", "owner@test.com")
        claims = verify_access_token(raw_token, expected_type=TokenType.ONBOARD)
        assert claims is not None
        assert claims["token_type"] == "onboard"
        assert claims["entity_id"] == "prop-xyz"

    def test_wrong_type_rejected(self):
        from services.access_token_service import issue_access_token, verify_access_token, TokenType
        raw_token, _ = issue_access_token(TokenType.INVITE, "tenant-abc")
        # Try to verify as onboard — should fail
        claims = verify_access_token(raw_token, expected_type=TokenType.ONBOARD)
        assert claims is None

    def test_expired_token_rejected(self):
        from services.access_token_service import issue_access_token, verify_access_token, TokenType
        raw_token, _ = issue_access_token(TokenType.INVITE, "tenant-abc", ttl_seconds=-10)
        claims = verify_access_token(raw_token)
        assert claims is None

    def test_tampered_token_rejected(self):
        from services.access_token_service import issue_access_token, verify_access_token, TokenType
        raw_token, _ = issue_access_token(TokenType.INVITE, "tenant-abc")
        # Tamper with the token
        tampered = raw_token[:-3] + "XXX"
        claims = verify_access_token(tampered)
        assert claims is None

    def test_malformed_token_rejected(self):
        from services.access_token_service import verify_access_token
        assert verify_access_token("not-a-real-token") is None
        assert verify_access_token("") is None
        assert verify_access_token("abc") is None

    def test_no_type_filter_accepts_any(self):
        from services.access_token_service import issue_access_token, verify_access_token, TokenType
        raw_token, _ = issue_access_token(TokenType.INVITE, "tenant-abc")
        # Without expected_type — should still work
        claims = verify_access_token(raw_token, expected_type=None)
        assert claims is not None
        assert claims["token_type"] == "invite"

    def test_hash_is_deterministic(self):
        from services.access_token_service import _hash_token
        h1 = _hash_token("test-token-123")
        h2 = _hash_token("test-token-123")
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex digest


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    from main import app
    from fastapi.testclient import TestClient
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def auth_header(client):
    resp = client.post("/auth/token", json={"tenant_id": "t1", "secret": "dev"})
    return {"Authorization": f"Bearer {resp.json()['data']['token']}"}


class TestAccessTokenRouter:
    """API endpoint tests with mocked DB."""

    def test_issue_invite_token(self, client, auth_header):
        """POST /admin/access-tokens should return a token."""
        mock_db = MagicMock()
        mock_insert_result = MagicMock()
        mock_insert_result.data = [{"id": "tok-001", "expires_at": "2026-03-20T00:00:00Z"}]
        mock_db.table.return_value.insert.return_value.execute.return_value = mock_insert_result

        with patch("api.access_token_router._get_db", return_value=mock_db):
            resp = client.post("/admin/access-tokens", headers=auth_header, json={
                "token_type": "invite",
                "entity_id": "tenant-abc",
                "email": "newstaff@test.com",
                "ttl_days": 7,
            })
        assert resp.status_code == 201
        body = resp.json()
        assert body["token_type"] == "invite"
        assert body["entity_id"] == "tenant-abc"
        assert "token" in body

    def test_issue_invalid_type_returns_400(self, client, auth_header):
        """Invalid token_type should be rejected."""
        resp = client.post("/admin/access-tokens", headers=auth_header, json={
            "token_type": "bogus",
            "entity_id": "x",
        })
        assert resp.status_code == 400

    def test_validate_endpoint_reachable(self, client):
        """POST /access-tokens/validate should be reachable without JWT."""
        from services.access_token_service import issue_access_token, TokenType
        raw_token, _ = issue_access_token(TokenType.INVITE, "tenant-abc", "x@test.com", 3600)

        # Mock DB for validation
        mock_db = MagicMock()
        mock_select_result = MagicMock()
        mock_select_result.data = [{"id": "tok-1", "used_at": None, "revoked_at": None, "entity_id": "tenant-abc", "email": "x@test.com", "metadata": {}}]
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = mock_select_result

        with patch("api.access_token_router._get_db", return_value=mock_db):
            resp = client.post("/access-tokens/validate", json={
                "token": raw_token,
                "expected_type": "invite",
            })
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    def test_validate_expired_token_returns_401(self, client):
        """Expired token should return 401."""
        from services.access_token_service import issue_access_token, TokenType
        raw_token, _ = issue_access_token(TokenType.INVITE, "t", ttl_seconds=-10)

        resp = client.post("/access-tokens/validate", json={
            "token": raw_token,
            "expected_type": "invite",
        })
        assert resp.status_code == 401
        assert resp.json()["valid"] is False
