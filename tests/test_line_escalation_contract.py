"""
Phase 124 — LINE Escalation (Pure Module) — Contract Tests

Tests for channels/line_escalation.py (pure module — no network, no DB).

Groups:
    A — should_escalate() logic
    B — build_line_message() shape
    C — format_line_text() content
    D — is_priority_eligible() helper
    E — LineEscalationRequest fields
    F — Pure module invariants (no side effects, no external calls)
"""
from __future__ import annotations

import pytest

from channels.line_escalation import (
    LineEscalationRequest,
    LineDispatchResult,
    build_line_message,
    format_line_text,
    is_priority_eligible,
    should_escalate,
)
from tasks.sla_engine import EscalationAction, EscalationResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _action(reason: str = "ACK_SLA_BREACH") -> EscalationAction:
    return EscalationAction(
        action_type="notify_ops",
        target="ops",
        reason=reason,
        task_id="task-001",
        property_id="prop-1",
        request_id="req-001",
    )


def _result(actions=None, triggers=None) -> EscalationResult:
    actions = actions or []
    return EscalationResult(
        actions=actions,
        audit_event={"triggers_fired": triggers or []},
        side_effects=[],
    )


def _task_row(
    task_id: str = "task-001",
    worker_role: str = "CLEANER",
    priority: str = "HIGH",
    urgency: str = "urgent",
    title: str = "Clean property",
    kind: str = "CLEANING",
    property_id: str = "prop-1",
    due_date: str = "2026-03-10",
) -> dict:
    return {
        "task_id": task_id,
        "worker_role": worker_role,
        "priority": priority,
        "urgency": urgency,
        "title": title,
        "kind": kind,
        "property_id": property_id,
        "due_date": due_date,
    }


# ===========================================================================
# Group A — should_escalate()
# ===========================================================================

class TestGroupA_ShouldEscalate:

    def test_a1_ack_breach_action_returns_true(self) -> None:
        """A1: ACK_SLA_BREACH action → should_escalate = True."""
        result = _result(actions=[_action("ACK_SLA_BREACH")])
        assert should_escalate(result) is True

    def test_a2_no_actions_returns_false(self) -> None:
        """A2: No actions → should_escalate = False."""
        result = _result(actions=[])
        assert should_escalate(result) is False

    def test_a3_completion_breach_only_returns_false(self) -> None:
        """A3: COMPLETION_SLA_BREACH only → should_escalate = False."""
        result = _result(actions=[_action("COMPLETION_SLA_BREACH")])
        assert should_escalate(result) is False

    def test_a4_mixed_actions_ack_present_returns_true(self) -> None:
        """A4: Both ACK + COMPLETION breaches → True (ACK is present)."""
        result = _result(actions=[
            _action("COMPLETION_SLA_BREACH"),
            _action("ACK_SLA_BREACH"),
        ])
        assert should_escalate(result) is True

    def test_a5_unknown_reason_returns_false(self) -> None:
        """A5: Unknown reason → should_escalate = False."""
        result = _result(actions=[_action("SOME_OTHER_REASON")])
        assert should_escalate(result) is False

    def test_a6_side_effects_empty_does_not_affect_result(self) -> None:
        """A6: side_effects=[] (correct) does not affect result."""
        result = _result(actions=[_action("ACK_SLA_BREACH")])
        assert result.side_effects == []
        assert should_escalate(result) is True


# ===========================================================================
# Group B — build_line_message()
# ===========================================================================

class TestGroupB_BuildLineMessage:

    def test_b1_returns_line_escalation_request(self) -> None:
        """B1: Returns a LineEscalationRequest instance."""
        req = build_line_message(_task_row())
        assert isinstance(req, LineEscalationRequest)

    def test_b2_task_id_matches(self) -> None:
        """B2: task_id in result matches input."""
        req = build_line_message(_task_row(task_id="abc-999"))
        assert req.task_id == "abc-999"

    def test_b3_property_id_matches(self) -> None:
        """B3: property_id in result matches input."""
        req = build_line_message(_task_row(property_id="villa-5"))
        assert req.property_id == "villa-5"

    def test_b4_worker_role_matches(self) -> None:
        """B4: worker_role in result matches input."""
        req = build_line_message(_task_row(worker_role="INSPECTOR"))
        assert req.worker_role == "INSPECTOR"

    def test_b5_trigger_is_ack_sla_breach(self) -> None:
        """B5: trigger is always ACK_SLA_BREACH."""
        req = build_line_message(_task_row())
        assert req.trigger == "ACK_SLA_BREACH"

    def test_b6_message_text_is_non_empty_string(self) -> None:
        """B6: message_text is a non-empty string."""
        req = build_line_message(_task_row())
        assert isinstance(req.message_text, str)
        assert len(req.message_text) > 0

    def test_b7_priority_matches(self) -> None:
        """B7: priority in result matches input."""
        req = build_line_message(_task_row(priority="CRITICAL"))
        assert req.priority == "CRITICAL"

    def test_b8_missing_fields_produce_empty_strings(self) -> None:
        """B8: Missing fields produce empty strings (no exceptions)."""
        req = build_line_message({})
        assert req.task_id == ""
        assert req.property_id == ""


