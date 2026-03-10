"""
Phase 212 — SMS Escalation Channel Contract Tests

Tests for:
    sms_escalation.py   — Pure module: should_escalate, build_sms_message,
                           format_sms_text, is_priority_eligible, dispatch_dry_run
    sms_router.py       — GET /sms/webhook, POST /sms/webhook
"""
from __future__ import annotations

import types
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient


# ===========================================================================
# Pure module tests — sms_escalation.py
# ===========================================================================

from channels.sms_escalation import (
    should_escalate,
    build_sms_message,
    format_sms_text,
    is_priority_eligible,
    dispatch_dry_run,
    SMSEscalationRequest,
    SMS_MAX_LENGTH,
)
from tasks.sla_engine import EscalationResult, EscalationAction


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _action(reason: str) -> EscalationAction:
    return EscalationAction(
        action_type="notify_ops",
        target="ops",
        reason=reason,
        task_id="task-001",
        property_id="prop-001",
        request_id="req-001",
    )


def _make_ack_breach() -> EscalationResult:
    return EscalationResult(
        actions=[_action("ACK_SLA_BREACH")],
        audit_event={},
    )


def _make_completion_breach() -> EscalationResult:
    return EscalationResult(
        actions=[_action("COMPLETION_SLA_BREACH")],
        audit_event={},
    )


def _make_empty_result() -> EscalationResult:
    return EscalationResult(actions=[], audit_event={})


def _make_critical_task() -> dict:
    return {
        "task_id": "task-uuid-0001",
        "property_id": "prop-001",
        "worker_role": "cleaner",
        "priority": "CRITICAL",
        "urgency": "critical",
        "title": "Emergency Cleaning",
        "kind": "CLEANING",
        "due_date": "2026-03-11",
    }


# ---------------------------------------------------------------------------
# should_escalate
# ---------------------------------------------------------------------------

class TestShouldEscalate:

    def test_triggers_on_ack_sla_breach(self):
        assert should_escalate(_make_ack_breach()) is True

    def test_does_not_trigger_on_completion_breach(self):
        assert should_escalate(_make_completion_breach()) is False

    def test_does_not_trigger_on_empty_actions(self):
        assert should_escalate(_make_empty_result()) is False

    def test_triggers_when_mixed_reasons_include_ack(self):
        result = EscalationResult(
            actions=[_action("COMPLETION_SLA_BREACH"), _action("ACK_SLA_BREACH")],
            audit_event={},
        )
        assert should_escalate(result) is True


# ---------------------------------------------------------------------------
# build_sms_message
# ---------------------------------------------------------------------------

class TestBuildSmsMessage:

    def test_builds_request(self):
        task = _make_critical_task()
        req = build_sms_message(task, to_number="+66812345678")

        assert isinstance(req, SMSEscalationRequest)
        assert req.task_id == "task-uuid-0001"
        assert req.property_id == "prop-001"
        assert req.worker_role == "cleaner"
        assert req.to_number == "+66812345678"
        assert req.priority == "CRITICAL"
        assert req.trigger == "ACK_SLA_BREACH"

    def test_body_is_string(self):
        req = build_sms_message(_make_critical_task(), "+66812345678")
        assert isinstance(req.body, str)
        assert len(req.body) > 0

    def test_handles_empty_task_row(self):
        req = build_sms_message({}, "+66800000000")
        assert req.task_id == ""
        assert req.property_id == ""
        assert isinstance(req.body, str)

    def test_immutable(self):
        req = build_sms_message(_make_critical_task(), "+66812345678")
        with pytest.raises((AttributeError, TypeError)):
            req.task_id = "mutated"


# ---------------------------------------------------------------------------
# format_sms_text
# ---------------------------------------------------------------------------

class TestFormatSmsText:

    def test_contains_title(self):
        task = _make_critical_task()
        text = format_sms_text(task)
        assert "Emergency Cleaning" in text

    def test_contains_property_id(self):
        task = _make_critical_task()
        text = format_sms_text(task)
        assert "prop-001" in text

    def test_contains_urgency(self):
        task = _make_critical_task()
        text = format_sms_text(task)
        assert "CRITICAL" in text

    def test_contains_ack_instruction(self):
        text = format_sms_text(_make_critical_task())
        assert "ACK" in text

    def test_plain_text_no_markdown(self):
        text = format_sms_text(_make_critical_task())
        # SMS should not contain Telegram-style *bold* markers
        assert "*" not in text

    def test_within_sms_max_length(self):
        task = _make_critical_task()
        text = format_sms_text(task)
        assert len(text) <= SMS_MAX_LENGTH

    def test_long_title_still_within_limit(self):
        task = _make_critical_task()
        task["title"] = "X" * 200  # very long title
        text = format_sms_text(task)
        assert len(text) <= SMS_MAX_LENGTH

    def test_empty_task_row(self):
        text = format_sms_text({})
        assert isinstance(text, str)
        assert len(text) > 0


