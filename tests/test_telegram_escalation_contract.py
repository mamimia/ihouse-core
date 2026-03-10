"""
Phase 203 — Telegram Escalation Channel — Contract Tests

Tests for channels/telegram_escalation.py (pure module).

Groups:
    A — should_escalate: trigger conditions
    B — build_telegram_message: payload construction
    C — format_telegram_text: Markdown formatting and edge cases
    D — is_priority_eligible: priority / urgency filtering
    E — Dispatcher integration: Telegram adapter builds correct payload
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("channels.telegram_escalation")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _task_row(
    task_id: str = "task-203",
    property_id: str = "prop-1",
    worker_role: str = "CLEANER",
    priority: str = "HIGH",
    urgency: str = "normal",
    title: str = "Clean room 101",
    kind: str = "CLEANING",
    due_date: str = "2026-03-11",
) -> dict:
    return {
        "task_id": task_id,
        "property_id": property_id,
        "worker_role": worker_role,
        "priority": priority,
        "urgency": urgency,
        "title": title,
        "kind": kind,
        "due_date": due_date,
    }


def _make_escalation_result(reasons: list[str]) -> "EscalationResult":
    from tasks.sla_engine import EscalationResult, EscalationAction
    actions = [
        EscalationAction(
            action_type="notify_ops",
            target="ops",
            reason=r,
            task_id="task-203",
            property_id="prop-1",
            request_id="req-001",
        )
        for r in reasons
    ]
    return EscalationResult(actions=actions, audit_event={})


# ===========================================================================
# Group A — should_escalate
# ===========================================================================

class TestGroupA_ShouldEscalate:

    def test_a1_ack_sla_breach_returns_true(self) -> None:
        """A1: ACK_SLA_BREACH action → should_escalate=True."""
        from channels.telegram_escalation import should_escalate
        result = _make_escalation_result(["ACK_SLA_BREACH"])
        assert should_escalate(result) is True

    def test_a2_completion_sla_breach_returns_false(self) -> None:
        """A2: COMPLETION_SLA_BREACH only → should_escalate=False."""
        from channels.telegram_escalation import should_escalate
        result = _make_escalation_result(["COMPLETION_SLA_BREACH"])
        assert should_escalate(result) is False

    def test_a3_empty_actions_returns_false(self) -> None:
        """A3: No actions → should_escalate=False."""
        from channels.telegram_escalation import should_escalate
        result = _make_escalation_result([])
        assert should_escalate(result) is False

    def test_a4_mixed_reasons_with_ack_returns_true(self) -> None:
        """A4: Mixed reasons including ACK_SLA_BREACH → True."""
        from channels.telegram_escalation import should_escalate
        result = _make_escalation_result(["COMPLETION_SLA_BREACH", "ACK_SLA_BREACH"])
        assert should_escalate(result) is True

    def test_a5_unknown_reason_returns_false(self) -> None:
        """A5: Unknown reason → False."""
        from channels.telegram_escalation import should_escalate
        result = _make_escalation_result(["SOME_OTHER_REASON"])
        assert should_escalate(result) is False


# ===========================================================================
# Group B — build_telegram_message
# ===========================================================================

class TestGroupB_BuildTelegramMessage:

    def test_b1_returns_telegram_escalation_request(self) -> None:
        """B1: Returns a TelegramEscalationRequest instance."""
        from channels.telegram_escalation import build_telegram_message, TelegramEscalationRequest
        req = build_telegram_message(_task_row(), chat_id="123456789")
        assert isinstance(req, TelegramEscalationRequest)

    def test_b2_task_id_matches(self) -> None:
        """B2: task_id field matches task_row."""
        from channels.telegram_escalation import build_telegram_message
        req = build_telegram_message(_task_row(task_id="task-abc"), chat_id="999")
        assert req.task_id == "task-abc"

    def test_b3_property_id_matches(self) -> None:
        """B3: property_id field matches task_row."""
        from channels.telegram_escalation import build_telegram_message
        req = build_telegram_message(_task_row(property_id="prop-XYZ"), chat_id="999")
        assert req.property_id == "prop-XYZ"

    def test_b4_chat_id_matches_argument(self) -> None:
        """B4: chat_id field matches the passed argument."""
        from channels.telegram_escalation import build_telegram_message
        req = build_telegram_message(_task_row(), chat_id="123456789")
        assert req.chat_id == "123456789"

    def test_b5_parse_mode_is_markdown(self) -> None:
        """B5: parse_mode is always 'Markdown'."""
        from channels.telegram_escalation import build_telegram_message
        req = build_telegram_message(_task_row(), chat_id="123")
        assert req.parse_mode == "Markdown"

    def test_b6_trigger_is_ack_sla_breach(self) -> None:
        """B6: trigger defaults to ACK_SLA_BREACH."""
        from channels.telegram_escalation import build_telegram_message
        req = build_telegram_message(_task_row(), chat_id="123")
        assert req.trigger == "ACK_SLA_BREACH"

    def test_b7_priority_matches(self) -> None:
        """B7: priority field matches task_row."""
        from channels.telegram_escalation import build_telegram_message
        req = build_telegram_message(_task_row(priority="CRITICAL"), chat_id="123")
        assert req.priority == "CRITICAL"

    def test_b8_text_is_non_empty(self) -> None:
        """B8: text field is a non-empty string."""
        from channels.telegram_escalation import build_telegram_message
        req = build_telegram_message(_task_row(), chat_id="123")
        assert isinstance(req.text, str) and len(req.text) > 0

    def test_b9_immutable(self) -> None:
        """B9: TelegramEscalationRequest is frozen (immutable)."""
        from channels.telegram_escalation import build_telegram_message
        req = build_telegram_message(_task_row(), chat_id="123")
        with pytest.raises((AttributeError, TypeError)):
            req.chat_id = "mutated"  # type: ignore[misc]


# ===========================================================================
# Group C — format_telegram_text
# ===========================================================================

class TestGroupC_FormatTelegramText:

    def test_c1_includes_title(self) -> None:
        """C1: Message includes the task title."""
        from channels.telegram_escalation import format_telegram_text
        text = format_telegram_text(_task_row(title="Clean room 101"))
        assert "Clean room 101" in text

    def test_c2_includes_property_id(self) -> None:
        """C2: Message includes property_id."""
        from channels.telegram_escalation import format_telegram_text
        text = format_telegram_text(_task_row(property_id="prop-beach-villa"))
        assert "prop-beach-villa" in text

    def test_c3_includes_due_date(self) -> None:
        """C3: Message includes due_date."""
        from channels.telegram_escalation import format_telegram_text
        text = format_telegram_text(_task_row(due_date="2026-03-11"))
        assert "2026-03-11" in text

    def test_c4_includes_urgency_uppercased(self) -> None:
        """C4: Urgency is present and uppercased."""
        from channels.telegram_escalation import format_telegram_text
        text = format_telegram_text(_task_row(urgency="critical"))
        assert "CRITICAL" in text

    def test_c5_includes_task_id(self) -> None:
        """C5: Task ID appears in the text."""
        from channels.telegram_escalation import format_telegram_text
        text = format_telegram_text(_task_row(task_id="task-203"))
        assert "task-203" in text

    def test_c6_has_markdown_bold_header(self) -> None:
        """C6: Text uses Markdown bold (*) for the header."""
        from channels.telegram_escalation import format_telegram_text
        text = format_telegram_text(_task_row())
        assert "*" in text  # bold markers present

    def test_c7_includes_acknowledgement_prompt(self) -> None:
        """C7: Text includes the acknowledgement call-to-action."""
        from channels.telegram_escalation import format_telegram_text
        text = format_telegram_text(_task_row())
        assert "acknowledge" in text.lower()

    def test_c8_empty_fields_handled_gracefully(self) -> None:
        """C8: Empty/missing optional fields → no KeyError, returns string."""
        from channels.telegram_escalation import format_telegram_text
        text = format_telegram_text({})
        assert isinstance(text, str) and len(text) > 0

    def test_c9_missing_due_date_omits_due_line(self) -> None:
        """C9: Missing due_date → 'Due:' line absent."""
        from channels.telegram_escalation import format_telegram_text
        row = {k: v for k, v in _task_row().items() if k != "due_date"}
        row["due_date"] = ""
        text = format_telegram_text(row)
        assert "Due:" not in text

    def test_c10_includes_escalation_header(self) -> None:
        """C10: Text includes the iHouse escalation header."""
        from channels.telegram_escalation import format_telegram_text
        text = format_telegram_text(_task_row())
        assert "iHouse" in text and "Escalation" in text


# ===========================================================================
# Group D — is_priority_eligible
# ===========================================================================

class TestGroupD_PriorityEligibility:

    def test_d1_high_priority_eligible(self) -> None:
        """D1: priority=HIGH → eligible."""
        from channels.telegram_escalation import is_priority_eligible
        assert is_priority_eligible(_task_row(priority="HIGH")) is True

    def test_d2_critical_priority_eligible(self) -> None:
        """D2: priority=CRITICAL → eligible."""
        from channels.telegram_escalation import is_priority_eligible
        assert is_priority_eligible(_task_row(priority="CRITICAL")) is True

    def test_d3_low_priority_not_eligible(self) -> None:
        """D3: priority=LOW → not eligible."""
        from channels.telegram_escalation import is_priority_eligible
        assert is_priority_eligible(_task_row(priority="LOW")) is False

    def test_d4_medium_priority_not_eligible(self) -> None:
        """D4: priority=MEDIUM → not eligible."""
        from channels.telegram_escalation import is_priority_eligible
        assert is_priority_eligible(_task_row(priority="MEDIUM")) is False

    def test_d5_critical_urgency_eligible(self) -> None:
        """D5: urgency=critical → eligible regardless of priority."""
        from channels.telegram_escalation import is_priority_eligible
        assert is_priority_eligible(_task_row(priority="LOW", urgency="critical")) is True

    def test_d6_urgent_urgency_eligible(self) -> None:
        """D6: urgency=urgent → eligible."""
        from channels.telegram_escalation import is_priority_eligible
        assert is_priority_eligible(_task_row(priority="MEDIUM", urgency="urgent")) is True

    def test_d7_empty_priority_not_eligible(self) -> None:
        """D7: empty priority and normal urgency → not eligible."""
        from channels.telegram_escalation import is_priority_eligible
        assert is_priority_eligible({}) is False


# ===========================================================================
# Group E — Dispatcher integration
# ===========================================================================

class TestGroupE_DispatcherIntegration:

    def test_e1_telegram_adapter_returns_channel_attempt(self) -> None:
        """E1: _default_telegram_adapter returns a ChannelAttempt with success=True."""
        from channels.notification_dispatcher import (
            _default_telegram_adapter,
            NotificationMessage,
            ChannelAttempt,
        )
        msg = NotificationMessage(title="Test Escalation", body="Please acknowledge task.")
        result = _default_telegram_adapter("123456789", msg)
        assert isinstance(result, ChannelAttempt)
        assert result.success is True
        assert result.channel_type == "telegram"
        assert result.channel_id == "123456789"

    def test_e2_telegram_adapter_channel_type_is_telegram(self) -> None:
        """E2: channel_type is exactly 'telegram'."""
        from channels.notification_dispatcher import _default_telegram_adapter, NotificationMessage
        msg = NotificationMessage(title="Alert", body="Body text")
        result = _default_telegram_adapter("chat-99", msg)
        assert result.channel_type == "telegram"

    def test_e3_dispatch_routes_to_telegram_adapter(self) -> None:
        """E3: dispatch_notification calls Telegram adapter when user has telegram channel."""
        from channels.notification_dispatcher import (
            dispatch_notification, NotificationMessage, CHANNEL_TELEGRAM,
        )

        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"channel_type": "telegram", "channel_id": "987654321"}]
        )
        mock_adapter = MagicMock()
        from channels.notification_dispatcher import ChannelAttempt
        mock_adapter.return_value = ChannelAttempt(
            channel_type="telegram", channel_id="987654321", success=True
        )

        msg = NotificationMessage(title="Task!", body="Acknowledge now.")
        result = dispatch_notification(
            db=mock_db,
            tenant_id="tenant_test",
            user_id="user-001",
            message=msg,
            adapters={CHANNEL_TELEGRAM: mock_adapter},
        )
        assert result.sent is True
        assert mock_adapter.called
