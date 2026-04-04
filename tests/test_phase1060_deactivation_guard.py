"""
Phase 1060 — jwt_auth_active: Session Invalidation on Worker Deactivation
=========================================================================

Tests the new jwt_auth_active dependency which:
  1. Validates the JWT (same as jwt_auth)
  2. Reads is_active from tenant_permissions via _get_active_db()
  3. Rejects deactivated users with 403 USER_DEACTIVATED (not bounded by TTL)
  4. Is fail-open on DB errors (transient storage outage must not lock out workers)
  5. Is a no-op in dev mode (same as jwt_auth)
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import jwt as _jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SECRET = "test-secret-for-phase-1060"
_TENANT = "test-tenant-1060"
_USER_ID = "user-uuid-1060"


def _make_token(user_id: str = _USER_ID, tenant_id: str = _TENANT, exp_offset: int = 3600) -> str:
    return _jwt.encode(
        {
            "sub": user_id,
            "tenant_id": tenant_id,
            "role": "worker",
            "iat": int(time.time()),
            "exp": int(time.time()) + exp_offset,
        },
        _SECRET,
        algorithm="HS256",
    )


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Test app — single sentinel endpoint using jwt_auth_active
# ---------------------------------------------------------------------------

def _build_app():
    from api.auth import jwt_auth_active
    app = FastAPI()

    @app.get("/worker/sentinel")
    async def sentinel(tenant_id: str = __import__("fastapi").Depends(jwt_auth_active)):
        return {"tenant_id": tenant_id}

    return app


def _mock_db_with(is_active_value):
    """Build a mock Supabase client that returns the given is_active value."""
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = (
        [{"is_active": is_active_value}] if is_active_value != "EMPTY" else []
    )
    return mock_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    monkeypatch.setenv("IHOUSE_JWT_SECRET", _SECRET)
    monkeypatch.delenv("IHOUSE_DEV_MODE", raising=False)
    monkeypatch.setenv("SUPABASE_URL", "https://fake.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "fake-service-key")


# ---------------------------------------------------------------------------
# Test: deactivated user is rejected with 403 USER_DEACTIVATED
# ---------------------------------------------------------------------------

def test_deactivated_user_rejected():
    """A worker with is_active=False must receive 403 regardless of JWT TTL."""
    mock_db = _mock_db_with(False)
    app = _build_app()
    token = _make_token()

    with patch("api.auth._get_active_db", return_value=mock_db):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/worker/sentinel", headers=_auth_headers(token))

    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
    body = resp.json()
    detail = body.get("detail", {})
    if isinstance(detail, dict):
        assert detail.get("code") == "USER_DEACTIVATED"
    else:
        assert "USER_DEACTIVATED" in str(detail)


# ---------------------------------------------------------------------------
# Test: active user passes through normally
# ---------------------------------------------------------------------------

def test_active_user_allowed():
    """A worker with is_active=True must pass through jwt_auth_active."""
    mock_db = _mock_db_with(True)
    app = _build_app()
    token = _make_token()

    with patch("api.auth._get_active_db", return_value=mock_db):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/worker/sentinel", headers=_auth_headers(token))

    assert resp.status_code == 200
    assert resp.json()["tenant_id"] == _TENANT


# ---------------------------------------------------------------------------
# Test: NULL is_active is treated as active (backward compatibility)
# ---------------------------------------------------------------------------

def test_null_is_active_treated_as_active():
    """Rows created without is_active set (NULL) must not block the user."""
    mock_db = _mock_db_with(None)
    app = _build_app()
    token = _make_token()

    with patch("api.auth._get_active_db", return_value=mock_db):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/worker/sentinel", headers=_auth_headers(token))

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Test: DB failure is fail-open (transient DB outage must not lock out workers)
# ---------------------------------------------------------------------------

def test_db_failure_fails_open():
    """If the DB check throws unexpectedly, the request must still pass (fail-open)."""
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.side_effect = Exception(
        "DB timeout"
    )

    app = _build_app()
    token = _make_token()

    with patch("api.auth._get_active_db", return_value=mock_db):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/worker/sentinel", headers=_auth_headers(token))

    assert resp.status_code == 200, f"DB failure should be fail-open, got {resp.status_code}"


# ---------------------------------------------------------------------------
# Test: expired JWT still rejected (crypto check, not bypassed by active guard)
# ---------------------------------------------------------------------------

def test_expired_token_rejected():
    """An expired JWT must still fail — jwt_auth_active calls verify_jwt first."""
    mock_db = _mock_db_with(True)
    app = _build_app()
    expired_token = _make_token(exp_offset=-10)  # expired 10s ago

    with patch("api.auth._get_active_db", return_value=mock_db):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/worker/sentinel", headers=_auth_headers(expired_token))

    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Test: missing token still rejected
# ---------------------------------------------------------------------------

def test_missing_token_rejected():
    """No Authorization header → must return 403."""
    app = _build_app()
    mock_db = _mock_db_with(True)
    with patch("api.auth._get_active_db", return_value=mock_db):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/worker/sentinel")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Test: no permission record (user not in tenant_permissions) → fail-open
# ---------------------------------------------------------------------------

def test_no_permission_record_passes():
    """A user with no tenant_permissions row returns empty records.
    Empty = no explicit is_active=False signal → pass through."""
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []

    app = _build_app()
    token = _make_token()

    with patch("api.auth._get_active_db", return_value=mock_db):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/worker/sentinel", headers=_auth_headers(token))

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Test: _get_active_db returns None → fail-open (DB not configured)
# ---------------------------------------------------------------------------

def test_none_db_fails_open():
    """If _get_active_db returns None (env vars missing), request must pass."""
    app = _build_app()
    token = _make_token()

    with patch("api.auth._get_active_db", return_value=None):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/worker/sentinel", headers=_auth_headers(token))

    assert resp.status_code == 200
