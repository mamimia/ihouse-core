"""
Contract tests — Phase 296: Organization API
=============================================

Tests cover:
- org service slug generation and validation
- Organization creation (success, duplicate slug, empty name)
- Member add/remove/list (success, duplicate, wrong role, last-admin guard)
- API routes (create org, list orgs, get org, members CRUD)

All tests use mocked Supabase clients — no real DB calls.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Service-level tests
# ---------------------------------------------------------------------------

class TestSlugify:
    def test_basic(self):
        from services.organization import _slugify
        assert _slugify("My Organization") == "my-organization"

    def test_special_chars(self):
        from services.organization import _slugify
        slug = _slugify("Acme & Partners, Ltd.")
        assert slug == "acme-partners-ltd"

    def test_truncate(self):
        from services.organization import _slugify
        long_name = "a" * 100
        assert len(_slugify(long_name)) <= 63

    def test_already_clean(self):
        from services.organization import _slugify
        assert _slugify("clean-slug") == "clean-slug"


class TestSlugValidation:
    def test_valid_slug(self):
        from services.organization import _is_valid_slug
        assert _is_valid_slug("my-org") is True
        assert _is_valid_slug("org123") is True
        assert _is_valid_slug("a1b2c3") is True

    def test_invalid_starts_with_dash(self):
        from services.organization import _is_valid_slug
        assert _is_valid_slug("-bad") is False

    def test_invalid_too_short(self):
        from services.organization import _is_valid_slug
        assert _is_valid_slug("ab") is False  # min 3 chars via pattern

    def test_invalid_uppercase(self):
        from services.organization import _is_valid_slug
        assert _is_valid_slug("MyOrg") is False


class TestCreateOrganization:
    def _make_db(self, org_id="org-test-uuid"):
        db = MagicMock()
        org_row = {
            "org_id": org_id,
            "name": "Test Org",
            "slug": "test-org",
            "description": None,
            "created_by": "tenant-001",
            "created_at": "2026-03-12T00:00:00Z",
        }
        db.table.return_value.insert.return_value.execute.return_value.data = [org_row]
        # For org_members insert
        db.table.return_value.insert.return_value.execute.return_value.data = [org_row]
        return db

    def test_create_success(self):
        from services.organization import create_organization
        db = MagicMock()
        org_row = {"org_id": "uuid-1", "name": "My Org", "slug": "my-org",
                   "description": None, "created_by": "t1", "created_at": "2026-03-12T00:00:00Z"}
        db.table.return_value.insert.return_value.execute.return_value.data = [org_row]
        result = create_organization(db, "My Org", "t1")
        assert result["slug"] == "my-org"
        assert result["org_id"] == "uuid-1"

    def test_empty_name_raises(self):
        from services.organization import create_organization
        db = MagicMock()
        with pytest.raises(ValueError, match="must not be empty"):
            create_organization(db, "", "t1")

    def test_name_too_long_raises(self):
        from services.organization import create_organization
        db = MagicMock()
        with pytest.raises(ValueError, match="≤ 100"):
            create_organization(db, "x" * 101, "t1")

    def test_invalid_slug_raises(self):
        from services.organization import create_organization
        db = MagicMock()
        with pytest.raises(ValueError, match="Invalid slug"):
            create_organization(db, "Valid Name", "t1", slug="-bad-slug-")

    def test_duplicate_slug_raises(self):
        from services.organization import create_organization
        db = MagicMock()
        db.table.return_value.insert.return_value.execute.side_effect = Exception(
            "duplicate key violates unique constraint: organizations_slug_key"
        )
        with pytest.raises(ValueError, match="already taken"):
            create_organization(db, "My Org", "t1")

    def test_custom_slug_accepted(self):
        from services.organization import create_organization
        db = MagicMock()
        org_row = {"org_id": "uuid-2", "name": "My Org", "slug": "custom-slug",
                   "description": None, "created_by": "t1", "created_at": "2026-03-12T00:00:00Z"}
        db.table.return_value.insert.return_value.execute.return_value.data = [org_row]
        result = create_organization(db, "My Org", "t1", slug="custom-slug")
        assert result["slug"] == "custom-slug"


class TestGetOrgForTenant:
    def test_returns_org_with_role(self):
        from services.organization import get_org_for_tenant
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"org_id": "org-1", "role": "org_admin"}
        ]
        # Second call for get_organization
        org_row = {"org_id": "org-1", "name": "Org", "slug": "org", "created_by": "t1",
                   "created_at": "2026-03-12T00:00:00Z"}
        db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [org_row]
        db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"org_id": "org-1", "role": "org_admin"}
        ]
        # patch get_organization separately
        with patch("services.organization.get_organization", return_value=org_row):
            result = get_org_for_tenant(db, "t1")
        assert result is not None
        assert result["caller_role"] == "org_admin"

    def test_returns_none_when_no_org(self):
        from services.organization import get_org_for_tenant
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        result = get_org_for_tenant(db, "t1")
        assert result is None


class TestAddOrgMember:
    def test_add_member_success(self):
        from services.organization import add_org_member
        db = MagicMock()
        member_row = {"id": "m-1", "org_id": "org-1", "tenant_id": "t2", "role": "member",
                      "invited_by": "t1", "joined_at": "2026-03-12T00:00:00Z"}
        db.table.return_value.insert.return_value.execute.return_value.data = [member_row]
        result = add_org_member(db, "org-1", "t2", "member", "t1")
        assert result["tenant_id"] == "t2"
        assert result["role"] == "member"

    def test_invalid_role_raises(self):
        from services.organization import add_org_member
        db = MagicMock()
        with pytest.raises(ValueError, match="Invalid role"):
            add_org_member(db, "org-1", "t2", "superuser", "t1")

    def test_duplicate_member_raises(self):
        from services.organization import add_org_member
        db = MagicMock()
        db.table.return_value.insert.return_value.execute.side_effect = Exception(
            "duplicate key: org_members_org_id_tenant_id_key"
        )
        with pytest.raises(ValueError, match="already a member"):
            add_org_member(db, "org-1", "t2", "member", "t1")


class TestRemoveOrgMember:
    def test_remove_success_returns_true(self):
        from services.organization import remove_org_member
        db = MagicMock()
        db.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
            {"id": "m-1"}
        ]
        assert remove_org_member(db, "org-1", "t2") is True

    def test_remove_not_found_returns_false(self):
        from services.organization import remove_org_member
        db = MagicMock()
        db.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value.data = []
        assert remove_org_member(db, "org-1", "t-nobody") is False


class TestIsOrgAdmin:
    def test_is_admin_true(self):
        from services.organization import is_org_admin
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
            {"role": "org_admin"}
        ]
        assert is_org_admin(db, "org-1", "t1") is True

    def test_is_admin_false_not_found(self):
        from services.organization import is_org_admin
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = []
        assert is_org_admin(db, "org-1", "t2") is False

    def test_is_admin_false_on_exception(self):
        from services.organization import is_org_admin
        db = MagicMock()
        db.table.side_effect = Exception("DB error")
        assert is_org_admin(db, "org-1", "t1") is False


# ---------------------------------------------------------------------------
# Router-level tests
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    """FastAPI test client with dev-mode JWT bypass."""
    import os
    os.environ["IHOUSE_DEV_MODE"] = "true"
    os.environ["SUPABASE_URL"] = "http://test.supabase.co"
    os.environ["SUPABASE_KEY"] = "test-key"
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.org_router import router
    _app = FastAPI()
    _app.include_router(router)
    yield TestClient(_app)


class TestOrgRouterCreate:
    def test_create_returns_201(self, client):
        org_row = {"org_id": "uuid-1", "name": "Test", "slug": "test",
                   "description": None, "created_by": "dev-tenant",
                   "created_at": "2026-03-12T00:00:00Z"}
        with patch("api.org_router._get_db") as mock_db_fn, \
             patch("api.org_router.create_organization", return_value=org_row):
            resp = client.post("/admin/org", json={"name": "Test"})
        assert resp.status_code == 201
        assert resp.json()["org"]["slug"] == "test"

    def test_create_empty_name_returns_422(self, client):
        resp = client.post("/admin/org", json={"name": ""})
        assert resp.status_code == 422

    def test_create_duplicate_slug_returns_422(self, client):
        with patch("api.org_router._get_db"), \
             patch("api.org_router.create_organization",
                   side_effect=ValueError("Slug 'test' is already taken.")):
            resp = client.post("/admin/org", json={"name": "Test"})
        assert resp.status_code == 422
        assert "already taken" in resp.json()["detail"]


class TestOrgRouterListMyOrgs:
    def test_list_empty(self, client):
        with patch("api.org_router._get_db"), \
             patch("api.org_router.list_orgs_for_tenant", return_value=[]):
            resp = client.get("/admin/org", headers={"Authorization": "Bearer dummy"})
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_list_with_org(self, client):
        orgs = [{"org_id": "o1", "name": "My Org", "caller_role": "org_admin"}]
        with patch("api.org_router._get_db"), \
             patch("api.org_router.list_orgs_for_tenant", return_value=orgs):
            resp = client.get("/admin/org", headers={"Authorization": "Bearer dummy"})
        assert resp.status_code == 200
        assert resp.json()["count"] == 1


class TestOrgRouterGetOrg:
    def test_get_returns_org(self, client):
        org = {"org_id": "o1", "name": "Org", "slug": "org", "created_by": "dev-tenant",
               "created_at": "2026-03-12T00:00:00Z"}
        members = [{"tenant_id": "dev-tenant", "role": "org_admin", "joined_at": "2026-03-12T00:00:00Z"}]
        with patch("api.org_router._get_db"), \
             patch("api.org_router.get_organization", return_value=org), \
             patch("api.org_router.list_org_members", return_value=members):
            resp = client.get("/admin/org/o1", headers={"Authorization": "Bearer dummy"})
        assert resp.status_code == 200

    def test_get_not_found_returns_404(self, client):
        with patch("api.org_router._get_db"), \
             patch("api.org_router.get_organization", return_value=None):
            resp = client.get("/admin/org/nonexistent", headers={"Authorization": "Bearer dummy"})
        assert resp.status_code == 404

    def test_get_not_member_returns_403(self, client):
        org = {"org_id": "o1", "name": "Org", "slug": "org"}
        # dev-tenant is not in members list
        with patch("api.org_router._get_db"), \
             patch("api.org_router.get_organization", return_value=org), \
             patch("api.org_router.list_org_members", return_value=[]):
            resp = client.get("/admin/org/o1", headers={"Authorization": "Bearer dummy"})
        assert resp.status_code == 403


class TestOrgRouterAddMember:
    def test_add_member_success(self, client):
        org = {"org_id": "o1", "name": "Org"}
        member = {"id": "m1", "tenant_id": "t2", "role": "member", "joined_at": "2026-03-12T00:00:00Z"}
        with patch("api.org_router._get_db"), \
             patch("api.org_router.get_organization", return_value=org), \
             patch("api.org_router.is_org_admin", return_value=True), \
             patch("api.org_router.add_org_member", return_value=member):
            resp = client.post(
                "/admin/org/o1/members",
                json={"tenant_id": "t2", "role": "member"},
                headers={"Authorization": "Bearer dummy"},
            )
        assert resp.status_code == 201

    def test_add_member_not_admin_returns_403(self, client):
        org = {"org_id": "o1", "name": "Org"}
        with patch("api.org_router._get_db"), \
             patch("api.org_router.get_organization", return_value=org), \
             patch("api.org_router.is_org_admin", return_value=False):
            resp = client.post(
                "/admin/org/o1/members",
                json={"tenant_id": "t2", "role": "member"},
                headers={"Authorization": "Bearer dummy"},
            )
        assert resp.status_code == 403


class TestOrgRouterRemoveMember:
    def test_remove_success(self, client):
        org = {"org_id": "o1", "name": "Org"}
        members = [
            {"tenant_id": "dev-tenant", "role": "org_admin"},
            {"tenant_id": "t2", "role": "member"},
        ]
        with patch("api.org_router._get_db"), \
             patch("api.org_router.get_organization", return_value=org), \
             patch("api.org_router.is_org_admin", return_value=True), \
             patch("api.org_router.list_org_members", return_value=members), \
             patch("api.org_router.remove_org_member", return_value=True):
            resp = client.delete(
                "/admin/org/o1/members/t2",
                headers={"Authorization": "Bearer dummy"},
            )
        assert resp.status_code == 200
        assert resp.json()["removed"] is True

    def test_remove_last_admin_returns_422(self, client):
        org = {"org_id": "o1"}
        # Only one admin (caller themselves)
        members = [{"tenant_id": "dev-tenant", "role": "org_admin"}]
        with patch("api.org_router._get_db"), \
             patch("api.org_router.get_organization", return_value=org), \
             patch("api.org_router.is_org_admin", return_value=True), \
             patch("api.org_router.list_org_members", return_value=members):
            resp = client.delete(
                "/admin/org/o1/members/dev-tenant",
                headers={"Authorization": "Bearer dummy"},
            )
        assert resp.status_code == 422
        assert "last org_admin" in resp.json()["detail"]

    def test_remove_not_found_returns_404(self, client):
        org = {"org_id": "o1"}
        members = [
            {"tenant_id": "dev-tenant", "role": "org_admin"},
            {"tenant_id": "other-admin", "role": "org_admin"},
        ]
        with patch("api.org_router._get_db"), \
             patch("api.org_router.get_organization", return_value=org), \
             patch("api.org_router.is_org_admin", return_value=True), \
             patch("api.org_router.list_org_members", return_value=members), \
             patch("api.org_router.remove_org_member", return_value=False):
            resp = client.delete(
                "/admin/org/o1/members/dev-tenant",
                headers={"Authorization": "Bearer dummy"},
            )
        assert resp.status_code == 404
