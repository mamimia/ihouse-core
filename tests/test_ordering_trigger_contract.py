"""
Phase 45 — Contract tests for Ordering Buffer Auto-Trigger.

Verifies that:
1. No buffered events → 0 replayed, replay_dlq_row not called
2. One waiting row → replay_dlq_row called, mark_replayed called
3. replay failure → logged to stderr, counted as failed, not raised
4. correct booking_id passed to get_buffered_events
5. returns correct summary dict
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch, call
import pytest


def _waiting_row(buffer_id: int, dlq_row_id: int, booking_id: str) -> dict:
    return {
        "id": buffer_id,
        "dlq_row_id": dlq_row_id,
        "booking_id": booking_id,
        "event_type": "BOOKING_CANCELED",
        "status": "waiting",
    }


class TestTriggerOrderedReplay:

    def test_empty_buffer_returns_zero_replayed(self) -> None:
        with patch("adapters.ota.ordering_trigger.get_buffered_events", return_value=[]) as mock_buf, \
             patch("adapters.ota.ordering_trigger.replay_dlq_row") as mock_replay:

            from adapters.ota.ordering_trigger import trigger_ordered_replay
            result = trigger_ordered_replay("bookingcom_res_001")

            assert result["replayed"] == 0
            assert result["failed"] == 0
            assert result["results"] == []
            mock_replay.assert_not_called()

    def test_one_waiting_row_calls_replay_and_mark(self) -> None:
        row = _waiting_row(buffer_id=7, dlq_row_id=3, booking_id="bookingcom_res_002")

        with patch("adapters.ota.ordering_trigger.get_buffered_events", return_value=[row]), \
             patch("adapters.ota.ordering_trigger.replay_dlq_row", return_value={"status": "APPLIED"}) as mock_replay, \
             patch("adapters.ota.ordering_trigger.mark_replayed") as mock_mark:

            from adapters.ota.ordering_trigger import trigger_ordered_replay
            result = trigger_ordered_replay("bookingcom_res_002")

            mock_replay.assert_called_once_with(3)
            mock_mark.assert_called_once_with(7, None)  # client=None
            assert result["replayed"] == 1
            assert result["failed"] == 0

    def test_correct_booking_id_passed_to_buffer(self) -> None:
        with patch("adapters.ota.ordering_trigger.get_buffered_events", return_value=[]) as mock_buf:
            from adapters.ota.ordering_trigger import trigger_ordered_replay
            trigger_ordered_replay("bookingcom_res_xyz")
            mock_buf.assert_called_once_with("bookingcom_res_xyz", None)

    def test_replay_failure_is_logged_not_raised(self, capsys) -> None:
        row = _waiting_row(buffer_id=9, dlq_row_id=5, booking_id="bookingcom_res_003")

        with patch("adapters.ota.ordering_trigger.get_buffered_events", return_value=[row]), \
             patch("adapters.ota.ordering_trigger.replay_dlq_row", side_effect=ValueError("DB error")), \
             patch("adapters.ota.ordering_trigger.mark_replayed") as mock_mark:

            from adapters.ota.ordering_trigger import trigger_ordered_replay
            result = trigger_ordered_replay("bookingcom_res_003")

            assert result["failed"] == 1
            assert result["replayed"] == 0
            mock_mark.assert_not_called()
            captured = capsys.readouterr()
            assert "ORDERING TRIGGER" in captured.err

    def test_multiple_rows_processes_all(self) -> None:
        rows = [
            _waiting_row(buffer_id=1, dlq_row_id=10, booking_id="bookingcom_test"),
            _waiting_row(buffer_id=2, dlq_row_id=11, booking_id="bookingcom_test"),
        ]

        with patch("adapters.ota.ordering_trigger.get_buffered_events", return_value=rows), \
             patch("adapters.ota.ordering_trigger.replay_dlq_row", return_value={"status": "APPLIED"}), \
             patch("adapters.ota.ordering_trigger.mark_replayed"):

            from adapters.ota.ordering_trigger import trigger_ordered_replay
            result = trigger_ordered_replay("bookingcom_test")
            assert result["replayed"] == 2
            assert len(result["results"]) == 2

    def test_partial_failure_continues(self) -> None:
        """One row fails → continues to next row → replayed=1, failed=1."""
        rows = [
            _waiting_row(buffer_id=1, dlq_row_id=10, booking_id="bookingcom_test"),
            _waiting_row(buffer_id=2, dlq_row_id=11, booking_id="bookingcom_test"),
        ]

        replay_returns = [ValueError("first fails"), {"status": "APPLIED"}]

        def side_effect(dlq_id):
            val = replay_returns.pop(0)
            if isinstance(val, Exception):
                raise val
            return val

        with patch("adapters.ota.ordering_trigger.get_buffered_events", return_value=rows), \
             patch("adapters.ota.ordering_trigger.replay_dlq_row", side_effect=side_effect), \
             patch("adapters.ota.ordering_trigger.mark_replayed"):

            from adapters.ota.ordering_trigger import trigger_ordered_replay
            result = trigger_ordered_replay("bookingcom_test")
            assert result["replayed"] == 1
            assert result["failed"] == 1

    def test_result_contains_booking_id(self) -> None:
        with patch("adapters.ota.ordering_trigger.get_buffered_events", return_value=[]):
            from adapters.ota.ordering_trigger import trigger_ordered_replay
            result = trigger_ordered_replay("bookingcom_res_zzz")
            assert result["booking_id"] == "bookingcom_res_zzz"
