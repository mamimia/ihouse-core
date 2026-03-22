"""
Phase 867 Follow-Up — Privilege Consistency Fix Verification
==============================================================

Targeted tests proving:
1. POST /invite/accept/{token} with role='admin' in metadata → defaults to 'worker'
2. POST /auth/login with an invalid role in tenant_permissions → returns 'worker'
3. POST /auth/google-callback with an invalid role in tenant_permissions → returns 'worker'
"""
from __future__ import annotations

import os
os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("IHOUSE_JWT_SECRET", "test-phase867fix-secret-32bytes!")
os.environ.setdefault("IHOUSE_ACCESS_TOKEN_SECRET", "access-token-secret-32-bytes-ok")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")

import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture()
def client():
    from main import app
    from fastapi.testclient import TestClient
    return TestClient(app, raise_server_exceptions=False)


class TestAdminBlockedViaInvite:
    """Prove the /invite/accept endpoint rejects admin role from metadata."""

    def test_accept_with_admin_role_defaults_to_worker(self, client):
        """Invite metadata says role='admin' → accept must default to 'worker'."""
        from services.access_token_service import issue_access_token, TokenType

        raw_token, _ = issue_access_token(
            TokenType.INVITE, "tenant-1", "admin-attempt@test.com", 3600
        )

        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{
                "id": "inv-fix",
                "token_type": "invite",
                "entity_id": "tenant-1",
                "email": "admin-attempt@test.com",
                "used_at": None,
                "revoked_at": None,
                "metadata": {"role": "admin", "organization_name": "Domaniqo"},
                "expires_at": "2026-04-01T00:00:00Z",
            }]
        )
        mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_db.table.return_value.insert.return_value.execute.return_value = MagicMock()

        with patch("api.invite_router._get_db", return_value=mock_db), \
             patch.dict("os.environ", {"SUPABASE_URL": "", "SUPABASE_SERVICE_ROLE_KEY": ""}):
            resp = client.post(f"/invite/accept/{raw_token}", json={
                "password": "SecurePass8!",
                "full_name": "Admin Attempt",
            })

        assert resp.status_code == 200
        body = resp.json()
        assert body["role"] == "worker", f"Expected 'worker' but got '{body['role']}' — admin via invite must be blocked"


class TestLoginInvalidRoleFallback:
    """Prove /auth/login defaults invalid roles to 'worker', not 'manager'."""

    def test_login_with_invalid_role_returns_worker(self, client):
        """If tenant_permissions has an invalid role, login must default to 'worker'."""
        tenant_info = {
            "tenant_id": "t1",
            "role": "nonexistent_role",  # not in CANONICAL_ROLES
            "is_active": True,
            "language": "en",
        }
        mock_signin = MagicMock()
        mock_signin.user = MagicMock()
        mock_signin.user.id = "uuid-bad-role"
        mock_signin.user.email = "badrole@test.com"
        mock_signin.user.user_metadata = {}
        mock_signin.session = MagicMock(access_token="at", refresh_token="rt")

        mock_anon_db = MagicMock()
        mock_anon_db.auth.sign_in_with_password.return_value = mock_signin

        with patch("api.auth_login_router._get_anon_db", return_value=mock_anon_db), \
             patch("api.auth_login_router._get_service_db", return_value=MagicMock()), \
             patch("services.tenant_bridge.lookup_user_tenant", return_value=tenant_info), \
             patch("api.auth_login_router.create_session", return_value={}):
            resp = client.post("/auth/login", json={
                "email": "badrole@test.com",
                "password": "SomePass123!",
            })

        data = resp.json().get("data", resp.json())
        assert data["role"] == "worker", f"Expected 'worker' but got '{data['role']}' — invalid role must not escalate to manager"


class TestGoogleCallbackInvalidRoleFallback:
    """Prove /auth/google-callback defaults invalid roles to 'worker'."""

    def test_google_callback_with_invalid_role_returns_worker(self, client):
        tenant_info = {
            "tenant_id": "t1",
            "role": "nonexistent_role",
            "is_active": True,
            "language": "en",
        }
        mock_user = MagicMock()
        mock_user.user_metadata = {}
        mock_user_obj = MagicMock()
        mock_user_obj.user = mock_user

        mock_service = MagicMock()
        mock_service.auth.admin.get_user_by_id.return_value = mock_user_obj

        with patch("services.tenant_bridge.lookup_user_tenant", return_value=tenant_info), \
             patch("api.auth_login_router._get_service_db", return_value=mock_service), \
             patch("api.auth_login_router.create_session", return_value={}):
            resp = client.post("/auth/google-callback", json={
                "user_id": "uuid-bad-role-google",
                "email": "badrole@gmail.com",
            })

        data = resp.json().get("data", resp.json())
        assert data["role"] == "worker", f"Expected 'worker' but got '{data['role']}'"
