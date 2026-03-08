"""
Phase 43 — Contract tests for booking_status.get_booking_status.

Verifies that:
1. unknown booking_id returns None
2. active booking returns 'active'
3. canceled booking returns 'canceled'
4. client injection works (no live Supabase needed)
5. function is read-only — never calls .insert(), .update(), .delete()
"""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest


def _make_client(rows: list) -> MagicMock:
    mock_result = MagicMock()
    mock_result.data = rows

    mock_eq = MagicMock()
    mock_eq.execute.return_value = mock_result

    mock_select = MagicMock()
    mock_select.eq.return_value = mock_eq

    mock_table = MagicMock()
    mock_table.select.return_value = mock_select

    client = MagicMock()
    client.table.return_value = mock_table
    return client


# ---------------------------------------------------------------------------
# Status reads
# ---------------------------------------------------------------------------

class TestGetBookingStatus:

    def test_unknown_booking_returns_none(self) -> None:
        client = _make_client([])
        from adapters.ota.booking_status import get_booking_status
        result = get_booking_status("does_not_exist", client)
        assert result is None

    def test_active_booking_returns_active(self) -> None:
        client = _make_client([{"booking_id": "bookingcom_res_001", "status": "active"}])
        from adapters.ota.booking_status import get_booking_status
        result = get_booking_status("bookingcom_res_001", client)
        assert result == "active"

    def test_canceled_booking_returns_canceled(self) -> None:
        client = _make_client([{"booking_id": "bookingcom_res_002", "status": "canceled"}])
        from adapters.ota.booking_status import get_booking_status
        result = get_booking_status("bookingcom_res_002", client)
        assert result == "canceled"

    def test_none_status_field_returns_none(self) -> None:
        """A row without status set returns None gracefully."""
        client = _make_client([{"booking_id": "bookingcom_res_003", "status": None}])
        from adapters.ota.booking_status import get_booking_status
        result = get_booking_status("bookingcom_res_003", client)
        assert result is None


# ---------------------------------------------------------------------------
# Read-only guard
# ---------------------------------------------------------------------------

class TestGetBookingStatusIsReadOnly:

    def test_never_calls_insert(self) -> None:
        client = _make_client([])
        from adapters.ota.booking_status import get_booking_status
        get_booking_status("any_id", client)
        client.table.return_value.insert.assert_not_called()

    def test_never_calls_update(self) -> None:
        client = _make_client([])
        from adapters.ota.booking_status import get_booking_status
        get_booking_status("any_id", client)
        client.table.return_value.update.assert_not_called()

    def test_never_calls_delete(self) -> None:
        client = _make_client([])
        from adapters.ota.booking_status import get_booking_status
        get_booking_status("any_id", client)
        client.table.return_value.delete.assert_not_called()

    def test_queries_booking_state_table(self) -> None:
        """Must read from booking_state, not any other table."""
        client = _make_client([])
        from adapters.ota.booking_status import get_booking_status
        get_booking_status("any_id", client)
        client.table.assert_called_once_with("booking_state")

    def test_selects_status_field(self) -> None:
        """Must select the status field."""
        client = _make_client([])
        from adapters.ota.booking_status import get_booking_status
        get_booking_status("any_id", client)
        client.table.return_value.select.assert_called_once_with("booking_id, status")
