"""
Phase 183 — Contract tests for notification_delivery_writer + bridge wiring

Groups:
    A — write_delivery_log: happy path (sent + failed attempts)
    B — write_delivery_log: edge cases (empty channels, DB error swallowed)
    C — write_delivery_log: row content validation
    D — write_delivery_log: return value (count of written rows)
    E — sla_dispatch_bridge: write_delivery_log called after dispatch
    F — sla_dispatch_bridge: delivery log DB error does not affect dispatch
"""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from channels.notification_delivery_writer import write_delivery_log
from channels.notification_dispatcher import ChannelAttempt, DispatchResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db(insert_raises: bool = False) -> MagicMock:
    """Build a minimal mock DB client."""
    db = MagicMock()
    if insert_raises:
        db.table.return_value.insert.return_value.execute.side_effect = RuntimeError("DB down")
    return db


def _make_result(
    user_id: str = "U-1",
    attempts: list[ChannelAttempt] | None = None,
) -> DispatchResult:
    if attempts is None:
        attempts = [
            ChannelAttempt(channel_type="line", channel_id="LINE-TOKEN", success=True),
        ]
    return DispatchResult(
        sent=any(a.success for a in attempts),
        user_id=user_id,
        channels=attempts,
    )


# ---------------------------------------------------------------------------
# Group A — happy path
# ---------------------------------------------------------------------------

class TestGroupAHappyPath:

    def test_a1_single_sent_attempt_writes_one_row(self):
        db = _make_db()
        result = _make_result()

        write_delivery_log(db=db, result=result, tenant_id="T1")

        db.table.assert_called_with("notification_delivery_log")
        db.table.return_value.insert.assert_called_once()

    def test_a2_single_failed_attempt_writes_one_row(self):
        db = _make_db()
        result = _make_result(attempts=[
            ChannelAttempt(channel_type="line", channel_id="LT", success=False, error="timeout"),
        ])

        write_delivery_log(db=db, result=result, tenant_id="T1")

        db.table.return_value.insert.assert_called_once()

    def test_a3_two_attempts_write_two_rows(self):
        db = _make_db()
        result = _make_result(attempts=[
            ChannelAttempt(channel_type="line", channel_id="LT", success=True),
            ChannelAttempt(channel_type="fcm", channel_id="FCM-T", success=False, error="err"),
        ])

        write_delivery_log(db=db, result=result, tenant_id="T1")

        assert db.table.return_value.insert.call_count == 2

    def test_a4_status_sent_for_success(self):
        db = _make_db()
        result = _make_result(attempts=[
            ChannelAttempt(channel_type="line", channel_id="LT", success=True),
        ])

        write_delivery_log(db=db, result=result, tenant_id="T1")

        inserted = db.table.return_value.insert.call_args[0][0]
        assert inserted["status"] == "sent"

    def test_a5_status_failed_for_failure(self):
        db = _make_db()
        result = _make_result(attempts=[
            ChannelAttempt(channel_type="fcm", channel_id="FC", success=False, error="timeout"),
        ])

        write_delivery_log(db=db, result=result, tenant_id="T1")

        inserted = db.table.return_value.insert.call_args[0][0]
        assert inserted["status"] == "failed"


# ---------------------------------------------------------------------------
# Group B — edge cases
# ---------------------------------------------------------------------------

class TestGroupBEdgeCases:

    def test_b1_empty_channels_writes_nothing(self):
        db = _make_db()
        result = DispatchResult(sent=False, user_id="U1", channels=[])

        write_delivery_log(db=db, result=result, tenant_id="T1")

        db.table.assert_not_called()

    def test_b2_db_insert_error_does_not_raise(self):
        db = _make_db(insert_raises=True)
        result = _make_result()

        # Must not raise
        write_delivery_log(db=db, result=result, tenant_id="T1")

    def test_b3_task_id_and_trigger_reason_none_by_default(self):
        db = _make_db()
        result = _make_result()

        write_delivery_log(db=db, result=result, tenant_id="T1")

        inserted = db.table.return_value.insert.call_args[0][0]
        assert inserted["task_id"] is None
        assert inserted["trigger_reason"] is None

    def test_b4_db_error_on_second_row_first_row_still_written(self):
        """First insert succeeds; second raises. Should write 1 row without raising."""
        db = MagicMock()
        db.table.return_value.insert.return_value.execute.side_effect = [
            None,  # first call ok
            RuntimeError("DB error"),  # second call fails
        ]
        result = _make_result(attempts=[
            ChannelAttempt(channel_type="line", channel_id="LT", success=True),
            ChannelAttempt(channel_type="fcm", channel_id="FT", success=True),
        ])

        count = write_delivery_log(db=db, result=result, tenant_id="T1")
        assert count == 1


# ---------------------------------------------------------------------------
# Group C — row content validation
# ---------------------------------------------------------------------------

