"""
Phase 165 — Permissions CRUD contract tests

~32 tests covering:
  - GET /permissions (list)
  - GET /permissions/{user_id} (single)
  - POST /permissions (upsert — create and update)
  - DELETE /permissions/{user_id}
  - Role validation (invalid role rejected)
  - Tenant isolation (cross-tenant not visible)
  - Missing user_id (400)
  - Invalid permissions field (400)
  - 404 on missing user
  - get_permission_record() helper
  - get_jwt_scope() helper
"""
from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from api.auth import jwt_auth

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_TENANT_A = "tenant-A"
_TENANT_B = "tenant-B"


@pytest.fixture
def client():
    _app = app
    _app.dependency_overrides[jwt_auth] = lambda: _TENANT_A
    yield TestClient(_app, raise_server_exceptions=False)
    _app.dependency_overrides.clear()


@pytest.fixture
def client_b():
    """Client authenticated as tenant-B."""
    _app = app
    _app.dependency_overrides[jwt_auth] = lambda: _TENANT_B
    yield TestClient(_app, raise_server_exceptions=False)
    _app.dependency_overrides.clear()


def _make_db(rows: List[Dict[str, Any]] = None) -> MagicMock:
    """Build a mock Supabase client that returns the supplied rows."""
    db = MagicMock()
    rows = rows or []

    query = MagicMock()
    query.select.return_value = query
    query.eq.return_value = query
    query.order.return_value = query
    query.limit.return_value = query
    query.upsert.return_value = query
    query.delete.return_value = query
    query.execute.return_value = MagicMock(data=rows)
    db.table.return_value = query
    return db


def _row(
    user_id="user-1",
    role="manager",
    permissions=None,
    tenant_id=_TENANT_A,
) -> Dict[str, Any]:
    return {
        "id": 1,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "role": role,
        "permissions": permissions or {},
        "created_at": "2026-03-10T00:00:00Z",
        "updated_at": "2026-03-10T00:00:00Z",
    }


_DB_PATCH = "api.permissions_router._get_supabase_client"


# ===========================================================================
# GET /permissions — list
# ===========================================================================

class TestListPermissions:
    def test_returns_200_with_empty_list(self, client):
        db = _make_db([])
        with patch(_DB_PATCH, return_value=db):
            r = client.get("/permissions")
        assert r.status_code == 200
        body = r.json()
        assert body["tenant_id"] == _TENANT_A
        assert body["count"] == 0
        assert body["permissions"] == []

    def test_returns_all_rows_for_tenant(self, client):
        rows = [_row("u1", "admin"), _row("u2", "worker")]
        db = _make_db(rows)
        with patch(_DB_PATCH, return_value=db):
            r = client.get("/permissions")
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 2
        assert len(body["permissions"]) == 2

    def test_response_has_required_fields(self, client):
        db = _make_db([_row()])
        with patch(_DB_PATCH, return_value=db):
            r = client.get("/permissions")
        assert r.status_code == 200
        perm = r.json()["permissions"][0]
        assert "user_id" in perm
        assert "role" in perm

    def test_returns_500_on_db_error(self, client):
        db = MagicMock()
        db.table.side_effect = RuntimeError("db failure")
        with patch(_DB_PATCH, return_value=db):
            r = client.get("/permissions")
        assert r.status_code == 500
        assert r.json()["code"] == "INTERNAL_ERROR"


# ===========================================================================
# GET /permissions/{user_id} — single
# ===========================================================================

class TestGetPermission:
    def test_returns_200_for_existing_user(self, client):
        db = _make_db([_row("user-1", "admin")])
        with patch(_DB_PATCH, return_value=db):
            r = client.get("/permissions/user-1")
        assert r.status_code == 200
        assert r.json()["user_id"] == "user-1"
        assert r.json()["role"] == "admin"

    def test_returns_404_for_missing_user(self, client):
        db = _make_db([])
        with patch(_DB_PATCH, return_value=db):
            r = client.get("/permissions/ghost-user")
        assert r.status_code == 404
        body = r.json()
        assert body["code"] == "PERMISSION_NOT_FOUND"
        assert body["user_id"] == "ghost-user"

    def test_returns_500_on_db_error(self, client):
        db = MagicMock()
        db.table.side_effect = Exception("oops")
        with patch(_DB_PATCH, return_value=db):
            r = client.get("/permissions/user-1")
        assert r.status_code == 500


