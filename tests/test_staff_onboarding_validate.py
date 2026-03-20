"""
Phase 857 — Staff Onboarding Validation Tests
=================================================

Tests for:
    1. validate endpoint rejects legacy Pipeline A tokens (audit C3 fix)
    2. validate endpoint shows clear rejection message (audit C9 fix)
    3. validate endpoint distinguishes revoked vs rejected vs used
"""
from __future__ import annotations

import os
import time

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("IHOUSE_JWT_SECRET", "test-secret-857")
    monkeypatch.setenv("IHOUSE_ACCESS_TOKEN_SECRET", "test-access-secret-857-32b")
    monkeypatch.setenv("IHOUSE_DEV_MODE", "true")
    monkeypatch.setenv("IHOUSE_DEV_PASSWORD", "dev")
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-key")


@pytest.fixture()
def client():
    from main import app
    from fastapi.testclient import TestClient
    return TestClient(app, raise_server_exceptions=False)


def _make_staff_token():
    """Create a valid staff_onboard JWT."""
    import jwt
    secret = os.environ.get("IHOUSE_ACCESS_TOKEN_SECRET", "test-access-secret-857-32b")
    now = int(time.time())
    claims = {
        "iss": "ihouse-core",
        "aud": "ihouse-tenant",
        "typ": "staff_onboard",
        "sub": "tenant-test",
        "ent": "tenant-test",
        "iat": now,
        "exp": now + 3600,
        "eml": "worker@test.com",
    }
    return jwt.encode(claims, secret, algorithm="HS256")


def _make_invite_token():
    """Create a Pipeline A invite JWT (should be rejected by Pipeline B validate)."""
    import jwt
    secret = os.environ.get("IHOUSE_ACCESS_TOKEN_SECRET", "test-access-secret-857-32b")
    now = int(time.time())
    claims = {
        "iss": "ihouse-core",
        "aud": "ihouse-tenant",
        "typ": "invite",  # Pipeline A type
        "sub": "tenant-test",
        "ent": "tenant-test",
        "iat": now,
        "exp": now + 3600,
    }
    return jwt.encode(claims, secret, algorithm="HS256")


class TestStaffOnboardingValidate:
    """Phase 857: staff onboarding validate endpoint fixes."""

    def test_rejects_legacy_invite_token(self, client):
        """Pipeline A invite tokens must NOT be accepted by Pipeline B validate (audit C3)."""
        token = _make_invite_token()

        mock_db = MagicMock()
        with patch("api.staff_onboarding_router._get_db", return_value=mock_db):
            resp = client.get(f"/staff-onboarding/validate/{token}")

        assert resp.status_code == 401
        body = resp.json()
        assert body["error"] == "INVALID_TYPE"

    def test_accepts_staff_onboard_token(self, client):
        """Valid staff_onboard token is accepted."""
        token = _make_staff_token()

        mock_db = MagicMock()
        mock_select_result = MagicMock()
        mock_select_result.data = [{
            "id": "tok-1",
            "metadata": {"status": "pending_submission", "intended_language": "th", "preselected_roles": ["cleaner"]},
            "used_at": None,
            "revoked_at": None,
        }]
        mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = mock_select_result

        with patch("api.staff_onboarding_router._get_db", return_value=mock_db):
            resp = client.get(f"/staff-onboarding/validate/{token}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is True
        assert body["email"] == "worker@test.com"

    def test_rejected_token_shows_clear_message(self, client):
        """Rejected tokens return 410 with APPLICATION_REJECTED (audit C9)."""
        token = _make_staff_token()

        mock_db = MagicMock()
        mock_select_result = MagicMock()
        mock_select_result.data = [{
            "id": "tok-2",
            "metadata": {"status": "rejected"},
            "used_at": None,
            "revoked_at": "2026-03-20T00:00:00Z",
        }]
        mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = mock_select_result

        with patch("api.staff_onboarding_router._get_db", return_value=mock_db):
            resp = client.get(f"/staff-onboarding/validate/{token}")

        assert resp.status_code == 410
        body = resp.json()
        assert body["error"] == "APPLICATION_REJECTED"
        assert "not approved" in body["message"].lower()

    def test_revoked_non_rejected_token_shows_token_revoked(self, client):
        """Revoked tokens without rejected status return TOKEN_REVOKED."""
        token = _make_staff_token()

        mock_db = MagicMock()
        mock_select_result = MagicMock()
        mock_select_result.data = [{
            "id": "tok-3",
            "metadata": {"status": "pending_confirm"},
            "used_at": None,
            "revoked_at": "2026-03-20T00:00:00Z",
        }]
        mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = mock_select_result

        with patch("api.staff_onboarding_router._get_db", return_value=mock_db):
            resp = client.get(f"/staff-onboarding/validate/{token}")

        assert resp.status_code == 400
        body = resp.json()
        assert body["error"] == "TOKEN_REVOKED"

    def test_used_token_shows_already_used(self, client):
        """Used tokens return ALREADY_USED (not ALREADY_USED_OR_REVOKED)."""
        token = _make_staff_token()

        mock_db = MagicMock()
        mock_select_result = MagicMock()
        mock_select_result.data = [{
            "id": "tok-4",
            "metadata": {"status": "approved"},
            "used_at": "2026-03-20T00:00:00Z",
            "revoked_at": None,
        }]
        mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = mock_select_result

        with patch("api.staff_onboarding_router._get_db", return_value=mock_db):
            resp = client.get(f"/staff-onboarding/validate/{token}")

        assert resp.status_code == 400
        body = resp.json()
        assert body["error"] == "ALREADY_USED"
