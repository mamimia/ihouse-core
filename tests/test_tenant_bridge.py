"""
Phase 760 / Phase 862 — Tenant Bridge Tests
=================================

Verifies that:
- provision_user_tenant requires explicit tenant_id and role (Phase 862 P5)
- lookup_user_tenant returns the correct mapping
- Both handle DB errors gracefully (never raise)
"""
from __future__ import annotations

import pytest
from services.tenant_bridge import (
    provision_user_tenant,
    lookup_user_tenant,
)


class FakeTable:
    """Minimal Supabase table mock."""

    def __init__(self, rows=None, upsert_return=None):
        self._rows = rows or []
        self._upsert_return = upsert_return or []
        self._filters = {}

    def select(self, columns):
        return self

    def eq(self, col, val):
        self._filters[col] = val
        return self

    def limit(self, n):
        return self

    def upsert(self, row, **kwargs):
        self._upsert_return = [row]
        return self

    def execute(self):
        if self._upsert_return:
            return type("R", (), {"data": self._upsert_return})()
        filtered = self._rows
        for col, val in self._filters.items():
            filtered = [r for r in filtered if r.get(col) == val]
        return type("R", (), {"data": filtered})()


class FakeDB:
    def __init__(self, rows=None):
        self._rows = rows or []

    def table(self, name):
        if name == "tenant_permissions":
            return FakeTable(self._rows)
        return FakeTable([])


# ==========================================================================
# provision_user_tenant tests
# ==========================================================================

class TestProvisionUserTenant:
    def test_creates_row_with_explicit_params(self):
        """Phase 862 P5: must supply explicit tenant_id and role."""
        db = FakeDB()
        result = provision_user_tenant(
            db, "supabase-uuid-123",
            tenant_id="my-tenant", role="worker",
        )
        assert result is not None
        assert result["user_id"] == "supabase-uuid-123"
        assert result["tenant_id"] == "my-tenant"
        assert result["role"] == "worker"

    def test_uses_explicit_tenant_and_role_with_permissions(self):
        db = FakeDB()
        result = provision_user_tenant(
            db, "uuid-456",
            tenant_id="custom-tenant",
            role="admin",
            permissions={"can_manage_workers": True},
        )
        assert result["tenant_id"] == "custom-tenant"
        assert result["role"] == "admin"
        assert result["permissions"]["can_manage_workers"] is True

    def test_raises_when_tenant_id_missing(self):
        """Phase 862 P5: missing tenant_id must raise ValueError."""
        db = FakeDB()
        with pytest.raises(ValueError, match="tenant_id is required"):
            provision_user_tenant(db, "uuid", tenant_id="", role="worker")

    def test_raises_when_role_missing(self):
        """Phase 862 P5: missing role must raise ValueError."""
        db = FakeDB()
        with pytest.raises(ValueError, match="role is required"):
            provision_user_tenant(db, "uuid", tenant_id="t1", role="")

    def test_returns_none_on_db_error(self):
        class BrokenDB:
            def table(self, name):
                raise RuntimeError("DB down")

        assert provision_user_tenant(BrokenDB(), "uuid", tenant_id="t1", role="worker") is None


# ==========================================================================
# lookup_user_tenant tests
# ==========================================================================

class TestLookupUserTenant:
    def test_returns_mapping_when_exists(self):
        db = FakeDB([{
            "user_id": "uuid-1",
            "tenant_id": "tenant_e2e",
            "role": "worker",
            "permissions": {},
        }])
        result = lookup_user_tenant(db, "uuid-1")
        assert result is not None
        assert result["tenant_id"] == "tenant_e2e"
        assert result["role"] == "worker"

    def test_returns_none_when_not_found(self):
        db = FakeDB([])
        assert lookup_user_tenant(db, "nonexistent") is None

    def test_returns_none_on_db_error(self):
        class BrokenDB:
            def table(self, name):
                raise RuntimeError("DB down")

        assert lookup_user_tenant(BrokenDB(), "uuid") is None