class TestGroupCRowContent:

    def _get_inserted_row(self) -> dict:
        db = _make_db()
        result = _make_result(
            user_id="USER-42",
            attempts=[
                ChannelAttempt(channel_type="email", channel_id="u@x.com", success=True),
            ],
        )
        write_delivery_log(
            db=db,
            result=result,
            tenant_id="TENANT-1",
            task_id="TASK-99",
            trigger_reason="ACK_SLA_BREACH",
        )
        return db.table.return_value.insert.call_args[0][0]

    def test_c1_tenant_id_written(self):
        assert self._get_inserted_row()["tenant_id"] == "TENANT-1"

    def test_c2_user_id_written(self):
        assert self._get_inserted_row()["user_id"] == "USER-42"

    def test_c3_task_id_written(self):
        assert self._get_inserted_row()["task_id"] == "TASK-99"

    def test_c4_trigger_reason_written(self):
        assert self._get_inserted_row()["trigger_reason"] == "ACK_SLA_BREACH"

    def test_c5_channel_type_and_id_written(self):
        row = self._get_inserted_row()
        assert row["channel_type"] == "email"
        assert row["channel_id"] == "u@x.com"

    def test_c6_notification_delivery_id_is_uuid(self):
        import uuid
        row = self._get_inserted_row()
        uid = row["notification_delivery_id"]
        # Must parse as a valid UUID
        assert uuid.UUID(uid)

    def test_c7_error_message_none_on_success(self):
        assert self._get_inserted_row()["error_message"] is None

    def test_c8_error_message_populated_on_failure(self):
        db = _make_db()
        result = _make_result(attempts=[
            ChannelAttempt(channel_type="line", channel_id="LT", success=False, error="conn refused"),
        ])
        write_delivery_log(db=db, result=result, tenant_id="T1")
        inserted = db.table.return_value.insert.call_args[0][0]
        assert inserted["error_message"] == "conn refused"


# ---------------------------------------------------------------------------
# Group D — return value
# ---------------------------------------------------------------------------

class TestGroupDReturnValue:

    def test_d1_returns_count_of_successful_writes(self):
        db = _make_db()
        result = _make_result(attempts=[
            ChannelAttempt(channel_type="line", channel_id="LT", success=True),
            ChannelAttempt(channel_type="fcm", channel_id="FT", success=True),
        ])
        count = write_delivery_log(db=db, result=result, tenant_id="T1")
        assert count == 2

    def test_d2_returns_zero_for_empty_channels(self):
        db = _make_db()
        result = DispatchResult(sent=False, user_id="U1", channels=[])
        count = write_delivery_log(db=db, result=result, tenant_id="T1")
        assert count == 0

    def test_d3_returns_zero_on_all_failures(self):
        db = _make_db(insert_raises=True)
        result = _make_result()
        count = write_delivery_log(db=db, result=result, tenant_id="T1")
        assert count == 0


# ---------------------------------------------------------------------------
# Group E — sla_dispatch_bridge: write_delivery_log called after dispatch
# ---------------------------------------------------------------------------

class TestGroupEBridgeWiring:

    def _run_bridge(self, write_mock, tenant_id: str = "T1"):
        """Helper: run dispatch_escalations with patched internals."""
        from tasks.sla_engine import EscalationAction
        from channels.sla_dispatch_bridge import dispatch_escalations
        from channels.notification_dispatcher import DispatchResult, ChannelAttempt

        action = EscalationAction(
            action_type="notify_ops",
            target="ops",
            task_id="T-001",
            property_id="P-1",
            reason="ACK_SLA_BREACH",
            request_id="REQ-1",
        )
        fake_dispatch_result = DispatchResult(
            sent=True,
            user_id="U-1",
            channels=[ChannelAttempt(channel_type="line", channel_id="LT", success=True)],
        )
        db = MagicMock()
        with patch("channels.sla_dispatch_bridge._resolve_users", return_value=["U-1"]), \
             patch("channels.sla_dispatch_bridge.dispatch_notification", return_value=fake_dispatch_result), \
             patch("channels.sla_dispatch_bridge.write_delivery_log", write_mock):
            results = dispatch_escalations(db=db, tenant_id=tenant_id, actions=[action])
        return results

    def test_e1_write_delivery_log_called_after_dispatch(self):
        mock_write = MagicMock()
        self._run_bridge(mock_write)
        assert mock_write.call_count >= 1

    def test_e2_write_delivery_log_receives_tenant_id(self):
        mock_write = MagicMock()
        self._run_bridge(mock_write, tenant_id="MYTENANT")
        _, kwargs = mock_write.call_args
        assert kwargs["tenant_id"] == "MYTENANT"

    def test_e3_write_delivery_log_receives_task_id(self):
        mock_write = MagicMock()
        self._run_bridge(mock_write)
        _, kwargs = mock_write.call_args
        assert kwargs["task_id"] == "T-001"

    def test_e4_write_delivery_log_receives_trigger_reason(self):
        mock_write = MagicMock()
        self._run_bridge(mock_write)
        _, kwargs = mock_write.call_args
        assert kwargs["trigger_reason"] == "ACK_SLA_BREACH"


# ---------------------------------------------------------------------------
# Group F — delivery log error does not affect dispatch
# ---------------------------------------------------------------------------

class TestGroupFDeliveryLogErrorIsolation:

    def test_f1_write_delivery_log_raising_does_not_affect_bridge_result(self):
        from tasks.sla_engine import EscalationAction
        from channels.sla_dispatch_bridge import dispatch_escalations

        action = EscalationAction(
            action_type="notify_ops",
            target="ops",
            task_id="T-002",
            property_id="P-1",
            reason="ACK_SLA_BREACH",
            request_id="REQ-2",
        )
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.eq.return_value.in_.return_value.execute.return_value.data = [
            {"user_id": "U-2"}
        ]
        db.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
            {"channel_type": "line", "channel_id": "LT"}
        ]

        with patch("channels.sla_dispatch_bridge.write_delivery_log") as mock_write:
            mock_write.side_effect = RuntimeError("DB exploded")
            # Must not raise, must return a BridgeResult
            results = dispatch_escalations(db=db, tenant_id="T1", actions=[action])

        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0].task_id == "T-002"
