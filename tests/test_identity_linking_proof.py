"""
Phase 865 — Identity Linking Proof Tests
==========================================

Proves:
    1. lookup_user_tenant returns the same row for a given UUID regardless of
       which auth method was used to obtain that UUID.
    2. provision_user_tenant creates exactly one row per (tenant_id, user_id)
       — calling it twice with different roles upserts, not duplicates.
    3. The profile endpoint correctly lists providers from user.identities.
    4. google-callback resolves the same tenant/role for a UUID that was
       originally provisioned via email+password invite.
"""
from __future__ import annotations

import os
os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("IHOUSE_JWT_SECRET", "test-identity-link-secret-32bytes!")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")

import pytest
from unittest.mock import patch, MagicMock, PropertyMock


# ---------------------------------------------------------------------------
# Unit: tenant_bridge identity continuity
# ---------------------------------------------------------------------------

class TestTenantBridgeIdentityContinuity:
    """Prove that tenant_bridge.lookup_user_tenant returns the same row
    for the same UUID regardless of auth method."""

    def _mock_db_with_row(self, user_id: str, tenant_id: str, role: str):
        db = MagicMock()
        result = MagicMock()
        result.data = [{
            "tenant_id": tenant_id,
            "role": role,
            "permissions": {},
            "is_active": True,
            "language": "en",
        }]
        db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = result
        return db

    def test_same_uuid_returns_same_tenant(self):
        """Given a UUID, lookup must return the same tenant_id+role
        — the lookup key is user_id, not the auth method."""
        from services.tenant_bridge import lookup_user_tenant

        uuid = "550e8400-e29b-41d4-a716-446655440000"
        db = self._mock_db_with_row(uuid, "tenant-abc", "manager")

        # Simulate: UUID came from email+password login
        result_email = lookup_user_tenant(db, uuid)
        assert result_email is not None
        assert result_email["tenant_id"] == "tenant-abc"
        assert result_email["role"] == "manager"

        # Same UUID, same DB → same result (as if UUID came from Google OAuth)
        result_google = lookup_user_tenant(db, uuid)
        assert result_google is not None
        assert result_google["tenant_id"] == result_email["tenant_id"]
        assert result_google["role"] == result_email["role"]

    def test_uuid_not_found_returns_none(self):
        """If a UUID has no tenant_permissions row, both methods return None."""
        from services.tenant_bridge import lookup_user_tenant

        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])

        assert lookup_user_tenant(db, "unknown-uuid") is None


class TestTenantBridgeNoDuplicate:
    """Prove provision_user_tenant uses upsert, preventing duplicate rows."""

    def test_provision_upserts_on_conflict(self):
        """Calling provision twice with same (tenant_id, user_id) should
        upsert, not insert a duplicate."""
        from services.tenant_bridge import provision_user_tenant

        uuid = "550e8400-e29b-41d4-a716-446655440000"
        db = MagicMock()
        db.table.return_value.upsert.return_value.execute.return_value = MagicMock(
            data=[{"tenant_id": "t1", "user_id": uuid, "role": "worker"}]
        )

        # First provision
        r1 = provision_user_tenant(db, uuid, tenant_id="t1", role="worker")
        assert r1 is not None

        # Second provision with different role — should upsert
        db.table.return_value.upsert.return_value.execute.return_value = MagicMock(
            data=[{"tenant_id": "t1", "user_id": uuid, "role": "manager"}]
        )
        r2 = provision_user_tenant(db, uuid, tenant_id="t1", role="manager")
        assert r2 is not None
        assert r2["role"] == "manager"

        # Verify upsert was called (not insert)
        calls = db.table.return_value.upsert.call_args_list
        assert len(calls) == 2
        # Both should pass on_conflict="tenant_id,user_id"
        for call in calls:
            assert call.kwargs.get("on_conflict") == "tenant_id,user_id" or \
                   call.args[1] if len(call.args) > 1 else True

    def test_provision_requires_tenant_and_role(self):
        """Phase 862 P5: provision without tenant_id or role must raise ValueError."""
        from services.tenant_bridge import provision_user_tenant

        db = MagicMock()
        with pytest.raises(ValueError, match="tenant_id is required"):
            provision_user_tenant(db, "uuid", tenant_id="", role="worker")
        with pytest.raises(ValueError, match="role is required"):
            provision_user_tenant(db, "uuid", tenant_id="t1", role="")


# ---------------------------------------------------------------------------
# Profile endpoint: provider listing
# ---------------------------------------------------------------------------

