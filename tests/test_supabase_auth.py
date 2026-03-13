"""
Phase 467 — Supabase Auth First Real User — Tests
==================================================

Tests for POST /auth/signup, POST /auth/signin, GET /auth/me.
These mock the Supabase client to test endpoint logic without live Supabase.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    import importlib
    import main as main_mod
    importlib.reload(main_mod)
    return TestClient(main_mod.app)


# ─────────────────────────────────────────────────────────────────────────────
# POST /auth/signup
# ─────────────────────────────────────────────────────────────────────────────

def test_signup_returns_503_when_supabase_not_configured(client):
    """Signup returns 503 when SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is missing."""
    with patch.dict("os.environ", {}, clear=True):
        resp = client.post("/auth/signup", json={
            "email": "test@example.com",
            "password": "Test1234!",
            "full_name": "Test User",
        })
    assert resp.status_code == 503
    assert resp.json()["error"] == "SUPABASE_NOT_CONFIGURED"


def test_signup_success_returns_user_and_token(client):
    """Signup returns user_id, email, access_token on success."""
    mock_user = MagicMock()
    mock_user.id = "user-uuid-123"

    mock_session = MagicMock()
    mock_session.access_token = "eyJ_access_token"
    mock_session.refresh_token = "refresh_token_abc"
    mock_session.expires_in = 3600

    mock_create_result = MagicMock()
    mock_create_result.user = mock_user

    mock_signin_result = MagicMock()
    mock_signin_result.session = mock_session
    mock_signin_result.user = mock_user

    mock_db = MagicMock()
    mock_db.auth.admin.create_user.return_value = mock_create_result
    mock_db.auth.sign_in_with_password.return_value = mock_signin_result

    with patch("api.auth_router._get_supabase_admin", return_value=mock_db):
        resp = client.post("/auth/signup", json={
            "email": "admin@domaniqo.com",
            "password": "SecurePass123!",
            "full_name": "Nir Admin",
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == "user-uuid-123"
    assert data["email"] == "admin@domaniqo.com"
    assert data["access_token"] == "eyJ_access_token"
    assert data["refresh_token"] == "refresh_token_abc"
    assert data["expires_in"] == 3600


# ─────────────────────────────────────────────────────────────────────────────
# POST /auth/signin
# ─────────────────────────────────────────────────────────────────────────────

def test_signin_returns_503_when_supabase_not_configured(client):
    """Signin returns 503 when Supabase is not configured."""
    with patch.dict("os.environ", {}, clear=True):
        resp = client.post("/auth/signin", json={
            "email": "test@example.com",
            "password": "Test1234!",
        })
    assert resp.status_code == 503


def test_signin_success_returns_token(client):
    """Signin returns access_token on valid credentials."""
    mock_user = MagicMock()
    mock_user.id = "user-uuid-123"

    mock_session = MagicMock()
    mock_session.access_token = "eyJ_access"
    mock_session.refresh_token = "refresh_abc"
    mock_session.expires_in = 3600

    mock_result = MagicMock()
    mock_result.session = mock_session
    mock_result.user = mock_user

    mock_db = MagicMock()
    mock_db.auth.sign_in_with_password.return_value = mock_result

    with patch("api.auth_router._get_supabase_admin", return_value=mock_db):
        resp = client.post("/auth/signin", json={
            "email": "admin@domaniqo.com",
            "password": "SecurePass123!",
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"] == "eyJ_access"
    assert data["user_id"] == "user-uuid-123"


def test_signin_failure_returns_401(client):
    """Signin returns 401 on invalid credentials."""
    mock_db = MagicMock()
    mock_db.auth.sign_in_with_password.side_effect = Exception("Invalid login")

    with patch("api.auth_router._get_supabase_admin", return_value=mock_db):
        resp = client.post("/auth/signin", json={
            "email": "bad@example.com",
            "password": "wrong",
        })

    assert resp.status_code == 401
    assert resp.json()["error"] == "AUTH_FAILED"


# ─────────────────────────────────────────────────────────────────────────────
# GET /auth/me
# ─────────────────────────────────────────────────────────────────────────────

def test_auth_me_returns_identity_in_dev_mode(client):
    """GET /auth/me returns tenant identity when IHOUSE_DEV_MODE is true."""
    with patch.dict("os.environ", {"IHOUSE_DEV_MODE": "true"}):
        resp = client.get("/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["tenant_id"] == "dev-tenant"
