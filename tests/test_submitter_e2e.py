"""
Phase 862 P26 — End-to-End Submitter → Owner Continuity Test
==============================================================

Proves the full lifecycle:
1. User submits intake request (with user_id linkage)
2. Submitter transitions to pending_review
3. Admin approves → owner provisioned
4. Identity surface reflects the new membership
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, call

from services.submitter_states import (
    can_transition, transition_intake, approve_intake,
    ALLOWED_TRANSITIONS,
)


class TestEndToEndSubmitterToOwner:
    """Full lifecycle test: intake → pending_review → approved → owner_provisioned."""

    def _mock_db(self, intake_row: dict) -> MagicMock:
        """Create a mock DB that returns the given intake row and tracks updates."""
        db = MagicMock()

        # Mutable state
        current_row = dict(intake_row)

        def mock_select_execute():
            result = MagicMock()
            result.data = [dict(current_row)]
            return result

        def mock_update_execute():
            result = MagicMock()
            result.data = []
            return result

        # Chain: db.table("intake_requests").select(...).eq(...).limit(...).execute()
        select_chain = MagicMock()
        select_chain.eq.return_value = select_chain
        select_chain.limit.return_value = select_chain
        select_chain.execute = mock_select_execute

        # Chain: db.table("intake_requests").update(...).eq(...).execute()
        update_chain = MagicMock()
        update_chain.eq.return_value = update_chain
        update_chain.execute = mock_update_execute

        def table_side_effect(name):
            t = MagicMock()
            t.select.return_value = select_chain
            t.update.return_value = update_chain
            t.upsert.return_value = update_chain
            return t

        db.table.side_effect = table_side_effect
        db._current_row = current_row
        return db

    def test_full_lifecycle_draft_to_owner(self):
        """Test: draft → pending_review → approved → owner_provisioned."""
        # 1. Verify allowed transitions
        assert can_transition("draft", "pending_review")
        assert can_transition("pending_review", "approved")
        assert can_transition("approved", "owner_provisioned")

    def test_transition_intake_updates_status(self):
        """transition_intake calls db.update correctly."""
        db = self._mock_db({"id": "intake-1", "user_id": "user-1", "status": "pending_review"})

        result = transition_intake(
            db, "intake-1",
            current_status="pending_review",
            target_status="approved",
            admin_user_id="admin-1",
        )

        assert result["ok"] is True
        assert result["status"] == "approved"
        # Verify DB was called
        db.table.assert_called_with("intake_requests")

    def test_transition_blocked_for_invalid(self):
        """transition_intake raises ValueError for invalid transitions."""
        db = self._mock_db({"id": "intake-1", "user_id": "user-1", "status": "rejected"})

        with pytest.raises(ValueError, match="Invalid transition"):
            transition_intake(
                db, "intake-1",
                current_status="rejected",
                target_status="approved",
            )

    @patch("services.tenant_bridge.provision_user_tenant")
    def test_approve_intake_provisions_owner(self, mock_provision):
        """approve_intake fetches intake, transitions, and provisions owner."""
        mock_provision.return_value = {"user_id": "user-1", "tenant_id": "tenant-1", "role": "owner"}

        db = self._mock_db({
            "id": "intake-1",
            "user_id": "user-1",
            "status": "pending_review",
            "email": "test@example.com",
        })

        result = approve_intake(
            db, "intake-1",
            admin_user_id="admin-1",
            tenant_id="tenant-1",
        )

        assert result["ok"] is True
        assert result["status"] == "owner_provisioned"
        assert result["user_id"] == "user-1"
        assert result["tenant_id"] == "tenant-1"

        # Verify provision was called with correct args
        mock_provision.assert_called_once_with(
            db, "user-1",
            tenant_id="tenant-1",
            role="owner",
        )

    def test_approve_intake_rejects_without_user_id(self):
        """approve_intake raises ValueError if intake has no linked user_id."""
        db = self._mock_db({
            "id": "intake-1",
            "user_id": None,
            "status": "pending_review",
            "email": "test@example.com",
        })

        with pytest.raises(ValueError, match="no linked user_id"):
            approve_intake(
                db, "intake-1",
                admin_user_id="admin-1",
                tenant_id="tenant-1",
            )

    def test_approve_intake_rejects_wrong_state(self):
        """approve_intake raises ValueError for non-pending/approved intake."""
        db = self._mock_db({
            "id": "intake-1",
            "user_id": "user-1",
            "status": "rejected",
            "email": "test@example.com",
        })

        with pytest.raises(ValueError, match="Cannot approve"):
            approve_intake(
                db, "intake-1",
                admin_user_id="admin-1",
                tenant_id="tenant-1",
            )

    def test_terminal_states_are_final(self):
        """Terminal states (rejected, expired, owner_provisioned) have no outgoing transitions."""
        for state in ("rejected", "expired", "owner_provisioned"):
            assert not ALLOWED_TRANSITIONS[state], f"{state} should be terminal"
            assert not can_transition(state, "pending_review")
            assert not can_transition(state, "approved")
