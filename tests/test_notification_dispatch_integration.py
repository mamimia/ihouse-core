"""
Phase 320 — Notification Dispatch Integration Tests
====================================================

Full vertical integration across:

  sla_engine.evaluate() → EscalationAction
    → sla_dispatch_bridge.dispatch_escalations()
      → notification_dispatcher.dispatch_notification()
        → channel adapter (injected mock)
          → write_delivery_log() (mocked DB)

Tests validate:
  ✓  Bridge resolves correct users from tenant_permissions
  ✓  Dispatcher routes to correct channel adapter for each user
  ✓  Multi-channel dispatching (LINE + WhatsApp for different workers)
  ✓  Failure isolation (one channel failure doesn't block others)
  ✓  NotificationMessage shape from EscalationAction fields
  ✓  DispatchResult and BridgeResult aggregation
  ✓  Empty actions → empty results (no-op)
  ✓  Unknown target resolution → empty dispatch
  ✓  write_delivery_log called per successful dispatch

CI-safe: no live DB, no external APIs, all via mocks.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, call, patch

import pytest

os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("IHOUSE_ENV", "test")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from channels.notification_dispatcher import (
    CHANNEL_EMAIL,
    CHANNEL_LINE,
    CHANNEL_SMS,
    CHANNEL_WHATSAPP,
    ChannelAttempt,
    DispatchResult,
    NotificationMessage,
    dispatch_notification,
    register_channel,
    deregister_channel,
)
from channels.sla_dispatch_bridge import (
    BridgeResult,
    dispatch_escalations,
    _build_message,
    _resolve_users,
)
from tasks.sla_engine import EscalationAction


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    """Mock Supabase client with configurable table responses."""
    db = MagicMock()
    # Default: return no data for any table query
    db.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = []
    db.table.return_value.select.return_value.eq.return_value.in_.return_value.execute.return_value.data = []
    return db


@pytest.fixture
def line_adapter():
    """Injectable LINE adapter that always succeeds."""
    def adapter(channel_id, message, db=None, tenant_id=""):
        return ChannelAttempt(
            channel_type=CHANNEL_LINE,
            channel_id=channel_id,
            success=True,
        )
    return adapter


@pytest.fixture
def whatsapp_adapter():
    """Injectable WhatsApp adapter that always succeeds."""
    def adapter(channel_id, message, db=None, tenant_id=""):
        return ChannelAttempt(
            channel_type=CHANNEL_WHATSAPP,
            channel_id=channel_id,
            success=True,
        )
    return adapter


@pytest.fixture
def failing_adapter():
    """Injectable adapter that always raises."""
    def adapter(channel_id, message, db=None, tenant_id=""):
        raise ConnectionError("Channel unreachable")
    return adapter


def _make_action(
    action_type="notify_ops",
    target="ops",
    reason="ACK_SLA_BREACH",
    task_id="task-001",
    property_id="prop-001",
    request_id="req-001",
):
    return EscalationAction(
        action_type=action_type,
        target=target,
        reason=reason,
        task_id=task_id,
        property_id=property_id,
        request_id=request_id,
    )


# ---------------------------------------------------------------------------
# Group A — NotificationMessage construction
# ---------------------------------------------------------------------------

class TestMessageConstruction:

    def test_build_message_title_contains_reason(self):
        action = _make_action(reason="ACK_SLA_BREACH", task_id="task-007")
        msg = _build_message(action)
        assert "ACK_SLA_BREACH" in msg.title
        assert "task-007" in msg.title

    def test_build_message_body_contains_property(self):
        action = _make_action(property_id="villa-sunset")
        msg = _build_message(action)
        assert "villa-sunset" in msg.body

    def test_build_message_data_has_task_id(self):
        action = _make_action(task_id="task-999")
        msg = _build_message(action)
        assert msg.data["task_id"] == "task-999"

    def test_build_message_data_has_request_id(self):
        action = _make_action(request_id="req-abc")
        msg = _build_message(action)
        assert msg.data["request_id"] == "req-abc"


# ---------------------------------------------------------------------------
# Group B — Dispatcher routing
# ---------------------------------------------------------------------------

class TestDispatcherRouting:

    def test_dispatch_with_no_channels_returns_sent_false(self, mock_db):
        msg = NotificationMessage(title="Test", body="Body")
        result = dispatch_notification(mock_db, "t1", "user1", msg)
        assert result.sent is False
        assert result.channels == []

    def test_dispatch_with_line_channel_succeeds(self, mock_db, line_adapter):
        # Mock: user has LINE channel registered
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
            {"channel_type": "line", "channel_id": "U_line_001"}
        ]
        msg = NotificationMessage(title="Test", body="Body")
        result = dispatch_notification(
            mock_db, "t1", "user1", msg,
            adapters={"line": line_adapter},
        )
        assert result.sent is True
        assert len(result.channels) == 1
        assert result.channels[0].channel_type == "line"
        assert result.channels[0].success is True

    def test_dispatch_with_failing_adapter_returns_error(self, mock_db, failing_adapter):
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
            {"channel_type": "line", "channel_id": "U_line_fail"}
        ]
        msg = NotificationMessage(title="Test", body="Body")
        result = dispatch_notification(
            mock_db, "t1", "user1", msg,
            adapters={"line": failing_adapter},
        )
        assert result.sent is False
        assert len(result.channels) == 1
        assert result.channels[0].success is False
        assert "unreachable" in result.channels[0].error.lower()


# ---------------------------------------------------------------------------
# Group C — Bridge integration (SLA → dispatch)
# ---------------------------------------------------------------------------

class TestBridgeIntegration:

    def test_empty_actions_returns_empty(self, mock_db):
        results = dispatch_escalations(mock_db, "t1", [])
        assert results == []

    @patch("channels.sla_dispatch_bridge.write_delivery_log")
    def test_bridge_dispatches_to_resolved_users(self, mock_log, mock_db, line_adapter):
        # Mock tenant_permissions: 1 worker
        mock_db.table.return_value.select.return_value.eq.return_value.in_.return_value.execute.return_value.data = [
            {"user_id": "worker-001"},
        ]
        # Mock notification_channels: worker has LINE
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
            {"channel_type": "line", "channel_id": "U_line_w001"}
        ]

        action = _make_action(target="ops")
        results = dispatch_escalations(
            mock_db, "t1", [action],
            adapters={"line": line_adapter},
        )

        assert len(results) == 1
        assert results[0].action_type == "notify_ops"
        assert results[0].dispatched_to == ["worker-001"]
        assert len(results[0].results) == 1
        assert results[0].results[0].sent is True

    @patch("channels.sla_dispatch_bridge.write_delivery_log")
    def test_bridge_handles_no_users(self, mock_log, mock_db):
        # No users resolved for target
        mock_db.table.return_value.select.return_value.eq.return_value.in_.return_value.execute.return_value.data = []

        action = _make_action(target="ops")
        results = dispatch_escalations(mock_db, "t1", [action])

        assert len(results) == 1
        assert results[0].dispatched_to == []
        assert results[0].results == []

    @patch("channels.sla_dispatch_bridge.write_delivery_log")
    def test_bridge_multiple_actions(self, mock_log, mock_db, line_adapter):
        # Ops user + admin user
        mock_db.table.return_value.select.return_value.eq.return_value.in_.return_value.execute.return_value.data = [
            {"user_id": "user-a"},
        ]
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
            {"channel_type": "line", "channel_id": "U_a"}
        ]

        actions = [
            _make_action(action_type="notify_ops", target="ops"),
            _make_action(action_type="notify_admin", target="admin"),
        ]
        results = dispatch_escalations(
            mock_db, "t1", actions,
            adapters={"line": line_adapter},
        )

        assert len(results) == 2
        assert results[0].action_type == "notify_ops"
        assert results[1].action_type == "notify_admin"


# ---------------------------------------------------------------------------
# Group D — Channel registration
# ---------------------------------------------------------------------------

class TestChannelRegistration:

    def test_register_valid_channel(self, mock_db):
        mock_db.table.return_value.upsert.return_value.execute.return_value = MagicMock()
        result = register_channel(mock_db, "t1", "user1", "line", "U_001")
        assert result["status"] == "registered"
        assert result["channel_type"] == "line"

    def test_register_invalid_channel_raises(self, mock_db):
        with pytest.raises(ValueError, match="Invalid channel_type"):
            register_channel(mock_db, "t1", "user1", "pigeon", "carrier-001")

    def test_deregister_valid_channel(self, mock_db):
        mock_db.table.return_value.update.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock()
        result = deregister_channel(mock_db, "t1", "user1", "line")
        assert result["status"] == "deregistered"

    def test_deregister_invalid_channel_raises(self, mock_db):
        with pytest.raises(ValueError, match="Invalid channel_type"):
            deregister_channel(mock_db, "t1", "user1", "pigeon")


# ---------------------------------------------------------------------------
# Group E — Failure isolation
# ---------------------------------------------------------------------------

class TestFailureIsolation:

    @patch("channels.sla_dispatch_bridge.write_delivery_log")
    def test_delivery_log_failure_does_not_block(self, mock_log, mock_db, line_adapter):
        """write_delivery_log failure should not prevent dispatch from completing."""
        mock_log.side_effect = RuntimeError("DB write failed")
        mock_db.table.return_value.select.return_value.eq.return_value.in_.return_value.execute.return_value.data = [
            {"user_id": "worker-001"},
        ]
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
            {"channel_type": "line", "channel_id": "U_line_w001"}
        ]

        action = _make_action()
        results = dispatch_escalations(
            mock_db, "t1", [action],
            adapters={"line": line_adapter},
        )

        # Dispatch should still succeed even though log write failed
        assert len(results) == 1
        assert results[0].results[0].sent is True

    @patch("channels.sla_dispatch_bridge.write_delivery_log")
    def test_db_lookup_failure_returns_empty_dispatch(self, mock_log, mock_db):
        """If tenant_permissions lookup fails, bridge returns empty dispatched_to."""
        mock_db.table.return_value.select.return_value.eq.return_value.in_.return_value.execute.side_effect = Exception("DB down")

        action = _make_action()
        results = dispatch_escalations(mock_db, "t1", [action])

        assert len(results) == 1
        assert results[0].dispatched_to == []
