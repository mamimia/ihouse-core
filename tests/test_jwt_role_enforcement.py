"""
Phase 397 — JWT Role Claim + Route Enforcement — Contract Tests
================================================================

Tests that:
    1. POST /auth/token includes 'role' in JWT and response
    2. Default role is 'manager' when not specified
    3. Invalid role returns 422
    4. POST /auth/login-session includes 'role' in JWT and response
    5. GET /auth/me returns role from JWT
"""
from __future__ import annotations

import os
import jwt
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("IHOUSE_JWT_SECRET", "test-secret-for-role-tests")
    monkeypatch.setenv("IHOUSE_DEV_MODE", "true")
    monkeypatch.setenv("IHOUSE_DEV_PASSWORD", "dev")
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-key")


@pytest.fixture()
def client():
    from main import app
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# POST /auth/token — role in JWT
# ---------------------------------------------------------------------------

class TestAuthTokenRole:
    """Tests for role claim in POST /auth/token."""

    def test_default_role_is_manager(self, client):
        """When no role specified, JWT should contain role='manager'."""
        resp = client.post("/auth/token", json={"tenant_id": "t1", "secret": "dev"})
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["role"] == "manager"
        # Decode JWT and verify role claim
        decoded = jwt.decode(body["token"], "test-secret-for-role-tests", algorithms=["HS256"])
        assert decoded["role"] == "manager"

    def test_explicit_role_in_jwt(self, client):
        """Explicit role is included in JWT payload and response."""
        resp = client.post("/auth/token", json={"tenant_id": "t1", "secret": "dev", "role": "worker"})
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["role"] == "worker"
        decoded = jwt.decode(body["token"], "test-secret-for-role-tests", algorithms=["HS256"])
        assert decoded["role"] == "worker"

    def test_owner_role(self, client):
        resp = client.post("/auth/token", json={"tenant_id": "t1", "secret": "dev", "role": "owner"})
        assert resp.status_code == 200
        assert resp.json()["data"]["role"] == "owner"

    def test_admin_role(self, client):
        resp = client.post("/auth/token", json={"tenant_id": "t1", "secret": "dev", "role": "admin"})
        assert resp.status_code == 200
        assert resp.json()["data"]["role"] == "admin"

    def test_ops_role(self, client):
        resp = client.post("/auth/token", json={"tenant_id": "t1", "secret": "dev", "role": "ops"})
        assert resp.status_code == 200
        assert resp.json()["data"]["role"] == "ops"

    def test_invalid_role_returns_422(self, client):
        """Invalid role should return 422 with INVALID_ROLE error."""
        resp = client.post("/auth/token", json={"tenant_id": "t1", "secret": "dev", "role": "superadmin"})
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"]["code"] == "INVALID_ROLE"

    def test_empty_role_defaults_to_manager(self, client):
        """Empty string role normalizes to default manager."""
        resp = client.post("/auth/token", json={"tenant_id": "t1", "secret": "dev", "role": ""})
        assert resp.status_code == 200
        assert resp.json()["data"]["role"] == "manager"

    def test_role_case_insensitive(self, client):
        """Role should be normalized to lowercase."""
        resp = client.post("/auth/token", json={"tenant_id": "t1", "secret": "dev", "role": "Worker"})
        assert resp.status_code == 200
        assert resp.json()["data"]["role"] == "worker"

    def test_all_valid_roles_accepted(self, client):
        """All 8 valid roles should be accepted."""
        valid_roles = ["admin", "manager", "ops", "worker", "owner", "checkin", "checkout", "maintenance"]
        for role in valid_roles:
            resp = client.post("/auth/token", json={"tenant_id": "t1", "secret": "dev", "role": role})
            assert resp.status_code == 200, f"Role '{role}' should be accepted"
            assert resp.json()["data"]["role"] == role


# ---------------------------------------------------------------------------
# POST /auth/login-session — role in JWT
# ---------------------------------------------------------------------------

class TestLoginSessionRole:
    """Tests for role claim in POST /auth/login-session."""

    def test_default_role_in_session_login(self, client):
        """Session login without role should default to 'manager'."""
        with patch("api.session_router.create_session", return_value={"session_id": "s1"}):
            resp = client.post("/auth/login-session", json={"tenant_id": "t1", "secret": "dev"})
        assert resp.status_code == 201
        body = resp.json()["data"]
        assert body["role"] == "manager"
        decoded = jwt.decode(body["token"], "test-secret-for-role-tests", algorithms=["HS256"])
        assert decoded["role"] == "manager"

    def test_explicit_role_in_session_login(self, client):
        """Session login with explicit role includes it in JWT."""
        with patch("api.session_router.create_session", return_value={"session_id": "s1"}):
            resp = client.post("/auth/login-session", json={"tenant_id": "t1", "secret": "dev", "role": "owner"})
        assert resp.status_code == 201
        body = resp.json()["data"]
        assert body["role"] == "owner"
        decoded = jwt.decode(body["token"], "test-secret-for-role-tests", algorithms=["HS256"])
        assert decoded["role"] == "owner"

    def test_invalid_role_in_session_login(self, client):
        """Session login with invalid role should return 422."""
        resp = client.post("/auth/login-session", json={"tenant_id": "t1", "secret": "dev", "role": "hacker"})
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "INVALID_ROLE"


# ---------------------------------------------------------------------------
# GET /auth/me — role from JWT
# ---------------------------------------------------------------------------

class TestAuthMeRole:
    """Tests for role in GET /auth/me response."""

    def test_me_returns_role(self, client):
        """GET /auth/me should return the role from the JWT."""
        # First get a token with explicit role
        resp = client.post("/auth/token", json={"tenant_id": "t1", "secret": "dev", "role": "worker"})
        token = resp.json()["data"]["token"]

        # Use token to call /auth/me
        with patch("api.session_router.validate_session", return_value=None):
            me_resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_resp.status_code == 200
        body = me_resp.json()["data"]
        assert body["role"] == "worker"
        # In dev mode, jwt_auth returns 'dev-tenant' rather than real JWT sub
        assert body["tenant_id"] == "dev-tenant"

    def test_me_returns_manager_default(self, client):
        """GET /auth/me with default role returns 'manager'."""
        resp = client.post("/auth/token", json={"tenant_id": "t1", "secret": "dev"})
        token = resp.json()["data"]["token"]

        with patch("api.session_router.validate_session", return_value=None):
            me_resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_resp.status_code == 200
        assert me_resp.json()["data"]["role"] == "manager"