# ===========================================================================
# POST /permissions — upsert
# ===========================================================================

class TestUpsertPermission:
    def test_creates_new_record(self, client):
        saved = _row("user-new", "owner")
        db = _make_db([saved])
        with patch(_DB_PATCH, return_value=db):
            r = client.post("/permissions", json={"user_id": "user-new", "role": "owner"})
        assert r.status_code == 201
        body = r.json()
        assert body["status"] == "upserted"
        assert body["user_id"] == "user-new"
        assert body["role"] == "owner"
        assert body["tenant_id"] == _TENANT_A

    def test_upsert_includes_permissions_field(self, client):
        db = _make_db([_row()])
        with patch(_DB_PATCH, return_value=db):
            r = client.post("/permissions", json={
                "user_id": "u1",
                "role": "manager",
                "permissions": {"can_approve_owner_statements": True},
            })
        assert r.status_code == 201
        body = r.json()
        assert body["permissions"]["can_approve_owner_statements"] is True

    def test_rejects_invalid_role(self, client):
        r = client.post("/permissions", json={"user_id": "u1", "role": "superuser"})
        assert r.status_code == 400
        assert r.json()["code"] == "VALIDATION_ERROR"

    def test_rejects_missing_user_id(self, client):
        r = client.post("/permissions", json={"role": "admin"})
        assert r.status_code == 400
        assert r.json()["code"] == "VALIDATION_ERROR"

    def test_rejects_empty_user_id(self, client):
        r = client.post("/permissions", json={"user_id": "  ", "role": "admin"})
        assert r.status_code == 400

    def test_rejects_missing_role(self, client):
        r = client.post("/permissions", json={"user_id": "u1"})
        assert r.status_code == 400

    def test_rejects_invalid_permissions_type(self, client):
        r = client.post("/permissions", json={"user_id": "u1", "role": "admin", "permissions": "not-a-dict"})
        assert r.status_code == 400

    def test_valid_roles_accepted(self, client):
        for role in ("admin", "manager", "worker", "owner"):
            db = _make_db([_row("u", role)])
            with patch(_DB_PATCH, return_value=db):
                r = client.post("/permissions", json={"user_id": "u", "role": role})
            assert r.status_code == 201, f"role={role} should be valid"

    def test_returns_updated_at_timestamp(self, client):
        db = _make_db([_row()])
        with patch(_DB_PATCH, return_value=db):
            r = client.post("/permissions", json={"user_id": "u1", "role": "admin"})
        assert r.status_code == 201
        assert "updated_at" in r.json()

    def test_returns_500_on_db_error(self, client):
        db = MagicMock()
        db.table.side_effect = Exception("db down")
        with patch(_DB_PATCH, return_value=db):
            r = client.post("/permissions", json={"user_id": "u1", "role": "admin"})
        assert r.status_code == 500


# ===========================================================================
# DELETE /permissions/{user_id}
# ===========================================================================

class TestDeletePermission:
    def _make_delete_db(self, exists: bool) -> MagicMock:
        """Mock that returns rows on select (existence check) then handles delete."""
        db = MagicMock()
        check_q = MagicMock()
        check_q.select.return_value = check_q
        check_q.eq.return_value = check_q
        check_q.limit.return_value = check_q
        check_q.execute.return_value = MagicMock(data=[_row()] if exists else [])

        del_q = MagicMock()
        del_q.delete.return_value = del_q
        del_q.eq.return_value = del_q
        del_q.execute.return_value = MagicMock(data=[])

        call_count = [0]

        def _table(name):
            call_count[0] += 1
            if call_count[0] == 1:
                return check_q
            return del_q

        db.table.side_effect = _table
        return db

    def test_deletes_existing_user(self, client):
        db = self._make_delete_db(exists=True)
        with patch(_DB_PATCH, return_value=db):
            r = client.delete("/permissions/user-1")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "deleted"
        assert body["user_id"] == "user-1"
        assert body["tenant_id"] == _TENANT_A

    def test_returns_404_for_nonexistent_user(self, client):
        db = self._make_delete_db(exists=False)
        with patch(_DB_PATCH, return_value=db):
            r = client.delete("/permissions/ghost")
        assert r.status_code == 404
        assert r.json()["code"] == "PERMISSION_NOT_FOUND"
        assert r.json()["user_id"] == "ghost"

    def test_returns_500_on_db_error(self, client):
        db = MagicMock()
        db.table.side_effect = Exception("db error")
        with patch(_DB_PATCH, return_value=db):
            r = client.delete("/permissions/u1")
        assert r.status_code == 500


