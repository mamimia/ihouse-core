"""
Contract Tests — SLA Dispatch Bridge (Phase 177)

Tests for src/channels/sla_dispatch_bridge.py

Groups:
  A — dispatch_escalations happy path
  B — _resolve_users target routing
  C — _build_message shape
  D — error isolation (DB errors, adapter errors, bad target)
  E — BridgeResult field contract
"""
from __future__ import annotations

import sys
import os
from unittest.mock import MagicMock, call, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from channels.sla_dispatch_bridge import (
    BridgeResult,
    _build_message,
    _resolve_users,
    dispatch_escalations,
)
from channels.notification_dispatcher import (
    ChannelAttempt,
    DispatchResult,
    NotificationMessage,
)
from tasks.sla_engine import EscalationAction


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _action(
    action_type="notify_ops",
    target="ops",
    reason="ACK_SLA_BREACH",
    task_id="task-001",
    property_id="prop-001",
    request_id="req-001",
) -> EscalationAction:
    return EscalationAction(
        action_type=action_type,
        target=target,
        reason=reason,
        task_id=task_id,
        property_id=property_id,
        request_id=request_id,
    )


def _db_with_users(user_ids: list[str]):
    """Mock DB for tenant_permissions.
    Actual chain: .table().select().eq('tenant_id',...).in_('role',[...]).execute()
    """
    db = MagicMock()
    result = MagicMock()
    result.data = [{"user_id": uid} for uid in user_ids]
    db.table.return_value.select.return_value.eq.return_value.in_.return_value.execute.return_value = result
    return db


def _db_error():
    """Mock DB that raises on .execute()."""
    db = MagicMock()
    db.table.side_effect = RuntimeError("DB down")
    return db


def _ok_dispatch(db, tenant_id, user_id, message, adapters=None):
    return DispatchResult(sent=True, user_id=user_id, channels=[
        ChannelAttempt(channel_type="line", channel_id="U123", success=True)
    ])


def _fail_dispatch(db, tenant_id, user_id, message, adapters=None):
    return DispatchResult(sent=False, user_id=user_id, channels=[
        ChannelAttempt(channel_type="line", channel_id="U123", success=False, error="timeout")
    ])


# ---------------------------------------------------------------------------
# Group A — Happy path
# ---------------------------------------------------------------------------

class TestGroupAHappyPath:

    def test_a1_single_action_single_user_returns_one_result(self):
        """A1: One action, one ops user → one BridgeResult with one DispatchResult."""
        db = _db_with_users(["user-A"])
        with patch("channels.sla_dispatch_bridge.dispatch_notification", side_effect=_ok_dispatch):
            results = dispatch_escalations(db, "tenant-1", [_action()])
        assert len(results) == 1
        assert results[0].task_id == "task-001"
        assert results[0].dispatched_to == ["user-A"]
        assert len(results[0].results) == 1
        assert results[0].results[0].sent is True

    def test_a2_single_action_two_users_dispatches_twice(self):
        """A2: One action, two ops users → dispatch called twice."""
        db = _db_with_users(["user-A", "user-B"])
        calls: list = []

        def _capture(db, tenant_id, user_id, message, adapters=None):
            calls.append(user_id)
            return DispatchResult(sent=True, user_id=user_id)

        with patch("channels.sla_dispatch_bridge.dispatch_notification", side_effect=_capture):
            results = dispatch_escalations(db, "tenant-1", [_action()])

        assert set(calls) == {"user-A", "user-B"}
        assert len(results[0].dispatched_to) == 2

    def test_a3_two_actions_returns_two_results(self):
        """A3: Two actions → two BridgeResults."""
        db = _db_with_users(["user-A"])
        with patch("channels.sla_dispatch_bridge.dispatch_notification", side_effect=_ok_dispatch):
            results = dispatch_escalations(db, "tenant-1", [
                _action(action_type="notify_ops", target="ops"),
                _action(action_type="notify_admin", target="admin", reason="COMPLETION_SLA_BREACH"),
            ])
        assert len(results) == 2

    def test_a4_empty_actions_returns_empty_list(self):
        """A4: Empty actions list → [] immediately, no DB call."""
        db = MagicMock()
        results = dispatch_escalations(db, "tenant-1", [])
        assert results == []
        db.table.assert_not_called()

    def test_a5_no_users_resolved_dispatched_to_empty(self):
        """A5: No users in tenant_permissions → dispatched_to=[], results=[]."""
        db = _db_with_users([])
        with patch("channels.sla_dispatch_bridge.dispatch_notification") as mock_disp:
            results = dispatch_escalations(db, "tenant-1", [_action()])
        assert results[0].dispatched_to == []
        assert results[0].results == []
        mock_disp.assert_not_called()

    def test_a6_bridge_result_action_type_propagated(self):
        """A6: action_type from EscalationAction is in BridgeResult."""
        db = _db_with_users(["user-A"])
        with patch("channels.sla_dispatch_bridge.dispatch_notification", side_effect=_ok_dispatch):
            results = dispatch_escalations(db, "tenant-1", [
                _action(action_type="notify_admin", target="admin")
            ])
        assert results[0].action_type == "notify_admin"

    def test_a7_reason_propagated(self):
        """A7: reason field preserved in BridgeResult."""
        db = _db_with_users(["user-A"])
        with patch("channels.sla_dispatch_bridge.dispatch_notification", side_effect=_ok_dispatch):
            results = dispatch_escalations(db, "tenant-1", [
                _action(reason="COMPLETION_SLA_BREACH")
            ])
        assert results[0].reason == "COMPLETION_SLA_BREACH"


