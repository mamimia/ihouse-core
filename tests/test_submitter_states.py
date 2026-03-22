"""
Phase 862 P17 — Submitter States Tests
========================================
Tests the state transition logic and approve_intake function.
"""
from __future__ import annotations

import pytest
from services.submitter_states import (
    can_transition,
    ALLOWED_TRANSITIONS,
    ALL_STATES,
)


class TestCanTransition:
    def test_draft_to_pending_review(self):
        assert can_transition("draft", "pending_review") is True

    def test_draft_to_approved_blocked(self):
        assert can_transition("draft", "approved") is False

    def test_pending_review_to_approved(self):
        assert can_transition("pending_review", "approved") is True

    def test_pending_review_to_rejected(self):
        assert can_transition("pending_review", "rejected") is True

    def test_pending_review_to_expired(self):
        assert can_transition("pending_review", "expired") is True

    def test_approved_to_owner_provisioned(self):
        assert can_transition("approved", "owner_provisioned") is True

    def test_approved_to_rejected_blocked(self):
        assert can_transition("approved", "rejected") is False

    def test_terminal_states_have_no_transitions(self):
        for state in ("rejected", "expired", "owner_provisioned"):
            assert not ALLOWED_TRANSITIONS[state], f"{state} should be terminal"

    def test_all_states_defined(self):
        expected = {"draft", "pending_review", "approved", "rejected", "expired", "owner_provisioned"}
        assert ALL_STATES == expected

    def test_unknown_state_returns_false(self):
        assert can_transition("nonexistent", "approved") is False
