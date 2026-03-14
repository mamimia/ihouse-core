"""
Phase 759 — Role Authority Tests
=================================

Verifies that resolve_role() reads the canonical role from DB,
ignores self-declared roles, and falls back to default when
no DB record exists.
"""
from __future__ import annotations

import pytest
from services.role_authority import lookup_role, resolve_role, DEFAULT_ROLE_IF_MISSING


class FakeTable:
    """Minimal Supabase table mock for testing."""

    def __init__(self, rows):
        self._rows = rows
        self._filters = {}

    def select(self, columns):
        return self

    def eq(self, col, val):
        self._filters[col] = val
        return self

    def limit(self, n):
        return self

    def execute(self):
        filtered = self._rows
        for col, val in self._filters.items():
            filtered = [r for r in filtered if r.get(col) == val]
        return type("Result", (), {"data": filtered})()


class FakeDB:
    """Fake Supabase client with canned tenant_permissions rows."""

    def __init__(self, rows=None):
        self._rows = rows or []

    def table(self, name):
        if name == "tenant_permissions":
            return FakeTable(self._rows)
        return FakeTable([])


# ==========================================================================
# lookup_role tests
# ==========================================================================

class TestLookupRole:
    def test_returns_role_when_record_exists(self):
        db = FakeDB([{"tenant_id": "t1", "user_id": "u1", "role": "admin"}])
        assert lookup_role(db, "t1", "u1") == "admin"

    def test_returns_none_when_no_record(self):
        db = FakeDB([])
        assert lookup_role(db, "t1", "u1") is None

    def test_returns_none_when_different_tenant(self):
        db = FakeDB([{"tenant_id": "t2", "user_id": "u1", "role": "admin"}])
        assert lookup_role(db, "t1", "u1") is None

    def test_normalizes_role_to_lowercase(self):
        db = FakeDB([{"tenant_id": "t1", "user_id": "u1", "role": "  Admin  "}])
        assert lookup_role(db, "t1", "u1") == "admin"

    def test_never_raises_on_db_error(self):
        """If DB throws, lookup_role returns None instead of raising."""

        class BrokenDB:
            def table(self, name):
                raise RuntimeError("DB down")

        assert lookup_role(BrokenDB(), "t1", "u1") is None


# ==========================================================================
# resolve_role tests
# ==========================================================================

class TestResolveRole:
    def test_db_role_wins_over_requested(self):
        """DB says 'worker' — even if request says 'admin', DB wins."""
        db = FakeDB([{"tenant_id": "t1", "user_id": "u1", "role": "worker"}])
        result = resolve_role(db, "t1", "u1", requested_role="admin")
        assert result == "worker"

    def test_db_role_returned_when_no_request(self):
        db = FakeDB([{"tenant_id": "t1", "user_id": "u1", "role": "owner"}])
        result = resolve_role(db, "t1", "u1")
        assert result == "owner"

    def test_fallback_to_default_when_no_db_record(self):
        db = FakeDB([])
        result = resolve_role(db, "t1", "u1", requested_role="admin")
        assert result == DEFAULT_ROLE_IF_MISSING

    def test_default_role_when_no_record_and_no_request(self):
        db = FakeDB([])
        result = resolve_role(db, "t1", "u1")
        assert result == DEFAULT_ROLE_IF_MISSING

    def test_db_role_takes_precedence_even_when_matching(self):
        """If DB and request agree, still returns DB role."""
        db = FakeDB([{"tenant_id": "t1", "user_id": "u1", "role": "manager"}])
        result = resolve_role(db, "t1", "u1", requested_role="manager")
        assert result == "manager"