# ===========================================================================
# Group C — format_line_text()
# ===========================================================================

class TestGroupC_FormatLineText:

    def test_c1_contains_task_id(self) -> None:
        """C1: format_line_text includes task_id."""
        text = format_line_text(_task_row(task_id="t-abc"))
        assert "t-abc" in text

    def test_c2_contains_property_id(self) -> None:
        """C2: format_line_text includes property_id."""
        text = format_line_text(_task_row(property_id="villa-7"))
        assert "villa-7" in text

    def test_c3_contains_due_date(self) -> None:
        """C3: format_line_text includes due_date."""
        text = format_line_text(_task_row(due_date="2026-04-01"))
        assert "2026-04-01" in text

    def test_c4_contains_title(self) -> None:
        """C4: format_line_text includes title."""
        text = format_line_text(_task_row(title="Prepare suite 401"))
        assert "Prepare suite 401" in text

    def test_c5_contains_ihouse_branding(self) -> None:
        """C5: format_line_text contains 'iHouse' branding."""
        text = format_line_text(_task_row())
        assert "iHouse" in text

    def test_c6_contains_acknowledge_cta(self) -> None:
        """C6: format_line_text asks worker to acknowledge."""
        text = format_line_text(_task_row())
        assert "acknowledge" in text.lower()

    def test_c7_urgency_displayed(self) -> None:
        """C7: urgency label appears in text."""
        text = format_line_text(_task_row(urgency="critical"))
        assert "CRITICAL" in text

    def test_c8_returns_string(self) -> None:
        """C8: returns a str."""
        text = format_line_text(_task_row())
        assert isinstance(text, str)


# ===========================================================================
# Group D — is_priority_eligible()
# ===========================================================================

class TestGroupD_PriorityEligible:

    def test_d1_high_priority_eligible(self) -> None:
        """D1: HIGH priority → eligible."""
        assert is_priority_eligible({"priority": "HIGH"}) is True

    def test_d2_critical_priority_eligible(self) -> None:
        """D2: CRITICAL priority → eligible."""
        assert is_priority_eligible({"priority": "CRITICAL"}) is True

    def test_d3_low_priority_not_eligible(self) -> None:
        """D3: LOW priority → not eligible."""
        assert is_priority_eligible({"priority": "LOW"}) is False

    def test_d4_medium_priority_not_eligible(self) -> None:
        """D4: MEDIUM priority → not eligible."""
        assert is_priority_eligible({"priority": "MEDIUM"}) is False

    def test_d5_urgent_urgency_eligible(self) -> None:
        """D5: urgency=urgent → eligible."""
        assert is_priority_eligible({"urgency": "urgent"}) is True

    def test_d6_critical_urgency_eligible(self) -> None:
        """D6: urgency=critical → eligible."""
        assert is_priority_eligible({"urgency": "critical"}) is True

    def test_d7_no_priority_not_eligible(self) -> None:
        """D7: empty task → not eligible."""
        assert is_priority_eligible({}) is False


# ===========================================================================
# Group E — LineEscalationRequest is immutable
# ===========================================================================

class TestGroupE_RequestImmutable:

    def test_e1_frozen_dataclass(self) -> None:
        """E1: LineEscalationRequest is frozen — cannot mutate."""
        req = build_line_message(_task_row())
        with pytest.raises((AttributeError, TypeError)):
            req.task_id = "hacked"  # type: ignore[misc]

    def test_e2_dispatch_result_sent_false(self) -> None:
        """E2: LineDispatchResult can be created with sent=False."""
        result = LineDispatchResult(sent=False, task_id="t1", error="timeout")
        assert result.sent is False
        assert result.error == "timeout"

    def test_e3_dispatch_result_sent_true(self) -> None:
        """E3: LineDispatchResult can be created with sent=True."""
        result = LineDispatchResult(sent=True, task_id="t1")
        assert result.sent is True
        assert result.error is None


# ===========================================================================
# Group F — Pure module invariants
# ===========================================================================

class TestGroupF_PureInvariants:

    def test_f1_build_line_message_has_no_side_effects(self) -> None:
        """F1: build_line_message does not mutate input dict."""
        row = _task_row()
        original = dict(row)
        build_line_message(row)
        assert row == original

    def test_f2_format_line_text_is_deterministic(self) -> None:
        """F2: format_line_text returns same output for same input."""
        row = _task_row()
        assert format_line_text(row) == format_line_text(row)

    def test_f3_should_escalate_is_deterministic(self) -> None:
        """F3: should_escalate returns same output for same input."""
        result = _result(actions=[_action("ACK_SLA_BREACH")])
        assert should_escalate(result) == should_escalate(result)

    def test_f4_module_has_no_global_state(self) -> None:
        """F4: Multiple calls with different inputs give independent results."""
        r1 = _result(actions=[_action("ACK_SLA_BREACH")])
        r2 = _result(actions=[])
        assert should_escalate(r1) is True
        assert should_escalate(r2) is False
        # Run again in same order — must be same
        assert should_escalate(r1) is True
        assert should_escalate(r2) is False
