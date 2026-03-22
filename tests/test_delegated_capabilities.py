"""
Phase 862 P31 — Tests for Delegated Capability Model
"""
import pytest
from unittest.mock import MagicMock

from services.delegated_capabilities import (
    ALL_CAPABILITIES,
    DEFAULT_MANAGER_CAPABILITIES,
    get_delegated_capabilities,
    has_capability,
    set_capabilities,
)


class TestCapabilityExtraction:
    """Tests for extracting capabilities from permissions JSONB."""

    def test_empty_permissions(self):
        assert get_delegated_capabilities(None) == {}
        assert get_delegated_capabilities({}) == {}

    def test_no_capabilities_key(self):
        assert get_delegated_capabilities({"other": "data"}) == {}

    def test_valid_capabilities(self):
        perms = {"capabilities": {"financial": True, "staffing": False}}
        caps = get_delegated_capabilities(perms)
        assert caps == {"financial": True, "staffing": False}

    def test_unknown_capabilities_ignored(self):
        perms = {"capabilities": {"financial": True, "unknown_thing": True}}
        caps = get_delegated_capabilities(perms)
        assert "unknown_thing" not in caps
        assert caps == {"financial": True}

    def test_has_capability_true(self):
        perms = {"capabilities": {"financial": True}}
        assert has_capability(perms, "financial") is True

    def test_has_capability_false(self):
        perms = {"capabilities": {"financial": False}}
        assert has_capability(perms, "financial") is False

    def test_has_capability_missing(self):
        perms = {"capabilities": {"staffing": True}}
        assert has_capability(perms, "financial") is False

    def test_has_capability_none_permissions(self):
        assert has_capability(None, "financial") is False


class TestCapabilityConstants:
    """Tests for the capability registry."""

    def test_all_capabilities_nonempty(self):
        assert len(ALL_CAPABILITIES) >= 7

    def test_known_capabilities(self):
        expected = {"financial", "staffing", "properties", "bookings", "maintenance", "settings", "intake"}
        assert expected.issubset(ALL_CAPABILITIES)

    def test_defaults_subset_of_all(self):
        for k in DEFAULT_MANAGER_CAPABILITIES:
            assert k in ALL_CAPABILITIES


class TestSetCapabilities:
    """Tests for admin-facing capability setter."""

    def _mock_db(self, role="manager", existing_perms=None):
        db = MagicMock()

        result = MagicMock()
        result.data = [{
            "role": role,
            "permissions": existing_perms or {},
        }]

        select_chain = MagicMock()
        select_chain.eq.return_value = select_chain
        select_chain.limit.return_value = select_chain
        select_chain.execute.return_value = result

        update_chain = MagicMock()
        update_chain.eq.return_value = update_chain
        update_chain.execute.return_value = MagicMock(data=[])

        def table_side_effect(name):
            t = MagicMock()
            t.select.return_value = select_chain
            t.update.return_value = update_chain
            return t

        db.table.side_effect = table_side_effect
        return db

    def test_set_valid_capabilities(self):
        db = self._mock_db()
        result = set_capabilities(db, "t1", "u1", {"financial": True, "staffing": True})
        assert result["ok"] is True
        assert result["capabilities"]["financial"] is True
        assert result["capabilities"]["staffing"] is True

    def test_rejects_non_manager(self):
        db = self._mock_db(role="worker")
        with pytest.raises(ValueError, match="only for managers"):
            set_capabilities(db, "t1", "u1", {"financial": True})

    def test_rejects_unknown_user(self):
        db = MagicMock()
        result = MagicMock()
        result.data = []
        chain = MagicMock()
        chain.eq.return_value = chain
        chain.limit.return_value = chain
        chain.execute.return_value = result
        table = MagicMock()
        table.select.return_value = chain
        db.table.return_value = table

        with pytest.raises(ValueError, match="not found"):
            set_capabilities(db, "t1", "u_unknown", {"financial": True})

    def test_merges_with_existing(self):
        existing = {"capabilities": {"bookings": True}}
        db = self._mock_db(existing_perms=existing)
        result = set_capabilities(db, "t1", "u1", {"financial": True})
        # Should have both bookings (existing) and financial (new)
        assert result["capabilities"]["bookings"] is True
        assert result["capabilities"]["financial"] is True

    def test_ignores_unknown_capabilities(self):
        db = self._mock_db()
        result = set_capabilities(db, "t1", "u1", {"financial": True, "fake_cap": True})
        assert "fake_cap" not in result["capabilities"]
        assert result["capabilities"]["financial"] is True