# ---------------------------------------------------------------------------
# Group B — _resolve_users routing
# ---------------------------------------------------------------------------

class TestGroupBResolveUsers:

    def test_b1_ops_target_queries_worker_manager_roles(self):
        """B1: target='ops' passes roles ['worker','manager'] to DB."""
        db = _db_with_users([])
        _resolve_users(db, "t1", "ops")
        # Actual query: .table().select().eq('tenant_id',...).in_('role', roles).execute()
        in_mock = db.table.return_value.select.return_value.eq.return_value.in_
        call_args = in_mock.call_args
        assert call_args is not None
        assert call_args[0][0] == "role"
        assert set(call_args[0][1]) == {"worker", "manager"}

    def test_b2_admin_target_queries_admin_role(self):
        """B2: target='admin' passes roles ['admin'] to DB."""
        db = _db_with_users([])
        _resolve_users(db, "t1", "admin")
        in_mock = db.table.return_value.select.return_value.eq.return_value.in_
        call_args = in_mock.call_args
        assert call_args is not None
        assert set(call_args[0][1]) == {"admin"}

    def test_b3_unknown_target_returns_empty(self):
        """B3: target='unknown' → [] without a DB call."""
        db = MagicMock()
        result = _resolve_users(db, "t1", "unknown_role")
        assert result == []

    def test_b4_tenant_id_filter_applied(self):
        """B4: tenant_id is passed as .eq('tenant_id', ...) filter."""
        db = _db_with_users([])
        _resolve_users(db, "tenant-xyz", "ops")
        first_eq_call = db.table.return_value.select.return_value.eq.call_args_list[0]
        assert first_eq_call[0] == ("tenant_id", "tenant-xyz")

    def test_b5_returns_all_user_ids(self):
        """B5: Returns exactly the user_ids from DB rows."""
        db = _db_with_users(["u1", "u2", "u3"])
        result = _resolve_users(db, "t1", "ops")
        assert set(result) == {"u1", "u2", "u3"}

    def test_b6_db_error_returns_empty(self):
        """B6: DB error → returns [] (best-effort)."""
        db = _db_error()
        result = _resolve_users(db, "t1", "ops")
        assert result == []


# ---------------------------------------------------------------------------
# Group C — _build_message shape
# ---------------------------------------------------------------------------

class TestGroupCBuildMessage:

    def _msg(self, **overrides) -> NotificationMessage:
        kw = dict(
            action_type="notify_ops", target="ops",
            reason="ACK_SLA_BREACH", task_id="T-111",
            property_id="P-222", request_id="R-333",
        )
        kw.update(overrides)
        return _build_message(_action(**kw))

    def test_c1_title_contains_reason(self):
        """C1: title contains the breach reason."""
        msg = self._msg(reason="ACK_SLA_BREACH")
        assert "ACK_SLA_BREACH" in msg.title

    def test_c2_title_contains_task_id(self):
        """C2: title contains the task_id."""
        msg = self._msg(task_id="T-777")
        assert "T-777" in msg.title

    def test_c3_body_contains_property_id(self):
        """C3: body contains property_id."""
        msg = self._msg(property_id="P-999")
        assert "P-999" in msg.body

    def test_c4_data_has_required_keys(self):
        """C4: data dict contains task_id, property_id, reason, request_id."""
        msg = self._msg()
        assert {"task_id", "property_id", "reason", "request_id"}.issubset(msg.data)

    def test_c5_data_values_correct(self):
        """C5: data values match the action fields."""
        msg = self._msg(task_id="T1", property_id="P2", reason="R3", request_id="REQ4")
        assert msg.data["task_id"] == "T1"
        assert msg.data["property_id"] == "P2"
        assert msg.data["reason"] == "R3"
        assert msg.data["request_id"] == "REQ4"


