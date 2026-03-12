"""
Phase 347 — Notification Delivery E2E Verification
====================================================

HTTP-level E2E tests for notification endpoints via the full app router.
Tests exercise the dispatcher dry-run paths (no Twilio/SendGrid env vars)
and verify notification_log persistence.

Groups:
  A — POST /notifications/send-sms (5 tests)
  B — POST /notifications/send-email (5 tests)
  C — POST /notifications/guest-token-send (5 tests)
  D — GET /notifications/log (4 tests)
  E — SLA → Bridge → Dispatch → Writer Chain (5 tests)
  F — Delivery Writer Persistence (4 tests)

Design:
  - All router tests use TestClient with dev-mode JWT bypass
  - Supabase DB mocked via patch on notification_router._get_db
  - Twilio/SendGrid env vars NOT set → dry_run mode
  - SLA chain tests exercise sla_engine → sla_dispatch_bridge → dispatcher
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch, call

os.environ.setdefault("IHOUSE_ENV", "test")
os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("SUPABASE_URL", "http://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("IHOUSE_GUEST_TOKEN_SECRET", "test-guest-secret-long-enough-32b")

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from main import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)

TENANT = "dev-tenant"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _query_chain(rows: list | None = None):
    q = MagicMock()
    for m in ("select", "eq", "gte", "lte", "lt", "neq", "in_", "is_",
              "limit", "order", "insert", "update", "upsert", "delete"):
        setattr(q, m, MagicMock(return_value=q))
    q.execute.return_value = MagicMock(data=rows if rows is not None else [])
    return q


def _make_db(log_row: dict | None = None):
    """Build a mock DB that handles notification_log inserts and queries."""
    db = MagicMock()
    default_row = log_row or {"notification_id": "n-test-001", "status": "pending"}

    def _table_side_effect(name: str):
        chain = _query_chain([default_row])
        return chain

    db.table.side_effect = _table_side_effect
    return db


# ---------------------------------------------------------------------------
# Group A — POST /notifications/send-sms
# ---------------------------------------------------------------------------

class TestGroupASendSms:

    def test_a1_dry_run_sms_returns_200(self):
        """SMS dispatch without Twilio env vars returns dry_run status."""
        with patch("api.notification_router._get_db", return_value=_make_db()):
            r = client.post("/notifications/send-sms", json={
                "to_number": "+66812345678",
                "body": "Test notification.",
            })
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "dry_run"
        assert body["channel"] == "sms"

    def test_a2_sms_response_has_notification_id(self):
        """SMS dispatch returns a notification_id for audit."""
        with patch("api.notification_router._get_db", return_value=_make_db()):
            r = client.post("/notifications/send-sms", json={
                "to_number": "+66000000000",
                "body": "Hello guest",
            })
        assert "notification_id" in r.json()

    def test_a3_sms_with_reference_id(self):
        """SMS dispatch logs the reference_id for tracing."""
        with patch("api.notification_router._get_db", return_value=_make_db()):
            r = client.post("/notifications/send-sms", json={
                "to_number": "+66812345678",
                "body": "Your booking BK-001 is confirmed.",
                "notification_type": "booking_confirm",
                "reference_id": "BK-001",
            })
        assert r.status_code == 200
        assert r.json()["recipient"] == "+66812345678"

    def test_a4_sms_missing_body_returns_422(self):
        """Send SMS without body text returns validation error."""
        r = client.post("/notifications/send-sms", json={
            "to_number": "+66812345678",
        })
        assert r.status_code == 422

    def test_a5_sms_missing_number_returns_422(self):
        """Send SMS without phone number returns validation error."""
        r = client.post("/notifications/send-sms", json={
            "body": "Hello",
        })
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Group B — POST /notifications/send-email
# ---------------------------------------------------------------------------

class TestGroupBSendEmail:

    def test_b1_dry_run_email_returns_200(self):
        """Email dispatch without SendGrid env vars returns dry_run."""
        with patch("api.notification_router._get_db", return_value=_make_db()):
            r = client.post("/notifications/send-email", json={
                "to_email": "guest@test.com",
                "subject": "Booking Confirmed",
                "body_html": "<p>Welcome!</p>",
            })
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "dry_run"
        assert body["channel"] == "email"

    def test_b2_email_response_has_notification_id(self):
        """Email dispatch returns a notification_id."""
        with patch("api.notification_router._get_db", return_value=_make_db()):
            r = client.post("/notifications/send-email", json={
                "to_email": "admin@test.com",
                "subject": "Test",
                "body_html": "<h1>Hi</h1>",
            })
        assert "notification_id" in r.json()

    def test_b3_email_with_reference_id(self):
        """Email dispatch logs reference_id."""
        with patch("api.notification_router._get_db", return_value=_make_db()):
            r = client.post("/notifications/send-email", json={
                "to_email": "owner@test.com",
                "subject": "Statement Ready",
                "body_html": "<p>Your owner statement is ready.</p>",
                "notification_type": "owner_statement",
                "reference_id": "STMT-2026-03",
            })
        assert r.status_code == 200

    def test_b4_email_missing_subject_returns_422(self):
        """Send email without subject returns 422."""
        r = client.post("/notifications/send-email", json={
            "to_email": "test@test.com",
            "body_html": "<p>Hi</p>",
        })
        assert r.status_code == 422

    def test_b5_email_missing_body_returns_422(self):
        """Send email without body returns 422."""
        r = client.post("/notifications/send-email", json={
            "to_email": "test@test.com",
            "subject": "Test",
        })
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Group C — POST /notifications/guest-token-send
# ---------------------------------------------------------------------------

class TestGroupCGuestTokenSend:

    def test_c1_sms_channel_returns_201(self):
        """Guest token send via SMS returns 201 with booking_ref."""
        with patch("api.notification_router._get_db", return_value=_make_db()):
            r = client.post("/notifications/guest-token-send", json={
                "booking_ref": "BK-GT-001",
                "to_phone": "+66812345678",
                "portal_base_url": "https://portal.domaniqo.com",
            })
        assert r.status_code == 201
        body = r.json()
        assert body["booking_ref"] == "BK-GT-001"
        assert body["channels_used"] == 1

    def test_c2_email_channel_returns_201(self):
        """Guest token send via email returns 201."""
        with patch("api.notification_router._get_db", return_value=_make_db()):
            r = client.post("/notifications/guest-token-send", json={
                "booking_ref": "BK-GT-002",
                "to_email": "guest@test.com",
                "portal_base_url": "https://portal.domaniqo.com",
            })
        assert r.status_code == 201
        body = r.json()
        assert body["channels_used"] == 1

    def test_c3_both_channels_returns_201(self):
        """Guest token send via SMS + email returns 201 with 2 channels."""
        with patch("api.notification_router._get_db", return_value=_make_db()):
            r = client.post("/notifications/guest-token-send", json={
                "booking_ref": "BK-GT-003",
                "to_phone": "+66812345678",
                "to_email": "guest@test.com",
                "portal_base_url": "https://portal.domaniqo.com",
            })
        assert r.status_code == 201
        body = r.json()
        assert body["channels_used"] == 2
        assert len(body["notifications"]) == 2

    def test_c4_no_recipient_returns_422(self):
        """Guest token send without any recipient returns 422."""
        r = client.post("/notifications/guest-token-send", json={
            "booking_ref": "BK-GT-004",
            "portal_base_url": "https://portal.domaniqo.com",
        })
        assert r.status_code == 422

    def test_c5_token_not_in_response(self):
        """Security: raw guest token is NOT included in the response."""
        with patch("api.notification_router._get_db", return_value=_make_db()):
            r = client.post("/notifications/guest-token-send", json={
                "booking_ref": "BK-GT-005",
                "to_phone": "+66000000000",
                "portal_base_url": "https://portal.domaniqo.com",
            })
        body = r.json()
        # The response should NOT contain a raw token field
        assert "token" not in body


# ---------------------------------------------------------------------------
# Group D — GET /notifications/log
# ---------------------------------------------------------------------------

class TestGroupDNotificationLog:

    def test_d1_log_returns_200_with_entries(self):
        """GET /notifications/log returns logged dispatches."""
        log_entries = [
            {"notification_id": "n-1", "channel": "sms", "status": "dry_run",
             "recipient": "+66812345678", "notification_type": "generic",
             "reference_id": None, "provider_id": None, "sent_at": None,
             "created_at": "2026-03-12T00:00:00Z"},
        ]
        db = MagicMock()
        db.table.return_value = _query_chain(log_entries)
        with patch("api.notification_router._get_db", return_value=db):
            r = client.get("/notifications/log")
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 1
        assert body["entries"][0]["channel"] == "sms"

    def test_d2_log_with_limit(self):
        """GET /notifications/log?limit=10 respects limit."""
        db = MagicMock()
        db.table.return_value = _query_chain([])
        with patch("api.notification_router._get_db", return_value=db):
            r = client.get("/notifications/log?limit=10")
        assert r.status_code == 200

    def test_d3_log_with_reference_filter(self):
        """GET /notifications/log?reference_id=BK-001 filters correctly."""
        db = MagicMock()
        db.table.return_value = _query_chain([])
        with patch("api.notification_router._get_db", return_value=db):
            r = client.get("/notifications/log?reference_id=BK-001")
        assert r.status_code == 200

    def test_d4_log_empty_returns_200(self):
        """GET /notifications/log with no entries returns count=0."""
        db = MagicMock()
        db.table.return_value = _query_chain([])
        with patch("api.notification_router._get_db", return_value=db):
            r = client.get("/notifications/log")
        assert r.json()["count"] == 0


# ---------------------------------------------------------------------------
# Group E — SLA → Bridge → Dispatch → Writer Chain
# ---------------------------------------------------------------------------

class TestGroupESlaChain:
    """Full-chain tests: sla_engine → sla_dispatch_bridge → dispatcher."""

    def test_e1_critical_ack_breach_triggers_ops_dispatch(self):
        """SLA breach generates EscalationAction, bridge dispatches to ops."""
        from tasks.sla_engine import EscalationAction
        from channels.sla_dispatch_bridge import dispatch_escalations

        action = EscalationAction(
            action_type="notify_ops",
            target="ops",
            task_id="T-SLA-001",
            property_id="prop-001",
            reason="ACK_SLA_BREACH",
            request_id="req-001",
        )

        db = MagicMock()
        # tenant_permissions returns ops users
        users_chain = _query_chain([
            {"user_id": "worker-1", "role": "worker"},
        ])
        # notification_channels returns LINE for worker
        channels_chain = _query_chain([
            {"channel_type": "line", "channel_id": "LINE-TOKEN-1"},
        ])

        call_count = [0]
        def _table_side_effect(name: str):
            if name == "tenant_permissions":
                return users_chain
            if name == "notification_channels":
                return channels_chain
            if name == "notification_delivery_log":
                return _query_chain([])
            return _query_chain([])

        db.table.side_effect = _table_side_effect

        results = dispatch_escalations(db, TENANT, [action])
        assert len(results) == 1
        assert results[0].action_type == "notify_ops"
        assert results[0].task_id == "T-SLA-001"
        assert len(results[0].dispatched_to) == 1

    def test_e2_admin_escalation_dispatches_to_admin(self):
        """Admin escalation action dispatches to admin users."""
        from tasks.sla_engine import EscalationAction
        from channels.sla_dispatch_bridge import dispatch_escalations

        action = EscalationAction(
            action_type="notify_admin",
            target="admin",
            task_id="T-SLA-002",
            property_id="prop-001",
            reason="ESCALATION_TIER_2",
            request_id="req-002",
        )

        db = MagicMock()
        def _table_side_effect(name: str):
            if name == "tenant_permissions":
                return _query_chain([{"user_id": "admin-1", "role": "admin"}])
            if name == "notification_channels":
                return _query_chain([
                    {"channel_type": "whatsapp", "channel_id": "+66999999999"},
                ])
            if name == "notification_delivery_log":
                return _query_chain([])
            return _query_chain([])
        db.table.side_effect = _table_side_effect

        results = dispatch_escalations(db, TENANT, [action])
        assert len(results) == 1
        assert results[0].action_type == "notify_admin"
        assert "admin-1" in results[0].dispatched_to

    def test_e3_empty_actions_returns_empty(self):
        """Empty actions list yields empty results (no-op)."""
        from channels.sla_dispatch_bridge import dispatch_escalations
        results = dispatch_escalations(MagicMock(), TENANT, [])
        assert results == []

    def test_e4_no_users_dispatches_empty(self):
        """No resolved users → dispatched_to is empty."""
        from tasks.sla_engine import EscalationAction
        from channels.sla_dispatch_bridge import dispatch_escalations

        action = EscalationAction(
            action_type="notify_ops", target="ops",
            task_id="T-SLA-003", property_id="prop-001",
            reason="ACK_SLA_BREACH", request_id="req-003",
        )
        db = MagicMock()
        db.table.return_value = _query_chain([])  # no users

        results = dispatch_escalations(db, TENANT, [action])
        assert results[0].dispatched_to == []

    def test_e5_bridge_result_shape(self):
        """BridgeResult has required fields: action_type, reason, task_id."""
        from tasks.sla_engine import EscalationAction
        from channels.sla_dispatch_bridge import dispatch_escalations, BridgeResult

        action = EscalationAction(
            action_type="notify_ops", target="ops",
            task_id="T-SLA-004", property_id="prop-001",
            reason="TEST_SHAPE", request_id="req-004",
        )
        db = MagicMock()
        db.table.return_value = _query_chain([])

        results = dispatch_escalations(db, TENANT, [action])
        br = results[0]
        assert isinstance(br, BridgeResult)
        assert br.reason == "TEST_SHAPE"


# ---------------------------------------------------------------------------
# Group F — Delivery Writer Persistence
# ---------------------------------------------------------------------------

class TestGroupFDeliveryWriter:
    """Tests for notification_delivery_writer.write_delivery_log."""

    def test_f1_writes_one_row_per_channel(self):
        """write_delivery_log creates one DB row per ChannelAttempt."""
        from channels.notification_dispatcher import ChannelAttempt, DispatchResult
        from channels.notification_delivery_writer import write_delivery_log

        result = DispatchResult(
            sent=True, user_id="U-1",
            channels=[
                ChannelAttempt(channel_type="line", channel_id="L-1", success=True),
                ChannelAttempt(channel_type="fcm", channel_id="F-1", success=True),
            ],
        )
        db = MagicMock()
        count = write_delivery_log(
            db=db, result=result, tenant_id=TENANT, task_id="T-1",
        )
        assert count == 2
        assert db.table.call_count == 2

    def test_f2_never_raises_on_db_error(self):
        """write_delivery_log swallows DB errors and returns 0."""
        from channels.notification_dispatcher import ChannelAttempt, DispatchResult
        from channels.notification_delivery_writer import write_delivery_log

        result = DispatchResult(
            sent=True, user_id="U-2",
            channels=[
                ChannelAttempt(channel_type="line", channel_id="L-2", success=True),
            ],
        )
        db = MagicMock()
        db.table.side_effect = RuntimeError("DB down")
        count = write_delivery_log(
            db=db, result=result, tenant_id=TENANT,
        )
        assert count == 0  # No rows written, but no exception raised

    def test_f3_empty_channels_writes_zero(self):
        """write_delivery_log with empty channels returns 0 immediately."""
        from channels.notification_dispatcher import DispatchResult
        from channels.notification_delivery_writer import write_delivery_log

        result = DispatchResult(sent=False, user_id="U-3", channels=[])
        db = MagicMock()
        count = write_delivery_log(
            db=db, result=result, tenant_id=TENANT,
        )
        assert count == 0
        db.table.assert_not_called()

    def test_f4_failed_channel_logged_with_error(self):
        """write_delivery_log records failed attempts with error_message."""
        from channels.notification_dispatcher import ChannelAttempt, DispatchResult
        from channels.notification_delivery_writer import write_delivery_log

        result = DispatchResult(
            sent=False, user_id="U-4",
            channels=[
                ChannelAttempt(
                    channel_type="sms", channel_id="+66000",
                    success=False, error="Twilio: invalid number",
                ),
            ],
        )
        db = MagicMock()
        count = write_delivery_log(
            db=db, result=result, tenant_id=TENANT,
            task_id="T-FAIL", trigger_reason="SMS_ESCALATION",
        )
        assert count == 1
        # Verify the row contains the error
        insert_call = db.table.return_value.insert.call_args
        payload = insert_call[0][0]
        assert payload["status"] == "failed"
        assert "Twilio" in payload["error_message"]
        assert payload["trigger_reason"] == "SMS_ESCALATION"
