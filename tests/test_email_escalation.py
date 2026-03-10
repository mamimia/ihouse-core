"""
Phase 213 — Email Notification Channel Contract Tests

Tests for:
    email_escalation.py  — Pure module: should_escalate, build_email_message,
                            format_email_subject, format_email_body,
                            is_priority_eligible, dispatch_dry_run
    email_router.py      — GET /email/webhook, GET /email/ack
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


# ===========================================================================
# Pure module tests — email_escalation.py
# ===========================================================================

from channels.email_escalation import (
    should_escalate,
    build_email_message,
    format_email_subject,
    format_email_body,
    is_priority_eligible,
    dispatch_dry_run,
    EmailEscalationRequest,
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
        task_id="task-email-001",
        property_id="prop-email",
        request_id="req-email-001",
    )


def _make_ack_breach() -> EscalationResult:
    return EscalationResult(actions=[_action("ACK_SLA_BREACH")], audit_event={})


def _make_completion_breach() -> EscalationResult:
    return EscalationResult(actions=[_action("COMPLETION_SLA_BREACH")], audit_event={})


def _make_empty_result() -> EscalationResult:
    return EscalationResult(actions=[], audit_event={})


def _make_critical_task() -> dict:
    return {
        "task_id": "task-email-001",
        "property_id": "prop-villa-01",
        "worker_role": "cleaner",
        "priority": "CRITICAL",
        "urgency": "critical",
        "title": "Emergency Turnover Cleaning",
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
# build_email_message
# ---------------------------------------------------------------------------

class TestBuildEmailMessage:

    def test_builds_request(self):
        task = _make_critical_task()
        req = build_email_message(task, to_address="worker@example.com")

        assert isinstance(req, EmailEscalationRequest)
        assert req.task_id == "task-email-001"
        assert req.property_id == "prop-villa-01"
        assert req.worker_role == "cleaner"
        assert req.to_address == "worker@example.com"
        assert req.priority == "CRITICAL"
        assert req.trigger == "ACK_SLA_BREACH"

    def test_subject_is_string(self):
        req = build_email_message(_make_critical_task(), "worker@example.com")
        assert isinstance(req.subject, str)
        assert len(req.subject) > 0

    def test_body_is_string(self):
        req = build_email_message(_make_critical_task(), "worker@example.com")
        assert isinstance(req.body, str)
        assert len(req.body) > 0

    def test_handles_empty_task_row(self):
        req = build_email_message({}, "x@x.com")
        assert req.task_id == ""
        assert isinstance(req.body, str)

    def test_immutable(self):
        req = build_email_message(_make_critical_task(), "a@b.com")
        with pytest.raises((AttributeError, TypeError)):
            req.task_id = "mutated"


# ---------------------------------------------------------------------------
# format_email_subject
# ---------------------------------------------------------------------------

class TestFormatEmailSubject:

    def test_contains_title(self):
        subject = format_email_subject(_make_critical_task())
        assert "Emergency Turnover Cleaning" in subject

    def test_urgent_prefix_for_critical(self):
        subject = format_email_subject(_make_critical_task())
        assert "[URGENT]" in subject

    def test_no_urgent_prefix_for_low(self):
        task = _make_critical_task()
        task["priority"] = "LOW"
        subject = format_email_subject(task)
        assert "[URGENT]" not in subject

    def test_contains_property_id(self):
        subject = format_email_subject(_make_critical_task())
        assert "prop-villa-01" in subject

    def test_empty_task(self):
        subject = format_email_subject({})
        assert isinstance(subject, str)
        assert len(subject) > 0


# ---------------------------------------------------------------------------
# format_email_body
# ---------------------------------------------------------------------------

class TestFormatEmailBody:

    def test_contains_title(self):
        body = format_email_body(_make_critical_task())
        assert "Emergency Turnover Cleaning" in body

    def test_contains_task_id(self):
        body = format_email_body(_make_critical_task())
        assert "task-email-001" in body

    def test_contains_property(self):
        body = format_email_body(_make_critical_task())
        assert "prop-villa-01" in body

    def test_contains_urgency(self):
        body = format_email_body(_make_critical_task())
        assert "CRITICAL" in body

    def test_contains_ack_instruction(self):
        body = format_email_body(_make_critical_task())
        assert "acknowledge" in body.lower()

    def test_contains_no_reply_notice(self):
        body = format_email_body(_make_critical_task())
        assert "Do not reply" in body

    def test_plain_text_no_html(self):
        body = format_email_body(_make_critical_task())
        assert "<" not in body and ">" not in body

    def test_empty_task(self):
        body = format_email_body({})
        assert isinstance(body, str)
        assert len(body) > 0


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
        req = build_email_message(_make_critical_task(), "owner@example.com")
        result = dispatch_dry_run(req)
        assert result.sent is False
        assert result.dry_run is True
        assert result.task_id == "task-email-001"
        assert result.error is None


# ===========================================================================
# Router tests — email_router.py
# ===========================================================================

def _make_client():
    import main
    return TestClient(main.app)


class TestEmailWebhookGet:
    """GET /email/webhook — health check."""

    def test_returns_ok_when_token_set(self):
        with patch.dict("os.environ", {"IHOUSE_EMAIL_TOKEN": "smtp-secret"}):
            client = _make_client()
            resp = client.get("/email/webhook")
        assert resp.status_code == 200
        assert resp.text == "ok"

    def test_returns_not_configured_when_no_token(self):
        env = {k: v for k, v in __import__("os").environ.items() if k != "IHOUSE_EMAIL_TOKEN"}
        with patch.dict("os.environ", env, clear=True):
            client = _make_client()
            resp = client.get("/email/webhook")
        assert resp.status_code == 200
        assert "not_configured" in resp.text


class TestEmailAckGet:
    """GET /email/ack — one-click task acknowledgement."""

    def test_missing_params_returns_error_html(self):
        client = _make_client()
        resp = client.get("/email/ack")
        assert resp.status_code == 200
        assert "Error" in resp.text or "Missing" in resp.text

    def test_invalid_token_returns_error_html(self):
        client = _make_client()
        resp = client.get(
            "/email/ack",
            params={"task_id": "task-abc-12345678", "token": "WRONGTOKEN"},
        )
        assert resp.status_code == 200
        assert "Invalid" in resp.text or "Error" in resp.text

    def test_valid_token_prefix_returns_html(self):
        """Valid token (starts with task_id[:8]) — no DB available → returns already_acked page."""
        task_id = "task-abc-12345678"
        token = task_id[:8] + "-extra"  # starts with correct prefix
        client = _make_client()
        resp = client.get(
            "/email/ack",
            params={"task_id": task_id, "token": token},
        )
        assert resp.status_code == 200
        # Should return a valid HTML page (success or already_acked without DB)
        assert "<!DOCTYPE html>" in resp.text

    def test_ack_page_is_html(self):
        task_id = "task-xyz-99887766"
        token = task_id[:8] + "-abc"
        client = _make_client()
        resp = client.get(
            "/email/ack",
            params={"task_id": task_id, "token": token},
        )
        assert "content-type" in resp.headers
        assert "text/html" in resp.headers["content-type"]
