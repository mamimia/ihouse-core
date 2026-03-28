"""
Phase 196 — WhatsApp Escalation Channel Contract Tests

Groups A–F:
    A — should_escalate(): ACK_SLA_BREACH / COMPLETION_SLA_BREACH / empty
    B — build_whatsapp_message(): field mapping and frozen dataclass
    C — format_whatsapp_text(): text content and structure
    D — is_priority_eligible(): HIGH/CRITICAL vs LOW/MEDIUM
    E — dry-run mode: no token → sent=False, no exception
    F — verify_whatsapp_signature(): valid, invalid, missing, no-secret
    G — whatsapp_router GET (challenge) and POST (sig check, task extraction)
    H — sla_dispatch_bridge: WhatsApp second-channel logic, BridgeResult fields
"""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import List, Optional
from unittest.mock import MagicMock, patch

import pytest

from channels.whatsapp_escalation import (
    WhatsAppDispatchResult,
    WhatsAppEscalationRequest,
    build_whatsapp_message,
    dispatch_dry_run,
    format_whatsapp_text,
    is_priority_eligible,
    should_escalate,
    verify_whatsapp_signature,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@dataclass
class _FakeAction:
    reason: str
    task_id: str = "task-001"
    property_id: str = "prop-001"
    action_type: str = "notify_ops"
    target: str = "ops"
    request_id: str = "req-001"


@dataclass
class _FakeResult:
    actions: List[_FakeAction]


BASE_TASK = {
    "task_id": "task-abc-123",
    "property_id": "prop-42",
    "worker_role": "housekeeper",
    "priority": "HIGH",
    "urgency": "urgent",
    "title": "Checkout cleaning required",
    "kind": "CHECKOUT_CLEAN",
    "due_date": "2026-03-11",
}


# ---------------------------------------------------------------------------
# Group A — should_escalate()
# ---------------------------------------------------------------------------

class TestGroupA_ShouldEscalate:

    def test_a1_ack_sla_breach_triggers(self):
        result = _FakeResult(actions=[_FakeAction(reason="ACK_SLA_BREACH")])
        assert should_escalate(result) is True

    def test_a2_completion_sla_breach_does_not_trigger(self):
        result = _FakeResult(actions=[_FakeAction(reason="COMPLETION_SLA_BREACH")])
        assert should_escalate(result) is False

    def test_a3_empty_actions_returns_false(self):
        result = _FakeResult(actions=[])
        assert should_escalate(result) is False

    def test_a4_multiple_actions_one_ack(self):
        result = _FakeResult(actions=[
            _FakeAction(reason="COMPLETION_SLA_BREACH"),
            _FakeAction(reason="ACK_SLA_BREACH"),
        ])
        assert should_escalate(result) is True

    def test_a5_unknown_reason_does_not_trigger(self):
        result = _FakeResult(actions=[_FakeAction(reason="UNKNOWN_REASON")])
        assert should_escalate(result) is False

    def test_a6_multiple_ack_breaches_triggers(self):
        result = _FakeResult(actions=[
            _FakeAction(reason="ACK_SLA_BREACH"),
            _FakeAction(reason="ACK_SLA_BREACH"),
        ])
        assert should_escalate(result) is True


# ---------------------------------------------------------------------------
# Group B — build_whatsapp_message()
# ---------------------------------------------------------------------------

class TestGroupB_BuildWhatsAppMessage:

    def test_b1_returns_frozen_dataclass(self):
        req = build_whatsapp_message(BASE_TASK)
        assert isinstance(req, WhatsAppEscalationRequest)

    def test_b2_task_id_preserved(self):
        req = build_whatsapp_message(BASE_TASK)
        assert req.task_id == "task-abc-123"

    def test_b3_property_id_preserved(self):
        req = build_whatsapp_message(BASE_TASK)
        assert req.property_id == "prop-42"

    def test_b4_worker_role_preserved(self):
        req = build_whatsapp_message(BASE_TASK)
        assert req.worker_role == "housekeeper"

    def test_b5_priority_preserved(self):
        req = build_whatsapp_message(BASE_TASK)
        assert req.priority == "HIGH"

    def test_b6_trigger_default(self):
        req = build_whatsapp_message(BASE_TASK)
        assert req.trigger == "ACK_SLA_BREACH"

    def test_b7_message_text_populated(self):
        req = build_whatsapp_message(BASE_TASK)
        assert req.message_text
        assert len(req.message_text) > 10

    def test_b8_frozen_immutable(self):
        req = build_whatsapp_message(BASE_TASK)
        with pytest.raises((AttributeError, TypeError)):
            req.task_id = "mutated"  # type: ignore[misc]

    def test_b9_empty_task_row_no_exception(self):
        req = build_whatsapp_message({})
        assert req.task_id == ""
        assert req.property_id == ""


# ---------------------------------------------------------------------------
# Group C — format_whatsapp_text()
# ---------------------------------------------------------------------------

class TestGroupC_FormatWhatsAppText:

    def test_c1_contains_title(self):
        text = format_whatsapp_text(BASE_TASK)
        assert "Checkout cleaning required" in text

    def test_c2_contains_property_id(self):
        text = format_whatsapp_text(BASE_TASK)
        assert "prop-42" in text

    def test_c3_contains_task_id(self):
        text = format_whatsapp_text(BASE_TASK)
        assert "task-abc-123" in text

    def test_c4_urgency_uppercased(self):
        text = format_whatsapp_text(BASE_TASK)
        assert "URGENT" in text

    def test_c5_contains_ihouse_branding(self):
        text = format_whatsapp_text(BASE_TASK)
        assert "iHouse" in text

    def test_c6_contains_acknowledge_call_to_action(self):
        text = format_whatsapp_text(BASE_TASK)
        assert "acknowledge" in text.lower()

    def test_c7_whatsapp_bold_formatting(self):
        text = format_whatsapp_text(BASE_TASK)
        # WhatsApp uses *bold* not <b>bold</b>
        assert "*" in text
        assert "<b>" not in text

    def test_c8_missing_optional_fields_no_exception(self):
        text = format_whatsapp_text({"task_id": "t-1"})
        assert "t-1" in text

    def test_c9_contains_due_date_when_present(self):
        text = format_whatsapp_text(BASE_TASK)
        assert "2026-03-11" in text


# ---------------------------------------------------------------------------
# Group D — is_priority_eligible()
# ---------------------------------------------------------------------------

class TestGroupD_PriorityEligibility:

    def test_d1_high_priority_eligible(self):
        assert is_priority_eligible({"priority": "HIGH"}) is True

    def test_d2_critical_priority_eligible(self):
        assert is_priority_eligible({"priority": "CRITICAL"}) is True

    def test_d3_urgent_urgency_eligible(self):
        assert is_priority_eligible({"priority": "LOW", "urgency": "urgent"}) is True

    def test_d4_low_priority_not_eligible(self):
        assert is_priority_eligible({"priority": "LOW"}) is False

    def test_d5_medium_priority_not_eligible(self):
        assert is_priority_eligible({"priority": "MEDIUM"}) is False

    def test_d6_empty_task_not_eligible(self):
        assert is_priority_eligible({}) is False

    def test_d7_critical_urgency_eligible(self):
        assert is_priority_eligible({"urgency": "critical"}) is True


# ---------------------------------------------------------------------------
# Group E — dry-run dispatch
# ---------------------------------------------------------------------------

class TestGroupE_DryRunDispatch:

    def test_e1_no_token_returns_dispatch_result(self):
        req = build_whatsapp_message(BASE_TASK)
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("IHOUSE_WHATSAPP_TOKEN", None)
            result = dispatch_dry_run(req)
        assert isinstance(result, WhatsAppDispatchResult)

    def test_e2_dry_run_flag_set(self):
        req = build_whatsapp_message(BASE_TASK)
        result = dispatch_dry_run(req)
        assert result.dry_run is True

    def test_e3_sent_is_false(self):
        req = build_whatsapp_message(BASE_TASK)
        result = dispatch_dry_run(req)
        assert result.sent is False

    def test_e4_no_exception_without_token(self):
        req = build_whatsapp_message(BASE_TASK)
        # Should never raise
        result = dispatch_dry_run(req)
        assert result is not None

    def test_e5_error_field_is_none_on_dry_run(self):
        req = build_whatsapp_message(BASE_TASK)
        result = dispatch_dry_run(req)
        assert result.error is None

    def test_e6_task_id_preserved_in_result(self):
        req = build_whatsapp_message(BASE_TASK)
        result = dispatch_dry_run(req)
        assert result.task_id == "task-abc-123"


# ---------------------------------------------------------------------------
# Group F — verify_whatsapp_signature()
# ---------------------------------------------------------------------------

class TestGroupF_SignatureVerification:

    _SECRET = "test-app-secret"

    def _make_sig(self, body: bytes) -> str:
        digest = hmac.new(
            self._SECRET.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()
        return f"sha256={digest}"

    def test_f1_valid_signature_returns_true(self):
        body = b'{"test": "data"}'
        sig = self._make_sig(body)
        with patch.dict("os.environ", {"IHOUSE_WHATSAPP_APP_SECRET": self._SECRET}):
            assert verify_whatsapp_signature(body, sig) is True

    def test_f2_invalid_signature_returns_false(self):
        body = b'{"test": "data"}'
        with patch.dict("os.environ", {"IHOUSE_WHATSAPP_APP_SECRET": self._SECRET}):
            assert verify_whatsapp_signature(body, "sha256=invalid") is False

    def test_f3_missing_signature_header_returns_false(self):
        body = b'{"test": "data"}'
        with patch.dict("os.environ", {"IHOUSE_WHATSAPP_APP_SECRET": self._SECRET}):
            assert verify_whatsapp_signature(body, "") is False

    def test_f4_no_app_secret_returns_false(self):
        body = b'{"test": "data"}'
        import os
        with patch.dict("os.environ", {}):
            os.environ.pop("IHOUSE_WHATSAPP_APP_SECRET", None)
            assert verify_whatsapp_signature(body, "sha256=anything") is False

    def test_f5_wrong_hash_prefix_returns_false(self):
        body = b'{"test": "data"}'
        sig = self._make_sig(body).replace("sha256=", "md5=")
        with patch.dict("os.environ", {"IHOUSE_WHATSAPP_APP_SECRET": self._SECRET}):
            assert verify_whatsapp_signature(body, sig) is False

    def test_f6_tampered_body_returns_false(self):
        body = b'{"test": "data"}'
        sig = self._make_sig(body)
        tampered = b'{"test": "tampered"}'
        with patch.dict("os.environ", {"IHOUSE_WHATSAPP_APP_SECRET": self._SECRET}):
            assert verify_whatsapp_signature(tampered, sig) is False


# ---------------------------------------------------------------------------
# Group G — whatsapp_router endpoints
# ---------------------------------------------------------------------------

class TestGroupG_WhatsAppRouter:

    def _make_app(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from api.whatsapp_router import router
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_g1_challenge_valid_token_returns_challenge(self):
        client = self._make_app()
        with patch.dict("os.environ", {"IHOUSE_WHATSAPP_VERIFY_TOKEN": "my-token"}):
            resp = client.get(
                "/whatsapp/webhook",
                params={
                    "hub.mode": "subscribe",
                    "hub.verify_token": "my-token",
                    "hub.challenge": "CHALLENGE_XYZ",
                },
            )
        assert resp.status_code == 200
        assert resp.text == "CHALLENGE_XYZ"

    def test_g2_challenge_wrong_token_returns_403(self):
        client = self._make_app()
        with patch.dict("os.environ", {"IHOUSE_WHATSAPP_VERIFY_TOKEN": "correct"}):
            resp = client.get(
                "/whatsapp/webhook",
                params={
                    "hub.mode": "subscribe",
                    "hub.verify_token": "wrong",
                    "hub.challenge": "c",
                },
            )
        assert resp.status_code == 403

    def test_g3_challenge_no_token_configured_returns_403(self):
        client = self._make_app()
        import os
        with patch.dict("os.environ", {}):
            os.environ.pop("IHOUSE_WHATSAPP_VERIFY_TOKEN", None)
            resp = client.get(
                "/whatsapp/webhook",
                params={"hub.mode": "subscribe", "hub.verify_token": "any", "hub.challenge": "c"},
            )
        assert resp.status_code == 403

    def test_g4_inbound_invalid_sig_returns_403(self):
        client = self._make_app()
        with patch.dict("os.environ", {"IHOUSE_WHATSAPP_APP_SECRET": "secret"}):
            resp = client.post(
                "/whatsapp/webhook",
                content=b'{"entry": []}',
                headers={"X-Hub-Signature-256": "sha256=badsig"},
            )
        assert resp.status_code == 403

    def test_g5_inbound_no_sig_returns_403(self):
        client = self._make_app()
        with patch.dict("os.environ", {"IHOUSE_WHATSAPP_APP_SECRET": "secret"}):
            resp = client.post(
                "/whatsapp/webhook",
                content=b'{}',
            )
        assert resp.status_code == 403

    def test_g6_inbound_valid_sig_returns_200(self):
        _SECRET = "testsecret"
        body = b'{"entry": []}'
        sig = "sha256=" + hmac.new(
            _SECRET.encode(), body, hashlib.sha256
        ).hexdigest()
        client = self._make_app()
        with patch.dict("os.environ", {"IHOUSE_WHATSAPP_APP_SECRET": _SECRET}):
            resp = client.post(
                "/whatsapp/webhook",
                content=body,
                headers={"X-Hub-Signature-256": sig},
            )
        assert resp.status_code == 200

    def test_g7_inbound_non_json_body_returns_200_after_sig(self):
        _SECRET = "s"
        body = b"not-json"
        sig = "sha256=" + hmac.new(_SECRET.encode(), body, hashlib.sha256).hexdigest()
        client = self._make_app()
        with patch.dict("os.environ", {"IHOUSE_WHATSAPP_APP_SECRET": _SECRET}):
            resp = client.post(
                "/whatsapp/webhook",
                content=body,
                headers={"X-Hub-Signature-256": sig},
            )
        assert resp.status_code == 200

    def test_g8_inbound_with_ack_message_processed_true(self):
        _SECRET = "secret"
        payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "text": {"body": "ACK task-abc-123"}
                        }]
                    }
                }]
            }]
        }
        body = json.dumps(payload).encode()
        sig = "sha256=" + hmac.new(_SECRET.encode(), body, hashlib.sha256).hexdigest()
        client = self._make_app()
        with patch.dict("os.environ", {"IHOUSE_WHATSAPP_APP_SECRET": _SECRET}):
            resp = client.post(
                "/whatsapp/webhook",
                content=body,
                headers={"X-Hub-Signature-256": sig},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["processed"] is True


# ---------------------------------------------------------------------------
# Group H — notification_dispatcher per-worker channel architecture
# ---------------------------------------------------------------------------

class TestGroupH_PerWorkerChannelArchitecture:

    def test_h1_whatsapp_channel_constant_defined(self):
        from channels.notification_dispatcher import CHANNEL_WHATSAPP
        assert CHANNEL_WHATSAPP == "whatsapp"

    def test_h2_telegram_channel_constant_defined(self):
        from channels.notification_dispatcher import CHANNEL_TELEGRAM
        assert CHANNEL_TELEGRAM == "telegram"

    def test_h3_sms_channel_constant_defined(self):
        from channels.notification_dispatcher import CHANNEL_SMS
        assert CHANNEL_SMS == "sms"

    def test_h4_whatsapp_in_all_channels(self):
        from channels.notification_dispatcher import _ALL_CHANNELS, CHANNEL_WHATSAPP
        assert CHANNEL_WHATSAPP in _ALL_CHANNELS

    def test_h5_telegram_in_all_channels(self):
        from channels.notification_dispatcher import _ALL_CHANNELS, CHANNEL_TELEGRAM
        assert CHANNEL_TELEGRAM in _ALL_CHANNELS

    def test_h6_sms_in_all_channels(self):
        from channels.notification_dispatcher import _ALL_CHANNELS, CHANNEL_SMS
        assert CHANNEL_SMS in _ALL_CHANNELS

    def test_h7_whatsapp_adapter_registered(self):
        from channels.notification_dispatcher import _DEFAULT_ADAPTERS, CHANNEL_WHATSAPP
        assert CHANNEL_WHATSAPP in _DEFAULT_ADAPTERS
        assert callable(_DEFAULT_ADAPTERS[CHANNEL_WHATSAPP])

    def test_h8_whatsapp_dispatches_to_worker_with_whatsapp_channel(self):
        """Worker registered with channel_type=whatsapp gets WhatsApp dispatch, not LINE."""
        from channels.notification_dispatcher import (
            CHANNEL_WHATSAPP,
            ChannelAttempt,
            NotificationMessage,
            dispatch_notification,
        )
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
            {"channel_type": "whatsapp", "channel_id": "+66812345678"}
        ]
        msg = NotificationMessage(title="Task SLA", body="Please acknowledge")

        def mock_wa_adapter(ch_id, message, db_arg=None, tid=None):
            return ChannelAttempt(channel_type=CHANNEL_WHATSAPP, channel_id=ch_id, success=True)

        result = dispatch_notification(db, "tenant-1", "worker-wa", msg,
                                        adapters={"whatsapp": mock_wa_adapter})
        assert result.sent is True
        assert result.channels[0].channel_type == CHANNEL_WHATSAPP
        assert result.channels[0].channel_id == "+66812345678"

    def test_h9_line_worker_does_not_receive_whatsapp(self):
        """Worker registered with channel_type=line should not get WhatsApp attempt."""
        from channels.notification_dispatcher import (
            CHANNEL_LINE,
            CHANNEL_WHATSAPP,
            ChannelAttempt,
            NotificationMessage,
            dispatch_notification,
        )
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
            {"channel_type": "line", "channel_id": "U-line-user-abc"}
        ]
        msg = NotificationMessage(title="Task SLA", body="Please acknowledge")

        def mock_line_adapter(ch_id, message, db_arg=None, tid=None):
            return ChannelAttempt(channel_type=CHANNEL_LINE, channel_id=ch_id, success=True)

        result = dispatch_notification(db, "tenant-1", "worker-line", msg,
                                        adapters={"line": mock_line_adapter})
        assert result.sent is True
        channel_types = [a.channel_type for a in result.channels]
        assert CHANNEL_LINE in channel_types
        assert CHANNEL_WHATSAPP not in channel_types

    def test_h10_bridge_result_no_whatsapp_global_chain_fields(self):
        """BridgeResult must NOT have whatsapp_attempted or whatsapp_result — those were global-chain artefacts."""
        from channels.sla_dispatch_bridge import BridgeResult
        result = BridgeResult(
            action_type="notify_ops",
            reason="ACK_SLA_BREACH",
            task_id="t-1",
            dispatched_to=[],
        )
        assert not hasattr(result, "whatsapp_attempted"), \
            "whatsapp_attempted should not exist on BridgeResult (global chain removed)"
        assert not hasattr(result, "whatsapp_result"), \
            "whatsapp_result should not exist on BridgeResult (global chain removed)"