# ---------------------------------------------------------------------------
# is_priority_eligible
# ---------------------------------------------------------------------------

class TestIsPriorityEligible:

    def test_critical_eligible(self):
        assert is_priority_eligible({"priority": "CRITICAL"}) is True

    def test_high_eligible(self):
        assert is_priority_eligible({"priority": "HIGH"}) is True

    def test_low_not_eligible(self):
        assert is_priority_eligible({"priority": "LOW"}) is False

    def test_medium_not_eligible(self):
        assert is_priority_eligible({"priority": "MEDIUM"}) is False

    def test_urgency_critical_eligible(self):
        assert is_priority_eligible({"urgency": "critical"}) is True

    def test_empty_not_eligible(self):
        assert is_priority_eligible({}) is False


# ---------------------------------------------------------------------------
# dispatch_dry_run
# ---------------------------------------------------------------------------

class TestDispatchDryRun:

    def test_returns_not_sent(self):
        req = build_sms_message(_make_critical_task(), "+66812345678")
        result = dispatch_dry_run(req)
        assert result.sent is False
        assert result.dry_run is True
        assert result.task_id == "task-uuid-0001"
        assert result.error is None


# ===========================================================================
# Router tests — sms_router.py
# ===========================================================================

def _make_client():
    import main
    return TestClient(main.app)


class TestSmsWebhookGet:
    """GET /sms/webhook — challenge/health check."""

    def test_returns_ok_when_token_set(self):
        with patch.dict("os.environ", {"IHOUSE_SMS_TOKEN": "test-token-123"}):
            client = _make_client()
            resp = client.get("/sms/webhook")
        assert resp.status_code == 200
        assert resp.text == "ok"

    def test_returns_not_configured_when_no_token(self):
        env = {k: v for k, v in __import__("os").environ.items() if k != "IHOUSE_SMS_TOKEN"}
        with patch.dict("os.environ", env, clear=True):
            client = _make_client()
            resp = client.get("/sms/webhook")
        assert resp.status_code == 200
        assert "not_configured" in resp.text


class TestSmsWebhookPost:
    """POST /sms/webhook — inbound SMS ACK."""

    def test_ack_extracts_task_id(self):
        env = {k: v for k, v in __import__("os").environ.items() if k != "IHOUSE_SMS_TOKEN"}
        with patch.dict("os.environ", env, clear=True):
            client = _make_client()
            resp = client.post(
                "/sms/webhook",
                data={"Body": "ACK task-abc-123", "From": "+66812345678"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["processed"] is True

    def test_non_ack_body_not_processed(self):
        env = {k: v for k, v in __import__("os").environ.items() if k != "IHOUSE_SMS_TOKEN"}
        with patch.dict("os.environ", env, clear=True):
            client = _make_client()
            resp = client.post(
                "/sms/webhook",
                data={"Body": "Hello there!", "From": "+66812345678"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["processed"] is False

    def test_empty_body_not_processed(self):
        env = {k: v for k, v in __import__("os").environ.items() if k != "IHOUSE_SMS_TOKEN"}
        with patch.dict("os.environ", env, clear=True):
            client = _make_client()
            resp = client.post("/sms/webhook", data={"Body": "", "From": ""})
        assert resp.status_code == 200
        body = resp.json()
        assert body["processed"] is False

    def test_case_insensitive_ack(self):
        env = {k: v for k, v in __import__("os").environ.items() if k != "IHOUSE_SMS_TOKEN"}
        with patch.dict("os.environ", env, clear=True):
            client = _make_client()
            resp = client.post(
                "/sms/webhook",
                data={"Body": "ack task-xyz-456", "From": "+66812345678"},
            )
        assert resp.status_code == 200
        assert resp.json()["processed"] is True

    def test_requires_signature_when_token_set(self):
        with patch.dict("os.environ", {"IHOUSE_SMS_TOKEN": "secret-token"}):
            client = _make_client()
            # No X-Twilio-Signature header → 403
            resp = client.post(
                "/sms/webhook",
                data={"Body": "ACK task-123", "From": "+1234567890"},
            )
        assert resp.status_code == 403

    def test_accepts_when_token_absent_no_signature_needed(self):
        """When no token is configured, signature check is skipped (dev mode)."""
        env = {k: v for k, v in __import__("os").environ.items() if k != "IHOUSE_SMS_TOKEN"}
        with patch.dict("os.environ", env, clear=True):
            client = _make_client()
            resp = client.post(
                "/sms/webhook",
                data={"Body": "ACK task-123", "From": "+66800000000"},
                # No X-Twilio-Signature header
            )
        assert resp.status_code == 200
