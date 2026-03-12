"""
Phase 324 — SLA Engine + Task Workflow Integration Tests
=========================================================

Extends sla_engine contract tests with:

Group A: Combined ACK + Completion SLA Breach
  ✓  Both SLAs breached simultaneously → 2 triggers fired
  ✓  Only ops notified for ACK, only admin for completion
  ✓  Both ops + admin when both triggers + cross-policy

Group B: Terminal State Guard
  ✓  Completed task → no actions emitted (audit only)
  ✓  Cancelled task → no actions emitted (audit only)

Group C: SLA Boundary Conditions
  ✓  now == ack_due (at boundary) → breach fires
  ✓  now < ack_due → no breach
  ✓  Empty ack_due string → no ACK trigger
  ✓  Acked task past ack_due → no ACK trigger (already acked)

Group D: Audit Event Shape Validation
  ✓  audit_event has all required keys
  ✓  triggers_fired matches actions_emitted count
  ✓  side_effects always empty

Group E: Full SLA→Dispatch Chain
  ✓  evaluate() → dispatch_escalations() → BridgeResult
  ✓  No DB users → no dispatches but result contains action type
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("IHOUSE_ENV", "test")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tasks.sla_engine import evaluate, EscalationResult, CRITICAL_ACK_SLA_MINUTES
from channels.sla_dispatch_bridge import dispatch_escalations


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _payload(
    state="Open",
    ack_state="Unacked",
    now_utc="2026-03-12T07:10:00Z",
    ack_due="2026-03-12T07:05:00Z",       # 5 min ago → breach
    completed_due="2026-03-12T08:00:00Z", # in future
    notify_ops_on=None,
    notify_admin_on=None,
    task_id="T-001",
    prop_id="P-001",
):
    return {
        "actor": {"actor_id": "worker-1", "role": "worker"},
        "context": {
            "run_id": "run-001",
            "timers_utc": {
                "now_utc": now_utc,
                "task_ack_due_utc": ack_due,
                "task_completed_due_utc": completed_due,
            },
        },
        "task": {
            "task_id": task_id,
            "property_id": prop_id,
            "task_type": "CLEANING",
            "state": state,
            "priority": "Critical",
            "ack_state": ack_state,
        },
        "policy": {
            "notify_ops_on": notify_ops_on or ["ACK_SLA_BREACH"],
            "notify_admin_on": notify_admin_on or [],
        },
        "idempotency": {"request_id": "req-001"},
    }


# ---------------------------------------------------------------------------
# Group A — Combined SLA Breaches
# ---------------------------------------------------------------------------

class TestCombinedSLABreaches:

    def test_both_sla_breached_fires_two_triggers(self):
        p = _payload(
            now_utc="2026-03-12T10:00:00Z",
            ack_due="2026-03-12T07:05:00Z",
            completed_due="2026-03-12T09:00:00Z",
            notify_ops_on=["ACK_SLA_BREACH", "COMPLETION_SLA_BREACH"],
        )
        result = evaluate(p)
        assert len(result.audit_event["triggers_fired"]) == 2
        assert "ACK_SLA_BREACH" in result.audit_event["triggers_fired"]
        assert "COMPLETION_SLA_BREACH" in result.audit_event["triggers_fired"]

    def test_ops_notified_for_ack_admin_for_completion(self):
        p = _payload(
            now_utc="2026-03-12T10:00:00Z",
            ack_due="2026-03-12T07:05:00Z",
            completed_due="2026-03-12T09:00:00Z",
            notify_ops_on=["ACK_SLA_BREACH"],
            notify_admin_on=["COMPLETION_SLA_BREACH"],
        )
        result = evaluate(p)
        assert len(result.actions) == 2
        targets = {a.target for a in result.actions}
        assert "ops" in targets
        assert "admin" in targets

    def test_cross_policy_notify_both_on_ack(self):
        p = _payload(
            now_utc="2026-03-12T10:00:00Z",
            ack_due="2026-03-12T07:05:00Z",
            completed_due="2026-03-12T12:00:00Z",   # future
            notify_ops_on=["ACK_SLA_BREACH"],
            notify_admin_on=["ACK_SLA_BREACH"],
        )
        result = evaluate(p)
        # Both ops + admin notified for ACK breach
        assert len(result.actions) == 2
        assert all(a.reason == "ACK_SLA_BREACH" for a in result.actions)


# ---------------------------------------------------------------------------
# Group B — Terminal State Guard
# ---------------------------------------------------------------------------

class TestTerminalStateGuard:

    def test_completed_task_no_actions(self):
        p = _payload(state="Completed", notify_ops_on=["ACK_SLA_BREACH", "COMPLETION_SLA_BREACH"])
        result = evaluate(p)
        assert result.actions == []

    def test_cancelled_task_no_actions(self):
        p = _payload(state="Cancelled", notify_ops_on=["ACK_SLA_BREACH"])
        result = evaluate(p)
        assert result.actions == []

    def test_completed_still_has_audit_event(self):
        p = _payload(state="Completed")
        result = evaluate(p)
        assert result.audit_event is not None
        assert result.audit_event["task"]["state"] == "Completed"


# ---------------------------------------------------------------------------
# Group C — SLA Boundary Conditions
# ---------------------------------------------------------------------------

class TestSLABoundaryConditions:

    def test_at_boundary_ack_breach_fires(self):
        """now == ack_due → breach must fire."""
        p = _payload(
            now_utc="2026-03-12T07:05:00Z",
            ack_due="2026-03-12T07:05:00Z",
            notify_ops_on=["ACK_SLA_BREACH"],
        )
        result = evaluate(p)
        assert any(a.reason == "ACK_SLA_BREACH" for a in result.actions)

    def test_before_deadline_no_breach(self):
        """now < ack_due → no breach."""
        p = _payload(
            now_utc="2026-03-12T07:00:00Z",
            ack_due="2026-03-12T07:05:00Z",
            notify_ops_on=["ACK_SLA_BREACH"],
        )
        result = evaluate(p)
        assert result.actions == []

    def test_empty_ack_due_no_trigger(self):
        p = _payload(ack_due="", notify_ops_on=["ACK_SLA_BREACH"])
        result = evaluate(p)
        assert result.actions == []

    def test_already_acked_no_ack_trigger(self):
        p = _payload(
            ack_state="Acked",
            now_utc="2026-03-12T10:00:00Z",
            ack_due="2026-03-12T07:05:00Z",
            notify_ops_on=["ACK_SLA_BREACH"],
        )
        result = evaluate(p)
        assert not any(a.reason == "ACK_SLA_BREACH" for a in result.actions)


# ---------------------------------------------------------------------------
# Group D — Audit Event Shape
# ---------------------------------------------------------------------------

class TestAuditEventShape:

    def test_audit_event_has_required_keys(self):
        result = evaluate(_payload())
        ae = result.audit_event
        for key in ("event_type", "request_id", "now_utc", "task", "triggers_fired", "actions_emitted"):
            assert key in ae, f"Missing key: {key}"

    def test_triggers_and_actions_aligned(self):
        p = _payload(
            now_utc="2026-03-12T10:00:00Z",
            ack_due="2026-03-12T07:05:00Z",
            notify_ops_on=["ACK_SLA_BREACH"],
        )
        result = evaluate(p)
        assert len(result.audit_event["actions_emitted"]) == len(result.actions)

    def test_side_effects_always_empty(self):
        result = evaluate(_payload())
        assert result.side_effects == []

    def test_critical_ack_sla_constant(self):
        """CRITICAL_ACK_SLA_MINUTES must be exactly 5 (skill invariant)."""
        assert CRITICAL_ACK_SLA_MINUTES == 5


# ---------------------------------------------------------------------------
# Group E — Full SLA→Dispatch Chain
# ---------------------------------------------------------------------------

class TestFullSLADispatchChain:

    @patch("channels.sla_dispatch_bridge.write_delivery_log")
    def test_evaluate_then_dispatch_single_worker(self, mock_log):
        """evaluate() → dispatch_escalations() with 1 resolved user."""
        # Evaluate SLA
        p = _payload(
            now_utc="2026-03-12T10:00:00Z",
            ack_due="2026-03-12T07:05:00Z",
            notify_ops_on=["ACK_SLA_BREACH"],
        )
        result = evaluate(p)
        assert result.actions  # at least one action

        # Mock DB for dispatch
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.in_.return_value.execute.return_value.data = [
            {"user_id": "worker-001"},
        ]
        db.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
            {"channel_type": "line", "channel_id": "U_line_001"}
        ]

        from channels.notification_dispatcher import ChannelAttempt, CHANNEL_LINE
        def line_adapter(ch_id, msg):
            return ChannelAttempt(channel_type=CHANNEL_LINE, channel_id=ch_id, success=True)

        bridge_results = dispatch_escalations(
            db, "tenant-1", result.actions,
            adapters={"line": line_adapter},
        )

        assert len(bridge_results) == 1
        assert bridge_results[0].action_type == "notify_ops"
        assert bridge_results[0].results[0].sent is True

    @patch("channels.sla_dispatch_bridge.write_delivery_log")
    def test_evaluate_no_users_dispatch_graceful(self, mock_log):
        """Even with zero resolved users, chain completes without error."""
        p = _payload(
            now_utc="2026-03-12T10:00:00Z",
            ack_due="2026-03-12T07:05:00Z",
            notify_ops_on=["ACK_SLA_BREACH"],
        )
        result = evaluate(p)

        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.in_.return_value.execute.return_value.data = []

        bridge_results = dispatch_escalations(db, "tenant-1", result.actions)

        assert bridge_results[0].dispatched_to == []
        assert bridge_results[0].results == []