# ---------------------------------------------------------------------------
# Group D — Error isolation
# ---------------------------------------------------------------------------

class TestGroupDErrorIsolation:

    def test_d1_dispatch_error_for_one_user_does_not_block_others(self):
        """D1: If dispatch raises for user-A, user-B still gets dispatched."""
        db = _db_with_users(["user-A", "user-B"])
        called: list = []

        def _mixed(db, tenant_id, user_id, message, adapters=None):
            if user_id == "user-A":
                raise RuntimeError("LINE timeout")
            called.append(user_id)
            return DispatchResult(sent=True, user_id=user_id)

        with patch("channels.sla_dispatch_bridge.dispatch_notification", side_effect=_mixed):
            results = dispatch_escalations(db, "t1", [_action()])

        assert "user-B" in called
        # Both users attempted
        assert set(results[0].dispatched_to) == {"user-A", "user-B"}

    def test_d2_dispatch_exception_recorded_as_failed_result(self):
        """D2: dispatch exception → DispatchResult(sent=False) added to results."""
        db = _db_with_users(["user-A"])

        def _raise(db, tenant_id, user_id, message, adapters=None):
            raise RuntimeError("crash")

        with patch("channels.sla_dispatch_bridge.dispatch_notification", side_effect=_raise):
            results = dispatch_escalations(db, "t1", [_action()])

        assert results[0].results[0].sent is False

    def test_d3_db_error_on_resolve_returns_bridge_result_with_empty(self):
        """D3: DB error during _resolve_users → BridgeResult(dispatched_to=[])."""
        db = _db_error()
        with patch("channels.sla_dispatch_bridge.dispatch_notification") as mock_d:
            results = dispatch_escalations(db, "t1", [_action()])
        assert results[0].dispatched_to == []
        mock_d.assert_not_called()

    def test_d4_never_raises(self):
        """D4: dispatch_escalations never raises, even if everything explodes."""
        db = MagicMock()
        db.table.side_effect = Exception("total chaos")
        # Should not raise
        results = dispatch_escalations(db, "t1", [_action()])
        assert isinstance(results, list)

    def test_d5_failed_dispatch_does_not_affect_next_action(self):
        """D5: BridgeResult for second action is independent of first failing."""
        db = _db_with_users(["user-X"])
        call_count = 0

        def _alternating(db, tenant_id, user_id, message, adapters=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("first fails")
            return DispatchResult(sent=True, user_id=user_id)

        with patch("channels.sla_dispatch_bridge.dispatch_notification", side_effect=_alternating):
            results = dispatch_escalations(db, "t1", [
                _action(reason="ACK_SLA_BREACH"),
                _action(reason="COMPLETION_SLA_BREACH"),
            ])

        assert len(results) == 2
        assert results[1].results[0].sent is True


# ---------------------------------------------------------------------------
# Group E — BridgeResult field contract
# ---------------------------------------------------------------------------

class TestGroupEBridgeResultContract:

    def _run_single(self, **action_overrides) -> BridgeResult:
        db = _db_with_users(["user-1"])
        with patch("channels.sla_dispatch_bridge.dispatch_notification", side_effect=_ok_dispatch):
            results = dispatch_escalations(db, "t1", [_action(**action_overrides)])
        return results[0]

    def test_e1_action_type_field(self):
        result = self._run_single(action_type="notify_admin", target="admin")
        assert result.action_type == "notify_admin"

    def test_e2_reason_field(self):
        result = self._run_single(reason="COMPLETION_SLA_BREACH")
        assert result.reason == "COMPLETION_SLA_BREACH"

    def test_e3_task_id_field(self):
        result = self._run_single(task_id="task-E3")
        assert result.task_id == "task-E3"

    def test_e4_dispatched_to_is_list_of_strings(self):
        result = self._run_single()
        assert isinstance(result.dispatched_to, list)
        assert all(isinstance(u, str) for u in result.dispatched_to)

    def test_e5_results_is_list_of_dispatch_results(self):
        result = self._run_single()
        assert isinstance(result.results, list)
        assert all(isinstance(r, DispatchResult) for r in result.results)
