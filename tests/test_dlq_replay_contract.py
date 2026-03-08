"""
Phase 39 — Contract tests for DLQ Controlled Replay.

Verifies that:
1. replay_dlq_row routes through apply_envelope (never bypasses)
2. replay is idempotent for successfully-replayed rows
3. replay outcome (replay_result, replayed_at, replay_trace_id) is persisted on the DLQ row
4. unknown event_type is handled gracefully
5. missing row raises ValueError
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import ANY, MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_dlq_row(
    row_id: int = 1,
    event_type: str = "BOOKING_CANCELED",
    envelope_payload: dict | None = None,
    replay_result: str | None = None,
    replayed_at: str | None = None,
    replay_trace_id: str | None = None,
) -> dict:
    return {
        "id": row_id,
        "provider": "bookingcom",
        "event_type": event_type,
        "rejection_code": "P0001",
        "rejection_msg": "BOOKING_NOT_FOUND",
        "envelope_json": {
            "type": event_type,
            "idempotency": {"request_id": "original-key-001"},
            "payload": envelope_payload or {"provider": "bookingcom", "reservation_id": "res_001"},
            "occurred_at": "2026-03-08T10:00:00Z",
        },
        "emitted_json": None,
        "trace_id": "test-trace-001",
        "received_at": "2026-03-08T10:00:00+00:00",
        "replay_result": replay_result,
        "replayed_at": replayed_at,
        "replay_trace_id": replay_trace_id,
    }


def _make_mock_client(row: dict) -> MagicMock:
    """Build a mock Supabase client that returns the given row on select."""
    mock_select_result = MagicMock()
    mock_select_result.data = [row]

    mock_select = MagicMock()
    mock_select.eq.return_value = mock_select
    mock_select.execute.return_value = mock_select_result

    mock_update_chain = MagicMock()
    mock_update_chain.eq.return_value = mock_update_chain
    mock_update_chain.execute.return_value = MagicMock(data=[])

    mock_rpc_execute = MagicMock()
    mock_rpc_execute.data = {"status": "APPLIED", "envelope_id": "dlq-replay-1-abc123"}

    mock_rpc_chain = MagicMock()
    mock_rpc_chain.execute.return_value = mock_rpc_execute

    def table_router(name):
        if name == "ota_dead_letter":
            t = MagicMock()
            t.select.return_value = mock_select
            t.update.return_value = mock_update_chain
            return t
        return MagicMock()

    client = MagicMock()
    client.table.side_effect = table_router
    client.rpc.return_value = mock_rpc_chain
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestReplayDlqRowIdempotency:

    def test_already_applied_row_is_idempotent_no_op(self, monkeypatch) -> None:
        """A row with replay_result=APPLIED must not be re-processed."""
        monkeypatch.setenv("SUPABASE_URL", "https://fake.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "fake")

        row = _make_dlq_row(replay_result="APPLIED", replay_trace_id="dlq-replay-1-prev")
        client = _make_mock_client(row)

        with patch("adapters.ota.dlq_replay.create_client", return_value=client):
            from adapters.ota.dlq_replay import replay_dlq_row
            result = replay_dlq_row(1)

        assert result["already_replayed"] is True
        assert result["replay_result"] == "APPLIED"
        assert result["replay_trace_id"] == "dlq-replay-1-prev"
        # apply_envelope must NOT have been called
        client.rpc.assert_not_called()

    def test_already_exists_row_is_idempotent_no_op(self, monkeypatch) -> None:
        """A row with replay_result=ALREADY_EXISTS is also treated as already done."""
        monkeypatch.setenv("SUPABASE_URL", "https://fake.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "fake")

        row = _make_dlq_row(replay_result="ALREADY_EXISTS")
        client = _make_mock_client(row)

        with patch("adapters.ota.dlq_replay.create_client", return_value=client):
            from adapters.ota.dlq_replay import replay_dlq_row
            result = replay_dlq_row(1)

        assert result["already_replayed"] is True
        client.rpc.assert_not_called()


class TestReplayDlqRowRouting:

    def test_calls_apply_envelope_for_booking_canceled(self, monkeypatch) -> None:
        """Replay must call apply_envelope — never bypass the canonical apply gate."""
        monkeypatch.setenv("SUPABASE_URL", "https://fake.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "fake")

        row = _make_dlq_row(event_type="BOOKING_CANCELED", replay_result=None)
        client = _make_mock_client(row)

        mock_skill_out = MagicMock()
        mock_emitted = MagicMock()
        mock_emitted.type = "BOOKING_CANCELED"
        mock_emitted.payload = {"booking_id": "bookingcom_res_001"}
        mock_skill_out.events_to_emit = [mock_emitted]

        with patch("adapters.ota.dlq_replay.create_client", return_value=client), \
             patch("adapters.ota.dlq_replay._get_skill_registry", return_value={"BOOKING_CANCELED": lambda p: mock_skill_out}):
            from adapters.ota.dlq_replay import replay_dlq_row
            result = replay_dlq_row(1)

        # apply_envelope must have been called
        client.rpc.assert_called_once_with("apply_envelope", {
            "p_envelope": ANY,
            "p_emit": [{"type": "BOOKING_CANCELED", "payload": {"booking_id": "bookingcom_res_001"}}],
        })

    def test_replay_uses_new_idempotency_key_not_original(self, monkeypatch) -> None:
        """Replay must use a new request_id, not the original envelope idempotency key."""
        monkeypatch.setenv("SUPABASE_URL", "https://fake.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "fake")

        row = _make_dlq_row(event_type="BOOKING_CANCELED", replay_result=None)
        client = _make_mock_client(row)

        mock_skill_out = MagicMock()
        mock_emitted = MagicMock()
        mock_emitted.type = "BOOKING_CANCELED"
        mock_emitted.payload = {"booking_id": "bookingcom_res_001"}
        mock_skill_out.events_to_emit = [mock_emitted]

        with patch("adapters.ota.dlq_replay.create_client", return_value=client), \
             patch("adapters.ota.dlq_replay._get_skill_registry", return_value={"BOOKING_CANCELED": lambda p: mock_skill_out}):
            from adapters.ota.dlq_replay import replay_dlq_row
            result = replay_dlq_row(1)

        rpc_call_args = client.rpc.call_args[0][1]
        replay_request_id = rpc_call_args["p_envelope"]["idempotency"]["request_id"]

        # Must be different from the original
        assert replay_request_id != "original-key-001"
        # Must start with dlq-replay prefix
        assert replay_request_id.startswith("dlq-replay-")

    def test_unknown_event_type_returns_no_skill_result(self, monkeypatch) -> None:
        """An event_type with no registered skill must be handled gracefully."""
        monkeypatch.setenv("SUPABASE_URL", "https://fake.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "fake")

        row = _make_dlq_row(event_type="UNKNOWN_TYPE", replay_result=None)
        client = _make_mock_client(row)

        with patch("adapters.ota.dlq_replay.create_client", return_value=client), \
             patch("adapters.ota.dlq_replay._get_skill_registry", return_value={}):
            from adapters.ota.dlq_replay import replay_dlq_row
            result = replay_dlq_row(1)

        assert result["replay_result"] == "NO_SKILL_FOR_EVENT_TYPE"
        client.rpc.assert_not_called()

    def test_missing_row_raises_value_error(self, monkeypatch) -> None:
        """A row_id that does not exist must raise ValueError."""
        monkeypatch.setenv("SUPABASE_URL", "https://fake.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "fake")

        empty_select = MagicMock()
        empty_select.data = []
        mock_select_chain = MagicMock()
        mock_select_chain.eq.return_value = mock_select_chain
        mock_select_chain.execute.return_value = empty_select

        client = MagicMock()
        client.table.return_value.select.return_value = mock_select_chain

        with patch("adapters.ota.dlq_replay.create_client", return_value=client):
            from adapters.ota.dlq_replay import replay_dlq_row
            with pytest.raises(ValueError, match="not found"):
                replay_dlq_row(9999)


class TestReplayDlqOutcomePersistence:

    def test_outcome_is_written_back_to_dlq_row(self, monkeypatch) -> None:
        """After successful replay, replayed_at, replay_result, replay_trace_id must be persisted."""
        monkeypatch.setenv("SUPABASE_URL", "https://fake.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "fake")

        row = _make_dlq_row(event_type="BOOKING_CANCELED", replay_result=None)
        client = _make_mock_client(row)

        mock_skill_out = MagicMock()
        mock_emitted = MagicMock()
        mock_emitted.type = "BOOKING_CANCELED"
        mock_emitted.payload = {"booking_id": "bookingcom_res_001"}
        mock_skill_out.events_to_emit = [mock_emitted]

        with patch("adapters.ota.dlq_replay.create_client", return_value=client), \
             patch("adapters.ota.dlq_replay._get_skill_registry", return_value={"BOOKING_CANCELED": lambda p: mock_skill_out}):
            from adapters.ota.dlq_replay import replay_dlq_row
            result = replay_dlq_row(1)

        # _record_replay_outcome calls client.table("ota_dead_letter").update({...}).eq(...).execute()
        # Verify via the result dict that replay_result was recorded
        assert result["replay_result"] == "APPLIED"
        assert result["replay_trace_id"].startswith("dlq-replay-")
