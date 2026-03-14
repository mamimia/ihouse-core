"""
Phase 766 — Auth Flow E2E Verification Tests
==============================================

Walks the complete auth flow end-to-end:
1. POST /admin/bootstrap → creates first admin
2. POST /auth/token    → dev token flow (tenant_id + secret)
3. POST /auth/login-session → session-based login
4. GET  /auth/me       → identity check
5. POST /auth/logout-session → session logout
6. POST /auth/signup   → Supabase Auth user creation
7. POST /auth/signin   → Supabase Auth login → includes tenant_id/role

All tests mock external services (Supabase Auth, DB) so they run offline.
This proves every auth endpoint is wired, returns the right envelope format,
and chains correctly.
"""
from __future__ import annotations

import os
import jwt
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("IHOUSE_JWT_SECRET", "test-secret-e2e-auth-flow-32char")
    monkeypatch.setenv("IHOUSE_DEV_MODE", "true")
    monkeypatch.setenv("IHOUSE_DEV_PASSWORD", "dev")
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-key")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
    monkeypatch.setenv("IHOUSE_BOOTSTRAP_SECRET", "e2e-bootstrap-secret")


@pytest.fixture()
def client():
    from main import app
    return TestClient(app, raise_server_exceptions=False)


class TestAuthFlowE2E:
    """Full auth flow E2E test suite — proves all endpoints chain correctly."""

    def test_dev_token_flow(self, client):
        """
        E2E: /auth/token → /auth/me

        1. Get a dev token with tenant_id
        2. Call /auth/me to verify identity
        """
        # Step 1: get token
        with patch("services.role_authority.lookup_role", return_value=None):
            resp = client.post("/auth/token", json={
                "tenant_id": "test-tenant",
                "secret": "dev",
            })
        assert resp.status_code == 200, f"Token: {resp.json()}"
        data = resp.json()["data"]
        assert "token" in data
        assert data["role"] == "manager"  # default when no DB record
        assert data["tenant_id"] == "test-tenant"

        token = data["token"]

        # Step 2: verify identity via /auth/me
        with patch("api.session_router.validate_session", return_value=None):
            me_resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_resp.status_code == 200
        me_data = me_resp.json()["data"]
        assert me_data["tenant_id"] == "dev-tenant"  # dev mode returns dev-tenant
        assert "role" in me_data

    def test_session_login_logout_flow(self, client):
        """
        E2E: /auth/login-session → /auth/me → /auth/logout-session

        Full session lifecycle.
        """
        session = {"session_id": "e2e-sid", "tenant_id": "test-tenant",
                   "created_at": "2026-03-14T00:00:00Z", "expires_at": "2026-03-15T00:00:00Z"}

        # Step 1: Login
        with patch("services.role_authority.lookup_role", return_value=None), \
             patch("api.session_router.create_session", return_value=session):
            resp = client.post("/auth/login-session", json={
                "tenant_id": "test-tenant",
                "secret": "dev",
            })
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["token_type"] == "session"
        assert data["role"] == "manager"
        assert data["session"]["session_id"] == "e2e-sid"

        token = data["token"]

        # Step 2: Check /auth/me
        with patch("api.session_router.validate_session", return_value=session):
            me_resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_resp.status_code == 200
        assert me_resp.json()["data"]["has_session"] is True

        # Step 3: Logout
        with patch("api.session_router.revoke_session", return_value=True):
            logout_resp = client.post("/auth/logout-session",
                                      headers={"Authorization": f"Bearer {token}"})
        assert logout_resp.status_code == 200
        assert logout_resp.json()["data"]["revoked"] is True

    def test_bootstrap_admin_flow(self, client):
        """
        E2E: /admin/bootstrap → admin user created

        Verifies the bootstrap endpoint creates an admin with all mappings.
        """
        mock_user = MagicMock()
        mock_user.id = "bootstrap-admin-uuid"

        mock_create_result = MagicMock()
        mock_create_result.user = mock_user

        mock_db = MagicMock()
        mock_db.auth.admin.create_user.return_value = mock_create_result
        mock_db.table.return_value.upsert.return_value.execute.return_value.data = [{}]

        with patch("api.bootstrap_router._get_supabase_admin", return_value=mock_db):
            resp = client.post("/admin/bootstrap", json={
                "email": "admin@domaniqo.com",
                "password": "SecurePass!",
                "bootstrap_secret": "e2e-bootstrap-secret",
            })

        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["user_id"] == "bootstrap-admin-uuid"
        assert data["role"] == "admin"
        assert data["status"] == "bootstrap_complete"

    def test_supabase_signup_signin_chain(self, client):
        """
        E2E: /auth/signup → /auth/signin → tenant_id + role returned

        Verifies the full Supabase Auth chain with tenant bridge.
        """
        mock_user = MagicMock()
        mock_user.id = "supabase-user-uuid"

        mock_session = MagicMock()
        mock_session.access_token = "eyJ_signup_token"
        mock_session.refresh_token = "refresh_signup"
        mock_session.expires_in = 3600

        mock_create_result = MagicMock()
        mock_create_result.user = mock_user

        mock_signin_result = MagicMock()
        mock_signin_result.session = mock_session
        mock_signin_result.user = mock_user

        mock_db = MagicMock()
        mock_db.auth.admin.create_user.return_value = mock_create_result
        mock_db.auth.sign_in_with_password.return_value = mock_signin_result

        # Step 1: Signup → auto-provisions tenant mapping
        with patch("api.auth_router._get_supabase_admin", return_value=mock_db), \
             patch("services.tenant_bridge.provision_user_tenant", return_value={
                 "tenant_id": "tenant_e2e_amended", "role": "manager",
             }):
            signup_resp = client.post("/auth/signup", json={
                "email": "new@domaniqo.com",
                "password": "Pass123!",
                "full_name": "New User",
            })
        assert signup_resp.status_code == 200
        signup_data = signup_resp.json()["data"]
        assert signup_data["tenant_id"] == "tenant_e2e_amended"
        assert signup_data["role"] == "manager"

        # Step 2: Signin → includes tenant lookup
        with patch("api.auth_router._get_supabase_admin", return_value=mock_db), \
             patch("services.tenant_bridge.lookup_user_tenant", return_value={
                 "tenant_id": "tenant_e2e_amended", "role": "manager",
             }):
            signin_resp = client.post("/auth/signin", json={
                "email": "new@domaniqo.com",
                "password": "Pass123!",
            })
        assert signin_resp.status_code == 200
        signin_data = signin_resp.json()["data"]
        assert signin_data["tenant_id"] == "tenant_e2e_amended"
        assert signin_data["role"] == "manager"
        assert signin_data["access_token"] == "eyJ_signup_token"

    def test_wrong_secret_rejected(self, client):
        """E2E: Invalid secrets are rejected across all endpoints."""
        # /auth/token
        resp = client.post("/auth/token", json={
            "tenant_id": "t1", "secret": "wrong",
        })
        assert resp.status_code == 401

        # /auth/login-session
        resp2 = client.post("/auth/login-session", json={
            "tenant_id": "t1", "secret": "wrong",
        })
        assert resp2.status_code == 401

        # /admin/bootstrap
        resp3 = client.post("/admin/bootstrap", json={
            "email": "a@b.com", "password": "x",
            "bootstrap_secret": "wrong",
        })
        assert resp3.status_code == 401

    def test_logout_clears_cookie(self, client):
        """E2E: /auth/logout clears the ihouse_token cookie."""
        resp = client.post("/auth/logout")
        assert resp.status_code == 200
        # Check Set-Cookie header clears the token
        cookie_header = resp.headers.get("set-cookie", "")
        assert "ihouse_token" in cookie_header
        assert "Max-Age=0" in cookie_header