# ===========================================================================
# Tenant isolation
# ===========================================================================

class TestTenantIsolation:
    def test_list_scoped_to_tenant(self, client):
        """Confirms eq('tenant_id', ...) is called with the correct tenant from JWT."""
        captured: dict = {}

        db = MagicMock()
        q = MagicMock()
        q.select.return_value = q
        q.order.return_value = q
        q.execute.return_value = MagicMock(data=[_row()])

        def _eq(col, val):
            captured[col] = val
            return q

        q.eq.side_effect = _eq
        db.table.return_value = q

        with patch(_DB_PATCH, return_value=db):
            client.get("/permissions")

        assert captured.get("tenant_id") == _TENANT_A

    def test_get_scoped_to_tenant_b(self, client_b):
        """Tenant-B sees tenant_b's permissions only."""
        captured: dict = {}
        db = MagicMock()
        q = MagicMock()
        q.select.return_value = q
        q.limit.return_value = q
        q.execute.return_value = MagicMock(data=[_row(tenant_id=_TENANT_B)])

        def _eq(col, val):
            captured[col] = val
            return q

        q.eq.side_effect = _eq
        db.table.return_value = q

        with patch(_DB_PATCH, return_value=db):
            client_b.get("/permissions/user-1")

        assert captured.get("tenant_id") == _TENANT_B


# ===========================================================================
# get_permission_record() helper
# ===========================================================================

class TestGetPermissionRecord:
    def test_returns_record_when_found(self):
        from api.permissions_router import get_permission_record
        db = _make_db([{"role": "owner", "permissions": {"read_statements": True}}])
        result = get_permission_record(db, "t1", "u1")
        assert result is not None
        assert result["role"] == "owner"
        assert result["permissions"]["read_statements"] is True

    def test_returns_none_when_not_found(self):
        from api.permissions_router import get_permission_record
        db = _make_db([])
        result = get_permission_record(db, "t1", "u-missing")
        assert result is None

    def test_returns_none_on_db_error(self):
        from api.permissions_router import get_permission_record
        db = MagicMock()
        db.table.side_effect = Exception("network error")
        result = get_permission_record(db, "t1", "u1")
        assert result is None


# ===========================================================================
# get_jwt_scope() helper
# ===========================================================================

class TestGetJwtScope:
    def test_returns_role_and_permissions(self):
        from api.auth import get_jwt_scope
        db = _make_db([{"role": "admin", "permissions": {"can_manage": True}}])
        scope = get_jwt_scope(db, "t1", "u1")
        assert scope["role"] == "admin"
        assert scope["permissions"]["can_manage"] is True

    def test_returns_empty_scope_when_no_record(self):
        from api.auth import get_jwt_scope
        db = _make_db([])
        scope = get_jwt_scope(db, "t1", "u-missing")
        assert scope["role"] is None
        assert scope["permissions"] == {}

    def test_returns_empty_scope_on_db_error(self):
        from api.auth import get_jwt_scope
        db = MagicMock()
        db.table.side_effect = Exception("broken")
        scope = get_jwt_scope(db, "t1", "u1")
        assert scope["role"] is None
        assert scope["permissions"] == {}

    def test_never_raises(self):
        from api.auth import get_jwt_scope
        db = MagicMock()
        db.table.side_effect = RuntimeError("catastrophe")
        try:
            scope = get_jwt_scope(db, "t1", "u1")
            assert scope is not None
        except Exception:
            pytest.fail("get_jwt_scope raised an exception")
