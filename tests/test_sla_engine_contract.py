"""
Phase 117 — SLA Escalation Engine contract tests.

evaluate(payload) → EscalationResult

Groups:
    A — No breach (task on-time, acked, not expired)
    B — ACK_SLA_BREACH trigger
    C — COMPLETION_SLA_BREACH trigger
    D — Both triggers simultaneously
    E — Terminal states (Completed, Cancelled) — audit only, no actions
    F — Policy routing (ops-only, admin-only, both, neither)
    G — Audit event structure
    H — Determinism and idempotency (same input → same output)
    I — Edge cases (empty due strings, missing fields, exact boundary)
"""
from __future__ import annotations

import copy
import pytest

from tasks.sla_engine import (
    CRITICAL_ACK_SLA_MINUTES,
    EscalationAction,
    EscalationResult,
    evaluate,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _payload(
    now_utc="2026-03-09T10:10:00Z",
    ack_due="2026-03-09T10:15:00Z",
    completed_due="2026-03-09T18:00:00Z",
    state="Open",
    ack_state="Unacked",
    priority="Normal",
    task_id="task_001",
    prop_id="prop_001",
    task_type="CHECKIN_PREP",
    notify_ops_on=None,
    notify_admin_on=None,
    request_id="req_001",
    actor_id="system",
    role="ops",
    run_id="run_001",
):
    return {
        "actor": {"actor_id": actor_id, "role": role},
        "context": {
            "run_id": run_id,
            "timers_utc": {
                "now_utc": now_utc,
                "task_ack_due_utc": ack_due,
                "task_completed_due_utc": completed_due,
            },
        },
        "task": {
            "task_id": task_id,
            "property_id": prop_id,
            "task_type": task_type,
            "state": state,
            "priority": priority,
            "ack_state": ack_state,
        },
        "policy": {
            "notify_ops_on": notify_ops_on or [],
            "notify_admin_on": notify_admin_on or [],
        },
        "idempotency": {"request_id": request_id},
    }


# ---------------------------------------------------------------------------
# Group A — No breach
# ---------------------------------------------------------------------------

class TestNoBreach:

    def test_no_breach_returns_empty_actions(self):
        """Task is on-time, Unacked but due is in the future → no triggers."""
        p = _payload(
            now_utc="2026-03-09T10:10:00Z",
            ack_due="2026-03-09T10:15:00Z",
            completed_due="2026-03-09T18:00:00Z",
            state="Open",
            ack_state="Unacked",
            notify_ops_on=["ACK_SLA_BREACH", "COMPLETION_SLA_BREACH"],
        )
        result = evaluate(p)
        assert isinstance(result, EscalationResult)
        assert result.actions == []
        assert result.side_effects == []

    def test_acked_task_does_not_trigger_ack_breach(self):
        """Acked task past ack_due → no ACK_SLA_BREACH."""
        p = _payload(
            now_utc="2026-03-09T10:20:00Z",
            ack_due="2026-03-09T10:15:00Z",
            state="InProgress",
            ack_state="Acked",
            notify_ops_on=["ACK_SLA_BREACH"],
        )
        result = evaluate(p)
        assert all(a.reason != "ACK_SLA_BREACH" for a in result.actions)

    def test_no_breach_audit_has_empty_triggers_fired(self):
        p = _payload()
        result = evaluate(p)
        assert result.audit_event["triggers_fired"] == []
        assert result.audit_event["actions_emitted"] == []


# ---------------------------------------------------------------------------
# Group B — ACK_SLA_BREACH
# ---------------------------------------------------------------------------

class TestAckSlaBreach:

    def test_ack_breach_when_now_equals_ack_due(self):
        """Boundary: now_utc == task_ack_due_utc → breach."""
        p = _payload(
            now_utc="2026-03-09T10:15:00Z",
            ack_due="2026-03-09T10:15:00Z",
            ack_state="Unacked",
            notify_ops_on=["ACK_SLA_BREACH"],
        )
        result = evaluate(p)
        triggers = result.audit_event["triggers_fired"]
        assert "ACK_SLA_BREACH" in triggers

    def test_ack_breach_when_now_after_ack_due(self):
        p = _payload(
            now_utc="2026-03-09T10:20:00Z",
            ack_due="2026-03-09T10:15:00Z",
            ack_state="Unacked",
            notify_ops_on=["ACK_SLA_BREACH"],
        )
        result = evaluate(p)
        assert any(a.action_type == "notify_ops" and a.reason == "ACK_SLA_BREACH"
                   for a in result.actions)

    def test_ack_breach_before_ack_due_no_trigger(self):
        p = _payload(
            now_utc="2026-03-09T10:14:59Z",
            ack_due="2026-03-09T10:15:00Z",
            ack_state="Unacked",
            notify_ops_on=["ACK_SLA_BREACH"],
        )
        result = evaluate(p)
        assert result.actions == []

    def test_ack_breach_empty_ack_due_no_trigger(self):
        """Empty task_ack_due_utc → ACK breach never fires."""
        p = _payload(ack_due="", ack_state="Unacked", notify_ops_on=["ACK_SLA_BREACH"])
        result = evaluate(p)
        assert all(a.reason != "ACK_SLA_BREACH" for a in result.actions)

    def test_ack_breach_action_carries_correct_fields(self):
        p = _payload(
            now_utc="2026-03-09T10:20:00Z",
            ack_due="2026-03-09T10:15:00Z",
            ack_state="Unacked",
            task_id="task_ABC",
            prop_id="prop_XYZ",
            request_id="req_999",
            notify_ops_on=["ACK_SLA_BREACH"],
        )
        result = evaluate(p)
        action = next(a for a in result.actions if a.reason == "ACK_SLA_BREACH")
        assert action.task_id == "task_ABC"
        assert action.property_id == "prop_XYZ"
        assert action.request_id == "req_999"
        assert action.action_type == "notify_ops"
        assert action.target == "ops"


# ---------------------------------------------------------------------------
# Group C — COMPLETION_SLA_BREACH
# ---------------------------------------------------------------------------

class TestCompletionSlaBreach:

    def test_completion_breach_when_now_equals_completed_due(self):
        p = _payload(
            now_utc="2026-03-09T18:00:00Z",
            completed_due="2026-03-09T18:00:00Z",
            state="Open",
            notify_ops_on=["COMPLETION_SLA_BREACH"],
        )
        result = evaluate(p)
        assert "COMPLETION_SLA_BREACH" in result.audit_event["triggers_fired"]

    def test_completion_breach_after_due(self):
        p = _payload(
            now_utc="2026-03-09T19:00:00Z",
            completed_due="2026-03-09T18:00:00Z",
            state="InProgress",
            notify_ops_on=["COMPLETION_SLA_BREACH"],
        )
        result = evaluate(p)
        assert any(a.reason == "COMPLETION_SLA_BREACH" for a in result.actions)

    def test_completion_breach_before_due_no_trigger(self):
        p = _payload(
            now_utc="2026-03-09T17:59:00Z",
            completed_due="2026-03-09T18:00:00Z",
            state="Open",
            notify_ops_on=["COMPLETION_SLA_BREACH"],
        )
        result = evaluate(p)
        assert result.actions == []

    def test_completion_breach_empty_completed_due_no_trigger(self):
        p = _payload(completed_due="", notify_ops_on=["COMPLETION_SLA_BREACH"])
        result = evaluate(p)
        assert all(a.reason != "COMPLETION_SLA_BREACH" for a in result.actions)

    def test_completed_state_does_not_trigger_completion_breach(self):
        """State=Completed is terminal — no COMPLETION_SLA_BREACH even if past due."""
        p = _payload(
            now_utc="2026-03-09T19:00:00Z",
            completed_due="2026-03-09T18:00:00Z",
            state="Completed",
            notify_ops_on=["COMPLETION_SLA_BREACH"],
        )
        result = evaluate(p)
        assert result.actions == []  # terminal state


# ---------------------------------------------------------------------------
# Group D — Both triggers simultaneously
# ---------------------------------------------------------------------------

class TestBothTriggers:

    def test_both_triggers_fire_simultaneously(self):
        p = _payload(
            now_utc="2026-03-09T20:00:00Z",
            ack_due="2026-03-09T10:15:00Z",   # past
            completed_due="2026-03-09T18:00:00Z",  # past
            state="Open",
            ack_state="Unacked",
            notify_ops_on=["ACK_SLA_BREACH", "COMPLETION_SLA_BREACH"],
        )
        result = evaluate(p)
        triggers = result.audit_event["triggers_fired"]
        assert "ACK_SLA_BREACH" in triggers
        assert "COMPLETION_SLA_BREACH" in triggers
        assert len(result.actions) == 2

    def test_both_triggers_emit_separate_actions(self):
        p = _payload(
            now_utc="2026-03-09T20:00:00Z",
            ack_due="2026-03-09T10:15:00Z",
            completed_due="2026-03-09T18:00:00Z",
            state="InProgress",
            ack_state="Unacked",
            notify_ops_on=["ACK_SLA_BREACH", "COMPLETION_SLA_BREACH"],
            notify_admin_on=["ACK_SLA_BREACH"],
        )
        result = evaluate(p)
        reasons = [a.reason for a in result.actions]
        # ops gets both, admin gets ACK only
        assert reasons.count("ACK_SLA_BREACH") == 2       # ops + admin
        assert reasons.count("COMPLETION_SLA_BREACH") == 1  # ops only


# ---------------------------------------------------------------------------
# Group E — Terminal states
# ---------------------------------------------------------------------------

class TestTerminalStates:

    @pytest.mark.parametrize("state", ["Completed", "Cancelled"])
    def test_terminal_state_emits_no_actions(self, state):
        p = _payload(
            now_utc="2026-03-09T20:00:00Z",
            ack_due="2026-03-09T10:00:00Z",
            completed_due="2026-03-09T18:00:00Z",
            state=state,
            ack_state="Unacked",
            notify_ops_on=["ACK_SLA_BREACH", "COMPLETION_SLA_BREACH"],
            notify_admin_on=["ACK_SLA_BREACH"],
        )
        result = evaluate(p)
        assert result.actions == []

    @pytest.mark.parametrize("state", ["Completed", "Cancelled"])
    def test_terminal_state_still_emits_audit(self, state):
        p = _payload(state=state)
        result = evaluate(p)
        assert result.audit_event["event_type"] == "AuditEvent"
        assert result.audit_event["triggers_fired"] == []

    @pytest.mark.parametrize("state", ["Completed", "Cancelled"])
    def test_terminal_side_effects_always_empty(self, state):
        p = _payload(state=state)
        assert evaluate(p).side_effects == []


# ---------------------------------------------------------------------------
# Group F — Policy routing
# ---------------------------------------------------------------------------

class TestPolicyRouting:

    def test_notify_ops_only(self):
        p = _payload(
            now_utc="2026-03-09T10:20:00Z",
            ack_due="2026-03-09T10:15:00Z",
            ack_state="Unacked",
            notify_ops_on=["ACK_SLA_BREACH"],
            notify_admin_on=[],
        )
        result = evaluate(p)
        assert len(result.actions) == 1
        assert result.actions[0].action_type == "notify_ops"

    def test_notify_admin_only(self):
        p = _payload(
            now_utc="2026-03-09T10:20:00Z",
            ack_due="2026-03-09T10:15:00Z",
            ack_state="Unacked",
            notify_ops_on=[],
            notify_admin_on=["ACK_SLA_BREACH"],
        )
        result = evaluate(p)
        assert len(result.actions) == 1
        assert result.actions[0].action_type == "notify_admin"

    def test_notify_both(self):
        p = _payload(
            now_utc="2026-03-09T10:20:00Z",
            ack_due="2026-03-09T10:15:00Z",
            ack_state="Unacked",
            notify_ops_on=["ACK_SLA_BREACH"],
            notify_admin_on=["ACK_SLA_BREACH"],
        )
        result = evaluate(p)
        types = {a.action_type for a in result.actions}
        assert types == {"notify_ops", "notify_admin"}

    def test_notify_neither_trigger_in_policy(self):
        """Trigger fires but is not in any policy → no actions emitted."""
        p = _payload(
            now_utc="2026-03-09T10:20:00Z",
            ack_due="2026-03-09T10:15:00Z",
            ack_state="Unacked",
            notify_ops_on=[],
            notify_admin_on=[],
        )
        result = evaluate(p)
        assert result.actions == []
        # But trigger IS still recorded in audit
        assert "ACK_SLA_BREACH" in result.audit_event["triggers_fired"]


# ---------------------------------------------------------------------------
# Group G — Audit event structure
# ---------------------------------------------------------------------------

class TestAuditEventStructure:

    def test_audit_event_has_required_keys(self):
        p = _payload()
        audit = evaluate(p).audit_event
        required = {
            "event_type", "request_id", "run_id", "now_utc",
            "actor_id", "role", "task", "timers_utc",
            "triggers_fired", "actions_emitted",
        }
        assert required.issubset(audit.keys())

    def test_audit_event_type_is_audit_event(self):
        assert evaluate(_payload()).audit_event["event_type"] == "AuditEvent"

    def test_audit_task_fields_echoed(self):
        p = _payload(task_id="T99", prop_id="P77", state="Open", priority="High")
        audit = evaluate(p).audit_event
        assert audit["task"]["task_id"] == "T99"
        assert audit["task"]["property_id"] == "P77"
        assert audit["task"]["state"] == "Open"
        assert audit["task"]["priority"] == "High"

    def test_audit_actions_emitted_matches_actions(self):
        p = _payload(
            now_utc="2026-03-09T10:20:00Z",
            ack_due="2026-03-09T10:15:00Z",
            ack_state="Unacked",
            notify_ops_on=["ACK_SLA_BREACH"],
        )
        result = evaluate(p)
        assert len(result.audit_event["actions_emitted"]) == len(result.actions)

    def test_audit_request_id_echoed(self):
        p = _payload(request_id="unique-req-XYZ")
        assert evaluate(p).audit_event["request_id"] == "unique-req-XYZ"


# ---------------------------------------------------------------------------
# Group H — Determinism and idempotency
# ---------------------------------------------------------------------------

class TestDeterminism:

    def test_same_input_same_output(self):
        p = _payload(
            now_utc="2026-03-09T10:20:00Z",
            ack_due="2026-03-09T10:15:00Z",
            ack_state="Unacked",
            notify_ops_on=["ACK_SLA_BREACH"],
        )
        r1 = evaluate(copy.deepcopy(p))
        r2 = evaluate(copy.deepcopy(p))
        assert r1.actions == r2.actions
        assert r1.audit_event == r2.audit_event

    def test_different_request_id_same_logic(self):
        """request_id changes echo in audit but doesn't affect trigger logic."""
        p1 = _payload(request_id="req_A", now_utc="2026-03-09T10:20:00Z",
                      ack_due="2026-03-09T10:15:00Z", ack_state="Unacked",
                      notify_ops_on=["ACK_SLA_BREACH"])
        p2 = _payload(request_id="req_B", now_utc="2026-03-09T10:20:00Z",
                      ack_due="2026-03-09T10:15:00Z", ack_state="Unacked",
                      notify_ops_on=["ACK_SLA_BREACH"])
        r1 = evaluate(p1)
        r2 = evaluate(p2)
        assert r1.audit_event["triggers_fired"] == r2.audit_event["triggers_fired"]
        assert len(r1.actions) == len(r2.actions)

    def test_side_effects_always_empty(self):
        for state in ["Open", "InProgress", "Completed", "Cancelled"]:
            result = evaluate(_payload(state=state))
            assert result.side_effects == []


# ---------------------------------------------------------------------------
# Group I — Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_critical_ack_sla_constant_is_5_minutes(self):
        assert CRITICAL_ACK_SLA_MINUTES == 5

    def test_missing_optional_completed_due_no_crash(self):
        p = _payload()
        p["context"]["timers_utc"].pop("task_completed_due_utc", None)
        # Should not raise — treats missing as empty
        result = evaluate(p)
        assert isinstance(result, EscalationResult)

    def test_both_due_timestamps_empty_no_actions(self):
        p = _payload(
            ack_due="",
            completed_due="",
            ack_state="Unacked",
            notify_ops_on=["ACK_SLA_BREACH", "COMPLETION_SLA_BREACH"],
        )
        result = evaluate(p)
        assert result.actions == []

    def test_inprogress_state_not_terminal(self):
        """InProgress is NOT terminal — escalation should still apply."""
        p = _payload(
            now_utc="2026-03-09T10:20:00Z",
            ack_due="2026-03-09T10:15:00Z",
            state="InProgress",
            ack_state="Unacked",
            notify_ops_on=["ACK_SLA_BREACH"],
        )
        result = evaluate(p)
        assert any(a.reason == "ACK_SLA_BREACH" for a in result.actions)

    def test_all_priorities_process_correctly(self):
        for priority in ["Normal", "High", "Critical"]:
            p = _payload(
                priority=priority,
                now_utc="2026-03-09T10:20:00Z",
                ack_due="2026-03-09T10:15:00Z",
                ack_state="Unacked",
                notify_ops_on=["ACK_SLA_BREACH"],
            )
            result = evaluate(p)
            assert isinstance(result, EscalationResult)
