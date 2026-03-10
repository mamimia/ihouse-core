"""
Phase 168 — Notification Dispatcher Contract Tests

Groups:
  A — dispatch_notification: no channels (sent=False)
  B — dispatch_notification: single LINE channel
  C — dispatch_notification: multiple channels, priority order LINE > FCM > email
  D — dispatch_notification: channel adapter failure is fail-isolated
  E — dispatch_notification: DB lookup failure returns empty result (best-effort)
  F — dispatch_notification: DispatchResult shape invariants
  G — register_channel: upsert + invalid channel_type
  H — deregister_channel: sets active=False
  I — _lookup_channels: only active=True rows returned
"""
from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from channels.notification_dispatcher import (
    dispatch_notification,
    register_channel,
    deregister_channel,
    _lookup_channels,
    NotificationMessage,
    DispatchResult,
    ChannelAttempt,
    CHANNEL_LINE,
    CHANNEL_FCM,
    CHANNEL_EMAIL,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MSG = NotificationMessage(
    title="Test Alert",
    body="This is a test notification.",
    data={"task_id": "t-001"},
)


def _make_db(channels: list[dict] | None = None, db_error: bool = False) -> MagicMock:
    """Build a mock Supabase client."""
    db = MagicMock()
    q = MagicMock()
    q.select.return_value = q
    q.eq.return_value = q
    q.update.return_value = q
    q.upsert.return_value = q
    if db_error:
        q.execute.side_effect = RuntimeError("DB error")
    else:
        q.execute.return_value = MagicMock(data=channels or [])
    db.table.return_value = q
    db._q = q
    return db


def _stub_adapter(success: bool, error: str | None = None):
    """Return an adapter that always returns the given success value."""
    def _adapter(channel_id: str, message: NotificationMessage) -> ChannelAttempt:
        return ChannelAttempt(
            channel_type="stub",
            channel_id=channel_id,
            success=success,
            error=error,
        )
    return _adapter


def _raising_adapter(exc: Exception):
    """Return an adapter that always raises."""
    def _adapter(channel_id: str, message: NotificationMessage) -> ChannelAttempt:
        raise exc
    return _adapter


# ---------------------------------------------------------------------------
# Group A — No channels → sent=False
# ---------------------------------------------------------------------------

def test_a1_no_channels_returns_sent_false():
    db = _make_db(channels=[])
    result = dispatch_notification(db, "t1", "u1", _MSG)
    assert result.sent is False


def test_a2_no_channels_returns_empty_attempts():
    db = _make_db(channels=[])
    result = dispatch_notification(db, "t1", "u1", _MSG)
    assert result.channels == []


def test_a3_no_channels_user_id_preserved():
    db = _make_db(channels=[])
    result = dispatch_notification(db, "t1", "u1", _MSG)
    assert result.user_id == "u1"


# ---------------------------------------------------------------------------
# Group B — Single LINE channel
# ---------------------------------------------------------------------------

def test_b1_line_channel_dispatched():
    db = _make_db(channels=[{"channel_type": CHANNEL_LINE, "channel_id": "line-abc"}])
    adapters = {CHANNEL_LINE: _stub_adapter(True)}
    result = dispatch_notification(db, "t1", "u1", _MSG, adapters=adapters)
    assert result.sent is True


def test_b2_line_dispatch_attempt_recorded():
    db = _make_db(channels=[{"channel_type": CHANNEL_LINE, "channel_id": "line-abc"}])
    adapters = {CHANNEL_LINE: _stub_adapter(True)}
    result = dispatch_notification(db, "t1", "u1", _MSG, adapters=adapters)
    assert len(result.channels) == 1
    assert result.channels[0].channel_type == "stub"


def test_b3_line_adapter_receives_message():
    received = []

    def _capture_adapter(channel_id: str, msg: NotificationMessage) -> ChannelAttempt:
        received.append((channel_id, msg))
        return ChannelAttempt(channel_type=CHANNEL_LINE, channel_id=channel_id, success=True)

    db = _make_db(channels=[{"channel_type": CHANNEL_LINE, "channel_id": "line-xyz"}])
    dispatch_notification(db, "t1", "u1", _MSG, adapters={CHANNEL_LINE: _capture_adapter})
    assert len(received) == 1
    assert received[0][0] == "line-xyz"
    assert received[0][1] is _MSG


# ---------------------------------------------------------------------------
# Group C — Multiple channels: priority order LINE > FCM > email
# ---------------------------------------------------------------------------

def test_c1_all_three_channels_all_attempted():
    db = _make_db(channels=[
        {"channel_type": CHANNEL_LINE,  "channel_id": "line-1"},
        {"channel_type": CHANNEL_FCM,   "channel_id": "fcm-tok"},
        {"channel_type": CHANNEL_EMAIL, "channel_id": "user@example.com"},
    ])
    order = []

    def _line(cid, msg):
        order.append(CHANNEL_LINE)
        return ChannelAttempt(channel_type=CHANNEL_LINE, channel_id=cid, success=True)

    def _fcm(cid, msg):
        order.append(CHANNEL_FCM)
        return ChannelAttempt(channel_type=CHANNEL_FCM, channel_id=cid, success=True)

    def _email(cid, msg):
        order.append(CHANNEL_EMAIL)
        return ChannelAttempt(channel_type=CHANNEL_EMAIL, channel_id=cid, success=True)

    dispatch_notification(db, "t1", "u1", _MSG, adapters={
        CHANNEL_LINE: _line,
        CHANNEL_FCM: _fcm,
        CHANNEL_EMAIL: _email,
    })
    assert order == [CHANNEL_LINE, CHANNEL_FCM, CHANNEL_EMAIL]


def test_c2_sent_true_if_any_channel_succeeds():
    db = _make_db(channels=[
        {"channel_type": CHANNEL_LINE, "channel_id": "line-1"},
        {"channel_type": CHANNEL_FCM,  "channel_id": "fcm-1"},
    ])
    adapters = {
        CHANNEL_LINE: _stub_adapter(True),
        CHANNEL_FCM:  _stub_adapter(False),
    }
    result = dispatch_notification(db, "t1", "u1", _MSG, adapters=adapters)
    assert result.sent is True


def test_c3_sent_false_if_all_channels_fail():
    db = _make_db(channels=[
        {"channel_type": CHANNEL_LINE, "channel_id": "line-1"},
        {"channel_type": CHANNEL_FCM,  "channel_id": "fcm-1"},
    ])
    adapters = {
        CHANNEL_LINE: _stub_adapter(False),
        CHANNEL_FCM:  _stub_adapter(False),
    }
    result = dispatch_notification(db, "t1", "u1", _MSG, adapters=adapters)
    assert result.sent is False


def test_c4_fcm_only_channel_dispatched():
    db = _make_db(channels=[{"channel_type": CHANNEL_FCM, "channel_id": "fcm-tok"}])
    adapters = {CHANNEL_FCM: _stub_adapter(True)}
    result = dispatch_notification(db, "t1", "u1", _MSG, adapters=adapters)
    assert result.sent is True
    assert len(result.channels) == 1


def test_c5_email_only_channel_dispatched():
    db = _make_db(channels=[{"channel_type": CHANNEL_EMAIL, "channel_id": "u@e.com"}])
    adapters = {CHANNEL_EMAIL: _stub_adapter(True)}
    result = dispatch_notification(db, "t1", "u1", _MSG, adapters=adapters)
    assert result.sent is True


# ---------------------------------------------------------------------------
# Group D — Channel adapter failure is fail-isolated
# ---------------------------------------------------------------------------

def test_d1_raising_adapter_does_not_propagate():
    db = _make_db(channels=[{"channel_type": CHANNEL_LINE, "channel_id": "line-1"}])
    adapters = {CHANNEL_LINE: _raising_adapter(RuntimeError("LINE API down"))}
    result = dispatch_notification(db, "t1", "u1", _MSG, adapters=adapters)
    # Must not raise; result.sent is False
    assert result.sent is False


def test_d2_raising_adapter_records_error_in_attempt():
    db = _make_db(channels=[{"channel_type": CHANNEL_LINE, "channel_id": "line-1"}])
    adapters = {CHANNEL_LINE: _raising_adapter(RuntimeError("timeout"))}
    result = dispatch_notification(db, "t1", "u1", _MSG, adapters=adapters)
    assert len(result.channels) == 1
    assert result.channels[0].success is False
    assert "timeout" in (result.channels[0].error or "")


def test_d3_line_fails_fcm_still_tried():
    db = _make_db(channels=[
        {"channel_type": CHANNEL_LINE, "channel_id": "line-1"},
        {"channel_type": CHANNEL_FCM,  "channel_id": "fcm-1"},
    ])
    adapters = {
        CHANNEL_LINE: _raising_adapter(RuntimeError("LINE down")),
        CHANNEL_FCM:  _stub_adapter(True),
    }
    result = dispatch_notification(db, "t1", "u1", _MSG, adapters=adapters)
    assert result.sent is True  # FCM succeeded
    assert len(result.channels) == 2


def test_d4_no_adapter_for_channel_records_failure():
    db = _make_db(channels=[{"channel_type": CHANNEL_LINE, "channel_id": "line-1"}])
    result = dispatch_notification(db, "t1", "u1", _MSG, adapters={})  # no LINE adapter
    assert len(result.channels) == 1
    assert result.channels[0].success is False


# ---------------------------------------------------------------------------
# Group E — DB error → best-effort empty result
# ---------------------------------------------------------------------------

def test_e1_db_error_returns_sent_false():
    db = _make_db(db_error=True)
    result = dispatch_notification(db, "t1", "u1", _MSG)
    assert result.sent is False


def test_e2_db_error_returns_empty_channels():
    db = _make_db(db_error=True)
    result = dispatch_notification(db, "t1", "u1", _MSG)
    assert result.channels == []


# ---------------------------------------------------------------------------
# Group F — DispatchResult shape invariants
# ---------------------------------------------------------------------------

def test_f1_result_is_dispatch_result():
    db = _make_db(channels=[])
    result = dispatch_notification(db, "t1", "u1", _MSG)
    assert isinstance(result, DispatchResult)


def test_f2_channel_attempt_has_required_fields():
    db = _make_db(channels=[{"channel_type": CHANNEL_LINE, "channel_id": "line-1"}])
    adapters = {CHANNEL_LINE: _stub_adapter(True)}
    result = dispatch_notification(db, "t1", "u1", _MSG, adapters=adapters)
    a = result.channels[0]
    assert hasattr(a, "channel_type")
    assert hasattr(a, "channel_id")
    assert hasattr(a, "success")


# ---------------------------------------------------------------------------
# Group G — register_channel
# ---------------------------------------------------------------------------

def test_g1_register_line_channel_calls_upsert():
    db = _make_db()
    result = register_channel(db, "t1", "u1", CHANNEL_LINE, "line-token")
    assert result["status"] == "registered"
    assert result["channel_type"] == CHANNEL_LINE


def test_g2_register_fcm_channel():
    db = _make_db()
    result = register_channel(db, "t1", "u1", CHANNEL_FCM, "fcm-token")
    assert result["channel_type"] == CHANNEL_FCM


def test_g3_register_invalid_channel_type_raises():
    db = _make_db()
    with pytest.raises(ValueError, match="Invalid channel_type"):
        register_channel(db, "t1", "u1", "whatsapp", "wa-token")


def test_g4_register_returns_correct_user_and_tenant():
    db = _make_db()
    result = register_channel(db, "tenant-x", "user-y", CHANNEL_EMAIL, "u@e.com")
    assert result["tenant_id"] == "tenant-x"
    assert result["user_id"] == "user-y"
    assert result["channel_id"] == "u@e.com"


# ---------------------------------------------------------------------------
# Group H — deregister_channel
# ---------------------------------------------------------------------------

def test_h1_deregister_returns_deregistered():
    db = _make_db()
    result = deregister_channel(db, "t1", "u1", CHANNEL_LINE)
    assert result["status"] == "deregistered"


def test_h2_deregister_invalid_type_raises():
    db = _make_db()
    with pytest.raises(ValueError):
        deregister_channel(db, "t1", "u1", "telegram")


# ---------------------------------------------------------------------------
# Group I — _lookup_channels filters active=True
# ---------------------------------------------------------------------------

def test_i1_lookup_passes_active_true_filter():
    db = _make_db(channels=[{"channel_type": CHANNEL_LINE, "channel_id": "x"}])
    result = _lookup_channels(db, "t1", "u1")
    assert len(result) == 1
    # Verify active=True eq was called on the query
    eq_calls = [c.args for c in db._q.eq.call_args_list]
    assert ("active", True) in eq_calls


def test_i2_lookup_db_error_returns_empty_list():
    db = _make_db(db_error=True)
    result = _lookup_channels(db, "t1", "u1")
    assert result == []
