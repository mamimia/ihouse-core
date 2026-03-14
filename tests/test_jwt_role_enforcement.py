"""
Phase 397 → Phase 759 — JWT Role Claim + Route Enforcement — Contract Tests
=============================================================================

Updated for Phase 759: Role Authority Closure.
Role in JWT is now determined by tenant_permissions DB table, not by request body.

Tests that:
    1. POST /auth/token default role is 'manager' (no DB record → fallback)
    2. POST /auth/token role comes from DB when record exists
    3. Self-declared role is IGNORED when DB record exists
    4. Invalid roles (not in DB, not valid) still return 422
    5. POST /auth/login-session follows same DB-authority model
    6. GET /auth/me returns role from JWT
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
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")


@pytest.fixture()
def client():
    from main import app
    return TestClient(app, raise_server_exceptions=False)


def _mock_resolve_role(return_role):
    """Helper: patch resolve_role to return a specific role."""
    return patch("services.role_authority.lookup_role", return_value=return_role)


# ---------------------------------------------------------------------------
# POST /auth/token — role in JWT
# ---------------------------------------------------------------------------

class TestAuthTokenRole:
    """Tests for role claim in POST /auth/token."""

    def test_default_role_is_manager(self, client):
        """When no DB record exists, JWT should contain role='manager' (default)."""
        with _mock_resolve_role(None):
            resp = client.post("/auth/token", json={"tenant_id": "t1", "secret": "dev"})
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["role"] == "manager"
        decoded = jwt.decode(body["token"], "test-secret-for-role-tests", algorithms=["HS256"])
        assert decoded["role"] == "manager"

    def test_db_role_in_jwt(self, client):
        """When DB has role='worker', JWT must contain role='worker' regardless of request."""
        with _mock_resolve_role("worker"):
            resp = client.post("/auth/token", json={"tenant_id": "t1", "secret": "dev", "role": "admin"})
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["role"] == "worker"  # DB wins, not the request
        decoded = jwt.decode(body["token"], "test-secret-for-role-tests", algorithms=["HS256"])
        assert decoded["role"] == "worker"

    def test_self_declared_role_ignored(self, client):
        """Even if request says 'admin', DB role 'owner' wins."""
        with _mock_resolve_role("owner"):
            resp = client.post("/auth/token", json={"tenant_id": "t1", "secret": "dev", "role": "admin"})
        assert resp.status_code == 200
        assert resp.json()["data"]["role"] == "owner"

    def test_admin_role_from_db(self, client):
        """Admin role from DB is correctly reflected in JWT."""
        with _mock_resolve_role("admin"):
            resp = client.post("/auth/token", json={"tenant_id": "t1", "secret": "dev"})
        assert resp.status_code == 200
        assert resp.json()["data"]["role"] == "admin"

    def test_ops_role_from_db(self, client):
        with _mock_resolve_role("ops"):
            resp = client.post("/auth/token", json={"tenant_id": "t1", "secret": "dev"})
        assert resp.status_code == 200
        assert resp.json()["data"]["role"] == "ops"

    def test_all_valid_roles_from_db(self, client):
        """All 8 valid roles should work when they come from DB."""
        valid_roles = ["admin", "manager", "ops", "worker", "owner", "checkin", "checkout", "maintenance"]
        for role in valid_roles:
            with _mock_resolve_role(role):
                resp = client.post("/auth/token", json={"tenant_id": "t1", "secret": "dev"})
            assert resp.status_code == 200, f"Role '{role}' should be accepted from DB"
            assert resp.json()["data"]["role"] == role

    def test_empty_role_defaults_to_manager(self, client):
        """Empty string role with no DB record normalizes to default manager."""
        with _mock_resolve_role(None):
            resp = client.post("/auth/token", json={"tenant_id": "t1", "secret": "dev", "role": ""})
        assert resp.status_code == 200
        assert resp.json()["data"]["role"] == "manager"


# ---------------------------------------------------------------------------
# POST /auth/login-session — role in JWT
# ---------------------------------------------------------------------------

class TestLoginSessionRole:
    """Tests for role claim in POST /auth/login-session."""

    def test_default_role_in_session_login(self, client):
        """Session login without DB record should default to 'manager'."""
        with _mock_resolve_role(None):
            with patch("api.session_router.create_session", return_value={"session_id": "s1"}):
                resp = client.post("/auth/login-session", json={"tenant_id": "t1", "secret": "dev"})
        assert resp.status_code == 201
        body = resp.json()["data"]
        assert body["role"] == "manager"
        decoded = jwt.decode(body["token"], "test-secret-for-role-tests", algorithms=["HS256"])
        assert decoded["role"] == "manager"

    def test_db_role_in_session_login(self, client):
        """Session login with DB role='owner' reflects in JWT."""
        with _mock_resolve_role("owner"):
            with patch("api.session_router.create_session", return_value={"session_id": "s1"}):
                resp = client.post("/auth/login-session", json={"tenant_id": "t1", "secret": "dev", "role": "admin"})
        assert resp.status_code == 201
        body = resp.json()["data"]
        assert body["role"] == "owner"  # DB wins, not request
        decoded = jwt.decode(body["token"], "test-secret-for-role-tests", algorithms=["HS256"])
        assert decoded["role"] == "owner"

    def test_invalid_role_from_db_rejected(self, client):
        """If DB somehow has an invalid role value, it should be rejected."""
        with _mock_resolve_role("superadmin"):
            resp = client.post("/auth/login-session", json={"tenant_id": "t1", "secret": "dev"})
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "INVALID_ROLE"


# ---------------------------------------------------------------------------
# GET /auth/me — role from JWT
# ---------------------------------------------------------------------------

class TestAuthMeRole:
    """Tests for role in GET /auth/me response."""

    def test_me_returns_role(self, client):
        """GET /auth/me should return the role from the JWT."""
        # First get a token with DB role
        with _mock_resolve_role("worker"):
            resp = client.post("/auth/token", json={"tenant_id": "t1", "secret": "dev"})
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
        with _mock_resolve_role(None):
            resp = client.post("/auth/token", json={"tenant_id": "t1", "secret": "dev"})
        token = resp.json()["data"]["token"]

        with patch("api.session_router.validate_session", return_value=None):
            me_resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_resp.status_code == 200
        assert me_resp.json()["data"]["role"] == "manager"
