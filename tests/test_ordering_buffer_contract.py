"""
Phase 44 — Contract tests for OTA Ordering Buffer.

Verifies that:
1. buffer_event writes a row with correct fields and status='waiting'
2. get_buffered_events returns only 'waiting' rows for a booking_id
3. get_buffered_events returns empty list for unknown booking_id
4. mark_replayed updates status to 'replayed'
5. get_buffered_events after mark_replayed returns empty (no longer waiting)
6. buffer_event returns the new row id (int)
"""
from __future__ import annotations

from unittest.mock import MagicMock, call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_insert_client(row_id: int = 1) -> MagicMock:
    """Client that returns a row with the given id on insert."""
    mock_insert_result = MagicMock()
    mock_insert_result.data = [{"id": row_id, "status": "waiting"}]

    mock_insert_chain = MagicMock()
    mock_insert_chain.execute.return_value = mock_insert_result

    client = MagicMock()
    client.table.return_value.insert.return_value = mock_insert_chain
    return client


def _make_select_client(rows: list) -> MagicMock:
    """Client that returns given rows on select."""
    mock_select_result = MagicMock()
    mock_select_result.data = rows

    mock_eq2 = MagicMock()
    mock_eq2.execute.return_value = mock_select_result

    mock_eq1 = MagicMock()
    mock_eq1.eq.return_value = mock_eq2

    mock_select = MagicMock()
    mock_select.eq.return_value = mock_eq1

    client = MagicMock()
    client.table.return_value.select.return_value = mock_select
    return client


def _make_update_client() -> MagicMock:
    """Client that accepts update calls."""
    mock_update_result = MagicMock()
    mock_update_result.data = []

    mock_update_chain = MagicMock()
    mock_update_chain.eq.return_value = mock_update_chain
    mock_update_chain.execute.return_value = mock_update_result

    client = MagicMock()
    client.table.return_value.update.return_value = mock_update_chain
    return client


# ---------------------------------------------------------------------------
# buffer_event
# ---------------------------------------------------------------------------

class TestBufferEvent:

    def test_returns_new_row_id(self) -> None:
        client = _make_insert_client(row_id=42)
        from adapters.ota.ordering_buffer import buffer_event
        result = buffer_event(99, "bookingcom_res_001", "BOOKING_CANCELED", client)
        assert result == 42

    def test_inserts_into_ordering_buffer_table(self) -> None:
        client = _make_insert_client()
        from adapters.ota.ordering_buffer import buffer_event
        buffer_event(5, "bookingcom_res_001", "BOOKING_CANCELED", client)
        client.table.assert_called_with("ota_ordering_buffer")

    def test_inserts_correct_fields(self) -> None:
        client = _make_insert_client()
        from adapters.ota.ordering_buffer import buffer_event
        buffer_event(7, "bookingcom_res_002", "BOOKING_CANCELED", client)
        insert_payload = client.table.return_value.insert.call_args[0][0]
        assert insert_payload["dlq_row_id"] == 7
        assert insert_payload["booking_id"] == "bookingcom_res_002"
        assert insert_payload["event_type"] == "BOOKING_CANCELED"
        assert insert_payload["status"] == "waiting"


# ---------------------------------------------------------------------------
# get_buffered_events
# ---------------------------------------------------------------------------

class TestGetBufferedEvents:

    def test_returns_waiting_rows_for_booking_id(self) -> None:
        rows = [
            {"id": 1, "booking_id": "bookingcom_res_001", "event_type": "BOOKING_CANCELED", "status": "waiting"},
        ]
        client = _make_select_client(rows)
        from adapters.ota.ordering_buffer import get_buffered_events
        result = get_buffered_events("bookingcom_res_001", client)
        assert result == rows

    def test_returns_empty_for_unknown_booking(self) -> None:
        client = _make_select_client([])
        from adapters.ota.ordering_buffer import get_buffered_events
        result = get_buffered_events("does_not_exist", client)
        assert result == []

    def test_filters_by_status_waiting(self) -> None:
        """Must filter status='waiting', not return replayed rows."""
        client = _make_select_client([])
        from adapters.ota.ordering_buffer import get_buffered_events
        get_buffered_events("bookingcom_res_001", client)
        # The second .eq() call must filter by status=waiting
        mock_select = client.table.return_value.select.return_value
        mock_eq1 = mock_select.eq.return_value
        mock_eq1.eq.assert_called_once_with("status", "waiting")

    def test_queries_correct_table(self) -> None:
        client = _make_select_client([])
        from adapters.ota.ordering_buffer import get_buffered_events
        get_buffered_events("any_id", client)
        client.table.assert_called_with("ota_ordering_buffer")


# ---------------------------------------------------------------------------
# mark_replayed
# ---------------------------------------------------------------------------

class TestMarkReplayed:

    def test_updates_status_to_replayed(self) -> None:
        client = _make_update_client()
        from adapters.ota.ordering_buffer import mark_replayed
        mark_replayed(3, client)
        client.table.return_value.update.assert_called_once_with({"status": "replayed"})

    def test_filters_by_buffer_id(self) -> None:
        client = _make_update_client()
        from adapters.ota.ordering_buffer import mark_replayed
        mark_replayed(3, client)
        client.table.return_value.update.return_value.eq.assert_called_once_with("id", 3)

    def test_updates_ordering_buffer_table(self) -> None:
        client = _make_update_client()
        from adapters.ota.ordering_buffer import mark_replayed
        mark_replayed(3, client)
        client.table.assert_called_with("ota_ordering_buffer")
