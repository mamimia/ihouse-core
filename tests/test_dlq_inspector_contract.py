"""
Phase 40 — Contract tests for DLQ Inspector.

Verifies that:
1. get_pending_count correctly counts rows NOT in applied statuses
2. get_replayed_count correctly counts rows IN applied statuses
3. get_rejection_breakdown returns and passes through summary view data
4. all functions handle empty DLQ gracefully (return 0 or [])
5. all functions accept an injected client (no real Supabase needed)
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


def _make_client(rows: list) -> MagicMock:
    """Build a minimal mock Supabase client returning the given rows on select."""
    mock_result = MagicMock()
    mock_result.data = rows

    mock_select = MagicMock()
    mock_select.execute.return_value = mock_result

    mock_table = MagicMock()
    mock_table.select.return_value = mock_select

    client = MagicMock()
    client.table.return_value = mock_table
    return client


# ---------------------------------------------------------------------------
# get_pending_count
# ---------------------------------------------------------------------------

class TestGetPendingCount:

    def test_all_pending_when_no_replays(self) -> None:
        rows = [
            {"id": 1, "replay_result": None},
            {"id": 2, "replay_result": None},
            {"id": 3, "replay_result": "REJECTED:BOOKING_NOT_FOUND"},
        ]
        from adapters.ota.dlq_inspector import get_pending_count
        assert get_pending_count(_make_client(rows)) == 3

    def test_none_pending_when_all_applied(self) -> None:
        rows = [
            {"id": 1, "replay_result": "APPLIED"},
            {"id": 2, "replay_result": "ALREADY_EXISTS"},
        ]
        from adapters.ota.dlq_inspector import get_pending_count
        assert get_pending_count(_make_client(rows)) == 0

    def test_mixed_pending_and_applied(self) -> None:
        rows = [
            {"id": 1, "replay_result": "APPLIED"},
            {"id": 2, "replay_result": None},
            {"id": 3, "replay_result": "BOOKING_NOT_FOUND"},
            {"id": 4, "replay_result": "ALREADY_APPLIED"},
        ]
        from adapters.ota.dlq_inspector import get_pending_count
        assert get_pending_count(_make_client(rows)) == 2  # id 2 and 3

    def test_empty_dlq_returns_zero(self) -> None:
        from adapters.ota.dlq_inspector import get_pending_count
        assert get_pending_count(_make_client([])) == 0

    def test_none_data_returns_zero(self) -> None:
        mock_result = MagicMock()
        mock_result.data = None
        mock_select = MagicMock()
        mock_select.execute.return_value = mock_result
        client = MagicMock()
        client.table.return_value.select.return_value = mock_select

        from adapters.ota.dlq_inspector import get_pending_count
        assert get_pending_count(client) == 0


# ---------------------------------------------------------------------------
# get_replayed_count
# ---------------------------------------------------------------------------

class TestGetReplayedCount:

    def test_all_replayed_when_all_applied(self) -> None:
        rows = [
            {"id": 1, "replay_result": "APPLIED"},
            {"id": 2, "replay_result": "ALREADY_EXISTS"},
            {"id": 3, "replay_result": "ALREADY_APPLIED"},
            {"id": 4, "replay_result": "ALREADY_EXISTS_BUSINESS"},
        ]
        from adapters.ota.dlq_inspector import get_replayed_count
        assert get_replayed_count(_make_client(rows)) == 4

    def test_none_replayed_when_all_pending(self) -> None:
        rows = [
            {"id": 1, "replay_result": None},
            {"id": 2, "replay_result": "REJECTED:BOOKING_NOT_FOUND"},
        ]
        from adapters.ota.dlq_inspector import get_replayed_count
        assert get_replayed_count(_make_client(rows)) == 0

    def test_empty_dlq_returns_zero(self) -> None:
        from adapters.ota.dlq_inspector import get_replayed_count
        assert get_replayed_count(_make_client([])) == 0


# ---------------------------------------------------------------------------
# get_rejection_breakdown
# ---------------------------------------------------------------------------

class TestGetRejectionBreakdown:

    def test_passes_through_summary_view_data(self) -> None:
        summary_rows = [
            {"event_type": "BOOKING_CANCELED", "rejection_code": "P0001", "total": 5, "pending": 3, "replayed": 2},
            {"event_type": "BOOKING_CREATED",  "rejection_code": "OVERLAP_NOT_ALLOWED", "total": 1, "pending": 1, "replayed": 0},
        ]
        from adapters.ota.dlq_inspector import get_rejection_breakdown
        result = get_rejection_breakdown(_make_client(summary_rows))
        assert result == summary_rows

    def test_empty_dlq_returns_empty_list(self) -> None:
        from adapters.ota.dlq_inspector import get_rejection_breakdown
        assert get_rejection_breakdown(_make_client([])) == []

    def test_queries_ota_dlq_summary_view(self) -> None:
        """Inspector must query the ota_dlq_summary view, not ota_dead_letter directly."""
        client = _make_client([])

        from adapters.ota.dlq_inspector import get_rejection_breakdown
        get_rejection_breakdown(client)

        client.table.assert_called_once_with("ota_dlq_summary")