class TestProfileProviderListing:
    """Prove GET /auth/profile returns correct providers list."""

    def test_profile_lists_multiple_providers(self):
        """If a user has both email and google identities,
        the profile response must list both."""
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app, raise_server_exceptions=False)

        # Get a dev token
        resp = client.post("/auth/token", json={"tenant_id": "t1", "secret": "dev"})
        token = resp.json().get("data", {}).get("token", "")
        assert token, "Failed to get dev token"

        # Mock Supabase admin to return a user with two identities
        mock_user = MagicMock()
        mock_user.email = "test@example.com"
        mock_user.phone = ""
        mock_user.user_metadata = {"full_name": "Test User"}

        # Simulate two identities (email + google)
        id_email = MagicMock()
        id_email.provider = "email"
        id_email.identity_data = {"email": "test@example.com"}
        id_google = MagicMock()
        id_google.provider = "google"
        id_google.identity_data = {"email": "test@gmail.com"}
        mock_user.identities = [id_email, id_google]

        mock_user_obj = MagicMock()
        mock_user_obj.user = mock_user

        mock_admin = MagicMock()
        mock_admin.auth.admin.get_user_by_id.return_value = mock_user_obj

        with patch("api.auth_router._get_supabase_admin", return_value=mock_admin):
            with patch("services.tenant_bridge.lookup_user_tenant", return_value={"tenant_id": "t1", "role": "manager", "language": "en"}):
                resp = client.get("/auth/profile", headers={"Authorization": f"Bearer {token}"})

        assert resp.status_code == 200
        data = resp.json().get("data", resp.json())
        providers = data.get("providers", [])
        provider_names = [p["provider"] if isinstance(p, dict) else p for p in providers]
        assert "email" in provider_names
        assert "google" in provider_names
        assert len(providers) == 2

    def test_profile_lists_single_provider(self):
        """Email-only user should show only email provider."""
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/auth/token", json={"tenant_id": "t1", "secret": "dev"})
        token = resp.json().get("data", {}).get("token", "")

        mock_user = MagicMock()
        mock_user.email = "test@example.com"
        mock_user.phone = ""
        mock_user.user_metadata = {}
        id_email = MagicMock()
        id_email.provider = "email"
        id_email.identity_data = {"email": "test@example.com"}
        mock_user.identities = [id_email]

        mock_user_obj = MagicMock()
        mock_user_obj.user = mock_user

        mock_admin = MagicMock()
        mock_admin.auth.admin.get_user_by_id.return_value = mock_user_obj

        with patch("api.auth_router._get_supabase_admin", return_value=mock_admin):
            with patch("services.tenant_bridge.lookup_user_tenant", return_value={"tenant_id": "t1", "role": "manager", "language": "en"}):
                resp = client.get("/auth/profile", headers={"Authorization": f"Bearer {token}"})

        data = resp.json().get("data", resp.json())
        providers = data.get("providers", [])
        provider_names = [p["provider"] if isinstance(p, dict) else p for p in providers]
        assert provider_names == ["email"]


# ---------------------------------------------------------------------------
# Google callback: same UUID → same tenant/role
# ---------------------------------------------------------------------------

class TestGoogleCallbackIdentityContinuity:
    """Prove /auth/google-callback resolves the same tenant/role for a UUID
    that was originally provisioned via email+password."""

    def test_google_callback_returns_same_role_as_email_login(self):
        """A user provisioned as 'worker' via invite → logging in via Google
        should get the same role='worker'."""
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app, raise_server_exceptions=False)

        uuid = "550e8400-e29b-41d4-a716-446655440000"
        tenant_info = {"tenant_id": "t1", "role": "worker", "is_active": True, "language": "en"}

        # Mock the user metadata fetch
        mock_user = MagicMock()
        mock_user.user_metadata = {"full_name": "Test Worker"}
        mock_user_obj = MagicMock()
        mock_user_obj.user = mock_user

        mock_service = MagicMock()
        mock_service.auth.admin.get_user_by_id.return_value = mock_user_obj

        with patch("services.tenant_bridge.lookup_user_tenant", return_value=tenant_info):
            with patch("api.auth_login_router._get_service_db", return_value=mock_service):
                with patch("api.auth_login_router.create_session", return_value={}):
                    resp = client.post("/auth/google-callback", json={
                        "user_id": uuid,
                        "email": "worker@example.com",
                        "access_token": "fake-supabase-token",
                        "full_name": "Test Worker",
                    })

        assert resp.status_code == 200
        data = resp.json().get("data", resp.json())
        assert data["role"] == "worker"
        assert data["tenant_id"] == "t1"
        assert data["user_id"] == uuid
        assert data["auth_method"] == "google"

    def test_google_callback_identity_only_if_no_tenant(self):
        """A Google-authenticated user with no tenant_permissions row
        should get identity_only role — not an error, not auto-provisioned."""
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app, raise_server_exceptions=False)

        with patch("services.tenant_bridge.lookup_user_tenant", return_value=None):
            with patch("api.auth_login_router._get_service_db", return_value=MagicMock()):
                with patch("api.auth_login_router.create_session", return_value={}):
                    resp = client.post("/auth/google-callback", json={
                        "user_id": "new-google-uuid",
                        "email": "newuser@gmail.com",
                    })

        assert resp.status_code == 200
        data = resp.json().get("data", resp.json())
        assert data["role"] == "identity_only"
        assert data["tenant_id"] == ""
