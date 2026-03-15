"""
Contract tests — Phase 297: Session Management
===============================================

Covers:
- session.py service: hash_token, create_session, validate_session,
  revoke_session, revoke_all_sessions, list_active_sessions
- session endpoints: POST /auth/login-session, GET /auth/me,
  POST /auth/logout-session, GET /auth/sessions,
  DELETE /auth/sessions (revoke-all)
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("SUPABASE_URL", "http://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")


# ---------------------------------------------------------------------------
# session.py service tests
# ---------------------------------------------------------------------------

class TestHashToken:
    def test_deterministic(self):
        from services.session import _hash_token
        assert _hash_token("abc") == _hash_token("abc")

    def test_different_tokens_different_hashes(self):
        from services.session import _hash_token
        assert _hash_token("token-a") != _hash_token("token-b")

    def test_returns_64_hex_chars(self):
        from services.session import _hash_token
        h = _hash_token("some-jwt-token")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


class TestCreateSession:
    def test_create_success(self):
        from services.session import create_session
        db = MagicMock()
        session_row = {
            "session_id": "sid-1",
            "tenant_id": "t1",
            "token_hash": "x" * 64,
            "created_at": "2026-03-12T00:00:00+00:00",
            "expires_at": "2026-03-13T00:00:00+00:00",
        }
        db.table.return_value.insert.return_value.execute.return_value.data = [session_row]
        result = create_session(db, "t1", "my-jwt")
        assert result["session_id"] == "sid-1"
        assert result["tenant_id"] == "t1"

    def test_returns_empty_on_no_data(self):
        from services.session import create_session
        db = MagicMock()
        db.table.return_value.insert.return_value.execute.return_value.data = []
        result = create_session(db, "t1", "my-jwt")
        assert result.get("session_id") is None

    def test_raises_on_db_error(self):
        from services.session import create_session
        db = MagicMock()
        db.table.return_value.insert.return_value.execute.side_effect = Exception("DB error")
        with pytest.raises(Exception, match="DB error"):
            create_session(db, "t1", "my-jwt")


class TestValidateSession:
    def _future_ts(self, seconds=3600):
        return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()

    def test_returns_session_when_active(self):
        from services.session import validate_session
        db = MagicMock()
        session_row = {
            "session_id": "sid-1",
            "tenant_id": "t1",
            "created_at": "2026-03-12T00:00:00+00:00",
            "expires_at": self._future_ts(3600),
            "revoked_at": None,
        }
        db.table.return_value.select.return_value.eq.return_value.is_.return_value.execute.return_value.data = [session_row]
        result = validate_session(db, "some-token")
        assert result is not None
        assert result["session_id"] == "sid-1"

    def test_returns_none_when_not_found(self):
        from services.session import validate_session
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.is_.return_value.execute.return_value.data = []
        result = validate_session(db, "some-token")
        assert result is None

    def test_returns_none_when_expired(self):
        from services.session import validate_session
        past_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        db = MagicMock()
        session_row = {
            "session_id": "sid-1",
            "tenant_id": "t1",
            "created_at": "2026-03-12T00:00:00+00:00",
            "expires_at": past_ts,
            "revoked_at": None,
        }
        db.table.return_value.select.return_value.eq.return_value.is_.return_value.execute.return_value.data = [session_row]
        result = validate_session(db, "some-token")
        assert result is None

    def test_returns_none_on_db_error(self):
        from services.session import validate_session
        db = MagicMock()
        db.table.side_effect = Exception("Connection lost")
        result = validate_session(db, "some-token")
        assert result is None


class TestRevokeSession:
    def test_revoke_success_true(self):
        from services.session import revoke_session
        db = MagicMock()
        db.table.return_value.update.return_value.eq.return_value.is_.return_value.execute.return_value.data = [{"revoked": True}]
        assert revoke_session(db, "some-token") is True

    def test_revoke_not_found_false(self):
        from services.session import revoke_session
        db = MagicMock()
        db.table.return_value.update.return_value.eq.return_value.is_.return_value.execute.return_value.data = []
        assert revoke_session(db, "some-token") is False

    def test_revoke_returns_false_on_error(self):
        from services.session import revoke_session
        db = MagicMock()
        db.table.side_effect = Exception("DB error")
        assert revoke_session(db, "some-token") is False


class TestRevokeAllSessions:
    def test_revoke_all_returns_count(self):
        from services.session import revoke_all_sessions
        db = MagicMock()
        db.table.return_value.update.return_value.eq.return_value.is_.return_value.execute.return_value.data = [
            {"session_id": "s1"},
            {"session_id": "s2"},
        ]
        count = revoke_all_sessions(db, "t1")
        assert count == 2

    def test_revoke_all_returns_zero_on_error(self):
        from services.session import revoke_all_sessions
        db = MagicMock()
        db.table.side_effect = Exception("error")
        count = revoke_all_sessions(db, "t1")
        assert count == 0


class TestListActiveSessions:
    def test_returns_active_sessions(self):
        from services.session import list_active_sessions
        future_ts = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.is_.return_value.order.return_value.execute.return_value.data = [
            {"session_id": "s1", "tenant_id": "t1", "expires_at": future_ts},
        ]
        result = list_active_sessions(db, "t1")
        assert len(result) == 1
        assert result[0]["session_id"] == "s1"

    def test_filters_out_expired(self):
        from services.session import list_active_sessions
        past_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.is_.return_value.order.return_value.execute.return_value.data = [
            {"session_id": "s1", "tenant_id": "t1", "expires_at": past_ts},
        ]
        result = list_active_sessions(db, "t1")
        assert len(result) == 0

    def test_returns_empty_on_error(self):
        from services.session import list_active_sessions
        db = MagicMock()
        db.table.side_effect = Exception("DB error")
        result = list_active_sessions(db, "t1")
        assert result == []


# ---------------------------------------------------------------------------
# Router-level tests
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    os.environ["IHOUSE_DEV_MODE"] = "true"
    os.environ["IHOUSE_JWT_SECRET"] = "test-secret-hs256"
    os.environ["SUPABASE_URL"] = "http://test.supabase.co"
    os.environ["SUPABASE_KEY"] = "test-key"
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.session_router import router
    _app = FastAPI()
    _app.include_router(router)
    return TestClient(_app)


class TestLoginSession:
    def test_login_success_returns_201(self, client):
        session = {"session_id": "sid-1", "tenant_id": "dev-tenant",
                   "created_at": "2026-03-12T00:00:00Z", "expires_at": "2026-03-13T00:00:00Z"}
        with patch("api.session_router._get_db"), \
             patch("api.session_router.create_session", return_value=session), \
             patch("services.role_authority.lookup_role", return_value=None):
            resp = client.post(
                "/auth/login-session",
                json={"tenant_id": "dev-tenant", "secret": "dev"},
            )
        assert resp.status_code == 201
        body = resp.json()["data"]
        assert "token" in body
        assert body["session"]["session_id"] == "sid-1"

    def test_login_empty_tenant_returns_422(self, client):
        resp = client.post("/auth/login-session", json={"tenant_id": "", "secret": "dev"})
        assert resp.status_code == 422

    def test_login_wrong_secret_returns_401(self, client):
        resp = client.post("/auth/login-session", json={"tenant_id": "t1", "secret": "wrong"})
        assert resp.status_code == 401

    def test_login_no_jwt_secret_returns_503(self, client):
        old = os.environ.pop("IHOUSE_JWT_SECRET", None)
        try:
            resp = client.post("/auth/login-session", json={"tenant_id": "t1", "secret": "dev"})
            assert resp.status_code == 503
        finally:
            if old:
                os.environ["IHOUSE_JWT_SECRET"] = old


class TestGetMe:
    def test_me_returns_session_info(self, client):
        session = {"session_id": "sid-1", "tenant_id": "dev-tenant",
                   "created_at": "2026-03-12T00:00:00Z", "expires_at": "2026-03-13T00:00:00Z"}
        with patch("api.session_router._get_db"), \
             patch("api.session_router.validate_session", return_value=session):
            resp = client.get(
                "/auth/me",
                headers={"Authorization": "Bearer dummy-token"},
            )
        assert resp.status_code == 200
        body = resp.json()["data"]
        import os; expected = os.environ.get("IHOUSE_TENANT_ID", "dev-tenant")
        assert body["tenant_id"] == expected

    def test_me_no_session_returns_info_without_session(self, client):
        """In dev-mode, /auth/me still returns tenant_id from JWT even w/o session record."""
        with patch("api.session_router._get_db"), \
             patch("api.session_router.validate_session", return_value=None):
            resp = client.get(
                "/auth/me",
                headers={"Authorization": "Bearer dummy-token"},
            )
        assert resp.status_code == 200
        assert resp.json()["data"]["has_session"] is False


class TestLogoutSession:
    def test_logout_revokes_session(self, client):
        with patch("api.session_router._get_db"), \
             patch("api.session_router.revoke_session", return_value=True):
            resp = client.post(
                "/auth/logout-session",
                headers={"Authorization": "Bearer dummy-token"},
            )
        assert resp.status_code == 200
        assert resp.json()["data"]["revoked"] is True


class TestListSessions:
    def test_list_sessions_returns_list(self, client):
        sessions = [
            {"session_id": "s1", "created_at": "2026-03-12T00:00:00Z", "expires_at": "2026-03-13T00:00:00Z"},
        ]
        with patch("api.session_router._get_db"), \
             patch("api.session_router.list_active_sessions", return_value=sessions):
            resp = client.get(
                "/auth/sessions",
                headers={"Authorization": "Bearer dummy-token"},
            )
        assert resp.status_code == 200
        assert resp.json()["data"]["count"] == 1


class TestRevokeAllSessions:
    def test_revoke_all_returns_count(self, client):
        with patch("api.session_router._get_db"), \
             patch("api.session_router.revoke_all_sessions", return_value=3):
            resp = client.delete(
                "/auth/sessions",
                headers={"Authorization": "Bearer dummy-token"},
            )
        assert resp.status_code == 200
        assert resp.json()["data"]["revoked_count"] == 3
