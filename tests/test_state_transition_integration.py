"""
Phase 326 — State Transition Guard Integration Tests
=====================================================

Tests the `validate()` function from state_transition_guard.py.

Group A: Allowed Transitions
  ✓  Matching rule → allowed, correct next_state
  ✓  Role-scoped rule only allows matching role
  ✓  force_next_state override works

Group B: Denied Transitions
  ✓  Explicit deny rule → denied, current_state unchanged
  ✓  No matching rule → UNKNOWN_TRANSITION denial
  ✓  Wrong role → no match → UNKNOWN_TRANSITION

Group C: Invariant Checks
  ✓  Invariant passes → allowed proceeds
  ✓  Invariant fails → INVARIANT_ERROR denial
  ✓  Invariant checked after priority rule allows

Group D: Input Validation
  ✓  Missing request_id → INPUT_INVALID
  ✓  Missing entity_type → INPUT_INVALID
  ✓  Empty payload → INPUT_INVALID, never raises

Group E: Audit Event Shape
  ✓  AuditEvent has all required keys
  ✓  decision_allowed reflects final decision
  ✓  applied_rules contains matched rule IDs
  ✓  side_effects always empty

CI-safe: pure, no DB, no network.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("IHOUSE_ENV", "test")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from services.state_transition_guard import (
    validate,
    TransitionResult,
    DENIAL_INPUT_INVALID,
    DENIAL_UNKNOWN_TRANS,
    DENIAL_RULE_DENIED,
    DENIAL_INVARIANT_ERROR,
)


# ---------------------------------------------------------------------------
# Builder helpers
# ---------------------------------------------------------------------------

def _payload(
    current_state: str = "Open",
    requested_state: str = "InProgress",
    role: str = "worker",
    rules: list = None,
    invariants: dict = None,
    related_facts: dict = None,
    request_id: str = "req-001",
    entity_type: str = "task",
    entity_id: str = "T-001",
) -> dict:
    return {
        "actor":   {"actor_id": "U-001", "role": role},
        "entity":  {"entity_type": entity_type, "entity_id": entity_id},
        "current": {"current_state": current_state, "current_version": 1},
        "requested": {
            "requested_state": requested_state,
            "reason_code": "worker_claimed",
            "request_id": request_id,
        },
        "context": {
            "priority_stack": rules or _default_rules(),
            "invariants": invariants or {},
            "related_facts": related_facts or {},
        },
        "time": {"now_utc": "2026-03-12T07:00:00Z"},
    }


def _default_rules() -> list:
    return [
        {
            "rule_id": "allow_open_to_inprogress",
            "from_states": ["Open"],
            "to_states": ["InProgress"],
            "roles": ["worker", "admin"],
            "effect": "allow",
            "terminal": True,
        },
        {
            "rule_id": "allow_inprogress_to_completed",
            "from_states": ["InProgress"],
            "to_states": ["Completed"],
            "roles": ["worker", "admin"],
            "effect": "allow",
            "terminal": True,
        },
        {
            "rule_id": "deny_direct_to_completed",
            "from_states": ["Open"],
            "to_states": ["Completed"],
            "roles": [],  # all roles
            "effect": "deny",
            "terminal": True,
        },
    ]


# ---------------------------------------------------------------------------
# Group A — Allowed Transitions
# ---------------------------------------------------------------------------

class TestAllowedTransitions:

    def test_matching_rule_allows_transition(self):
        result = validate(_payload(current_state="Open", requested_state="InProgress"))
        assert result.decision.allowed is True
        assert result.decision.allowed_next_state == "InProgress"
        assert result.decision.denial_code == ""

    def test_role_scoped_rule_allows_admin(self):
        result = validate(_payload(
            current_state="Open", requested_state="InProgress", role="admin"
        ))
        assert result.decision.allowed is True

    def test_force_next_state_override(self):
        rules = [
            {
                "rule_id": "admin_fast_track",
                "from_states": ["Open"],
                "to_states": ["InProgress"],
                "roles": ["admin"],
                "effect": "allow",
                "terminal": True,
                "force_next_state": "FastTracked",
            }
        ]
        result = validate(_payload(current_state="Open", requested_state="InProgress",
                                   role="admin", rules=rules))
        assert result.decision.allowed is True
        assert result.decision.allowed_next_state == "FastTracked"

    def test_sequential_transition_allowed(self):
        result = validate(_payload(current_state="InProgress", requested_state="Completed"))
        assert result.decision.allowed is True
        assert result.decision.allowed_next_state == "Completed"


# ---------------------------------------------------------------------------
# Group B — Denied Transitions
# ---------------------------------------------------------------------------

class TestDeniedTransitions:

    def test_explicit_deny_rule_fires(self):
        result = validate(_payload(current_state="Open", requested_state="Completed"))
        assert result.decision.allowed is False
        assert result.decision.allowed_next_state == "Open"
        assert result.decision.denial_code == DENIAL_RULE_DENIED

    def test_no_matching_rule_unknown_transition(self):
        result = validate(_payload(current_state="Completed", requested_state="Open"))
        assert result.decision.allowed is False
        assert result.decision.denial_code == DENIAL_UNKNOWN_TRANS

    def test_wrong_role_no_match(self):
        rules = [
            {
                "rule_id": "admin_only_rule",
                "from_states": ["Open"],
                "to_states": ["InProgress"],
                "roles": ["admin"],
                "effect": "allow",
                "terminal": True,
            }
        ]
        result = validate(_payload(current_state="Open", requested_state="InProgress",
                                   role="worker", rules=rules))
        assert result.decision.allowed is False
        assert result.decision.denial_code == DENIAL_UNKNOWN_TRANS


# ---------------------------------------------------------------------------
# Group C — Invariant Checks
# ---------------------------------------------------------------------------

class TestInvariantChecks:

    def test_invariant_passes_allows_proceed(self):
        result = validate(_payload(
            invariants={"tenant_active": {"field": "active", "must_equal": True}},
            related_facts={"active": True},
        ))
        assert result.decision.allowed is True

    def test_invariant_fails_denies(self):
        result = validate(_payload(
            invariants={"tenant_active": {"field": "active", "must_equal": True}},
            related_facts={"active": False},
        ))
        assert result.decision.allowed is False
        assert result.decision.denial_code == DENIAL_INVARIANT_ERROR

    def test_invariant_checked_after_allow_rule(self):
        result = validate(_payload(
            invariants={"must_have_property": {"field": "property_id", "must_equal": "P-001"}},
            related_facts={"property_id": "P-999"},  # wrong
        ))
        # Rule allows, but invariant fails
        assert result.decision.allowed is False


# ---------------------------------------------------------------------------
# Group D — Input Validation
# ---------------------------------------------------------------------------

class TestInputValidation:

    def test_missing_request_id_denied(self):
        p = _payload(request_id="")
        result = validate(p)
        assert result.decision.allowed is False
        assert result.decision.denial_code == DENIAL_INPUT_INVALID

    def test_missing_entity_type_denied(self):
        p = _payload(entity_type="")
        result = validate(p)
        assert result.decision.allowed is False
        assert result.decision.denial_code == DENIAL_INPUT_INVALID

    def test_empty_payload_never_raises(self):
        result = validate({})
        assert isinstance(result, TransitionResult)
        assert result.decision.allowed is False


# ---------------------------------------------------------------------------
# Group E — Audit Event Shape
# ---------------------------------------------------------------------------

class TestAuditEventShape:

    def test_audit_event_has_required_keys(self):
        result = validate(_payload())
        ae = result.audit_event
        required = ("event_type", "request_id", "actor_id", "role", "entity_type",
                    "entity_id", "current_state", "requested_state",
                    "allowed_next_state", "decision_allowed", "denial_code",
                    "applied_rules", "now_utc")
        for key in required:
            assert key in ae, f"Missing: {key}"

    def test_decision_allowed_reflects_result(self):
        result = validate(_payload())  # allowed
        assert result.audit_event["decision_allowed"] is True
        denied = validate(_payload(current_state="Open", requested_state="Completed"))
        assert denied.audit_event["decision_allowed"] is False

    def test_applied_rules_contains_matched_id(self):
        result = validate(_payload())
        assert "allow_open_to_inprogress" in result.decision.applied_rules

    def test_side_effects_always_empty(self):
        result = validate(_payload())
        assert result.side_effects == []
