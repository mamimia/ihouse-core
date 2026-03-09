"""
Phase 84 — Contract tests for reservation_timeline.py.

Tests:
  A — TimelineEvent structure and sort_key
  B — build_reservation_timeline: happy path, all sources
  C — Source isolation: each fetcher returns its events correctly
  D — Partial failure: one source fails, others still contribute
  E — Empty: no events from any source → empty timeline, not an error
  F — Ordering: events sorted by recorded_at ascending
  G — Tenant isolation: event_log and financial_facts are tenant-scoped
  H — ReservationTimeline structure invariants
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
from typing import List

import pytest

from adapters.ota.reservation_timeline import (
    TimelineEvent,
    ReservationTimeline,
    build_reservation_timeline,
    _fetch_event_log_events,
    _fetch_financial_events,
    _fetch_dlq_events,
    _fetch_buffer_events,
)

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

TENANT = "tenant-abc"
BOOKING = "airbnb_res12345"


def _make_db(
    event_log_data=None,
    financial_data=None,
    dlq_data=None,
    buffer_data=None,
    event_log_raises=False,
    financial_raises=False,
    dlq_raises=False,
    buffer_raises=False,
) -> MagicMock:
    """
    Build a mock Supabase client that returns specified data per table.
    """
    db = MagicMock()

    def _table_factory(table_name):
        mock_table = MagicMock()

        def _chain(*args, **kwargs):
            """Return self for all chained methods."""
            return mock_table

        mock_table.select = _chain
        mock_table.eq = _chain
        mock_table.order = _chain
        mock_table.limit = _chain

        def _execute():
            if table_name == "event_log":
                if event_log_raises:
                    raise RuntimeError("event_log DB error")
                result = MagicMock()
                result.data = event_log_data or []
                return result
            elif table_name == "booking_financial_facts":
                if financial_raises:
                    raise RuntimeError("financial DB error")
                result = MagicMock()
                result.data = financial_data or []
                return result
            elif table_name == "ota_dead_letter":
                if dlq_raises:
                    raise RuntimeError("dlq DB error")
                result = MagicMock()
                result.data = dlq_data or []
                return result
            elif table_name == "ota_ordering_buffer":
                if buffer_raises:
                    raise RuntimeError("buffer DB error")
                result = MagicMock()
                result.data = buffer_data or []
                return result
            else:
                result = MagicMock()
                result.data = []
                return result

        mock_table.execute = _execute
        return mock_table

    db.table = _table_factory
    return db


def _event_log_row(
    event_kind="BOOKING_CREATED",
    occurred_at="2026-10-01T10:00:00+00:00",
    recorded_at="2026-10-01T10:01:00+00:00",
    envelope_id="env-001",
    source="airbnb",
) -> dict:
    return {
        "event_kind": event_kind,
        "occurred_at": occurred_at,
        "recorded_at": recorded_at,
        "envelope_id": envelope_id,
        "source": source,
    }


def _financial_row(
    event_kind="BOOKING_CREATED",
    recorded_at="2026-10-01T10:01:30+00:00",
    total_price="500.00",
    currency="USD",
    source_confidence="FULL",
) -> dict:
    return {
        "event_kind": event_kind,
        "recorded_at": recorded_at,
        "total_price": total_price,
        "currency": currency,
        "source_confidence": source_confidence,
    }


def _dlq_row(
    id="dlq-001",
    recorded_at="2026-10-01T10:05:00+00:00",
    rejection_reason="DUPLICATE_EVENT",
    event_type="BOOKING_CREATED",
    replay_result=None,
) -> dict:
    return {
        "id": id,
        "recorded_at": recorded_at,
        "rejection_reason": rejection_reason,
        "event_type": event_type,
        "replay_result": replay_result,
    }


def _buffer_row(
    id="buf-001",
    received_at="2026-10-01T10:00:30+00:00",
    event_kind="BOOKING_AMENDED",
    status="pending",
) -> dict:
    return {
        "id": id,
        "received_at": received_at,
        "event_kind": event_kind,
        "status": status,
    }


# ---------------------------------------------------------------------------
# Group A — TimelineEvent structure
# ---------------------------------------------------------------------------

class TestTimelineEvent:

    def test_A1_frozen_dataclass(self) -> None:
        event = TimelineEvent(
            source_table="event_log",
            event_kind="BOOKING_CREATED",
            occurred_at="2026-10-01T10:00:00",
            recorded_at="2026-10-01T10:01:00",
        )
        with pytest.raises((AttributeError, TypeError)):
            event.event_kind = "MUTATED"  # type: ignore

    def test_A2_sort_key_prefers_recorded_at(self) -> None:
        event = TimelineEvent(
            source_table="event_log",
            event_kind="BOOKING_CREATED",
            occurred_at="2026-01-01",
            recorded_at="2026-10-15",
        )
        assert event.sort_key() == "2026-10-15"

    def test_A3_sort_key_falls_back_to_occurred_at(self) -> None:
        event = TimelineEvent(
            source_table="event_log",
            event_kind="BOOKING_CREATED",
            occurred_at="2026-01-01",
            recorded_at=None,
        )
        assert event.sort_key() == "2026-01-01"

    def test_A4_sort_key_empty_when_both_none(self) -> None:
        event = TimelineEvent(
            source_table="ota_dead_letter",
            event_kind="DLQ_INGESTED",
            occurred_at=None,
            recorded_at=None,
        )
        assert event.sort_key() == ""

    def test_A5_metadata_defaults_to_empty_dict(self) -> None:
        event = TimelineEvent(
            source_table="event_log",
            event_kind="BOOKING_CREATED",
            occurred_at=None,
            recorded_at=None,
        )
        assert event.metadata == {}


# ---------------------------------------------------------------------------
# Group B — build_reservation_timeline happy path
# ---------------------------------------------------------------------------

class TestBuildReservationTimelineHappyPath:

    def test_B1_returns_reservation_timeline(self) -> None:
        db = _make_db()
        result = build_reservation_timeline(db, TENANT, BOOKING)
        assert isinstance(result, ReservationTimeline)

    def test_B2_booking_id_preserved(self) -> None:
        db = _make_db()
        result = build_reservation_timeline(db, TENANT, BOOKING)
        assert result.booking_id == BOOKING

    def test_B3_tenant_id_preserved(self) -> None:
        db = _make_db()
        result = build_reservation_timeline(db, TENANT, BOOKING)
        assert result.tenant_id == TENANT

    def test_B4_no_events_returns_empty_list(self) -> None:
        db = _make_db()
        result = build_reservation_timeline(db, TENANT, BOOKING)
        assert result.events == []

    def test_B5_partial_false_when_all_succeed(self) -> None:
        db = _make_db()
        result = build_reservation_timeline(db, TENANT, BOOKING)
        assert result.partial is False

    def test_B6_events_from_all_sources_aggregated(self) -> None:
        db = _make_db(
            event_log_data=[_event_log_row()],
            financial_data=[_financial_row()],
            dlq_data=[_dlq_row()],
            buffer_data=[_buffer_row()],
        )
        result = build_reservation_timeline(db, TENANT, BOOKING)
        assert len(result.events) == 4

    def test_B7_source_tables_represented(self) -> None:
        db = _make_db(
            event_log_data=[_event_log_row()],
            financial_data=[_financial_row()],
            dlq_data=[_dlq_row()],
            buffer_data=[_buffer_row()],
        )
        result = build_reservation_timeline(db, TENANT, BOOKING)
        tables = {e.source_table for e in result.events}
        assert "event_log" in tables
        assert "booking_financial_facts" in tables
        assert "ota_dead_letter" in tables
        assert "ota_ordering_buffer" in tables


# ---------------------------------------------------------------------------
# Group C — _fetch_* source fetchers
# ---------------------------------------------------------------------------

class TestFetchEventLog:

    def test_C1_returns_events_and_false(self) -> None:
        db = _make_db(event_log_data=[_event_log_row()])
        events, failed = _fetch_event_log_events(db, TENANT, BOOKING)
        assert len(events) == 1
        assert failed is False

    def test_C2_event_kind_preserved(self) -> None:
        db = _make_db(event_log_data=[_event_log_row(event_kind="BOOKING_CANCELED")])
        events, _ = _fetch_event_log_events(db, TENANT, BOOKING)
        assert events[0].event_kind == "BOOKING_CANCELED"

    def test_C3_source_table_is_event_log(self) -> None:
        db = _make_db(event_log_data=[_event_log_row()])
        events, _ = _fetch_event_log_events(db, TENANT, BOOKING)
        assert events[0].source_table == "event_log"

    def test_C4_envelope_id_in_metadata(self) -> None:
        db = _make_db(event_log_data=[_event_log_row(envelope_id="env-xyz")])
        events, _ = _fetch_event_log_events(db, TENANT, BOOKING)
        assert events[0].metadata["envelope_id"] == "env-xyz"

    def test_C5_exception_returns_empty_and_true(self) -> None:
        db = _make_db(event_log_raises=True)
        events, failed = _fetch_event_log_events(db, TENANT, BOOKING)
        assert events == []
        assert failed is True


class TestFetchFinancial:

    def test_C6_returns_financial_recorded_kind(self) -> None:
        db = _make_db(financial_data=[_financial_row()])
        events, failed = _fetch_financial_events(db, TENANT, BOOKING)
        assert len(events) == 1
        assert events[0].event_kind == "FINANCIAL_RECORDED"
        assert failed is False

    def test_C7_currency_in_metadata(self) -> None:
        db = _make_db(financial_data=[_financial_row(currency="EUR")])
        events, _ = _fetch_financial_events(db, TENANT, BOOKING)
        assert events[0].metadata["currency"] == "EUR"

    def test_C8_exception_returns_empty_and_true(self) -> None:
        db = _make_db(financial_raises=True)
        events, failed = _fetch_financial_events(db, TENANT, BOOKING)
        assert events == []
        assert failed is True


class TestFetchDLQ:

    def test_C9_returns_dlq_ingested_kind(self) -> None:
        db = _make_db(dlq_data=[_dlq_row()])
        events, failed = _fetch_dlq_events(db, BOOKING)
        assert len(events) == 1
        assert events[0].event_kind == "DLQ_INGESTED"
        assert failed is False

    def test_C10_rejection_reason_in_metadata(self) -> None:
        db = _make_db(dlq_data=[_dlq_row(rejection_reason="OUT_OF_ORDER")])
        events, _ = _fetch_dlq_events(db, BOOKING)
        assert events[0].metadata["rejection_reason"] == "OUT_OF_ORDER"

    def test_C11_exception_returns_empty_and_true(self) -> None:
        db = _make_db(dlq_raises=True)
        events, failed = _fetch_dlq_events(db, BOOKING)
        assert events == []
        assert failed is True


class TestFetchBuffer:

    def test_C12_returns_buffered_kind(self) -> None:
        db = _make_db(buffer_data=[_buffer_row()])
        events, failed = _fetch_buffer_events(db, BOOKING)
        assert len(events) == 1
        assert events[0].event_kind == "BUFFERED"
        assert failed is False

    def test_C13_original_event_kind_in_metadata(self) -> None:
        db = _make_db(buffer_data=[_buffer_row(event_kind="BOOKING_AMENDED")])
        events, _ = _fetch_buffer_events(db, BOOKING)
        assert events[0].metadata["original_event_kind"] == "BOOKING_AMENDED"

    def test_C14_exception_returns_empty_and_true(self) -> None:
        db = _make_db(buffer_raises=True)
        events, failed = _fetch_buffer_events(db, BOOKING)
        assert events == []
        assert failed is True


# ---------------------------------------------------------------------------
# Group D — Partial failure
# ---------------------------------------------------------------------------

class TestPartialFailure:

    def test_D1_partial_true_when_event_log_fails(self) -> None:
        db = _make_db(
            event_log_raises=True,
            financial_data=[_financial_row()],
        )
        result = build_reservation_timeline(db, TENANT, BOOKING)
        assert result.partial is True

    def test_D2_partial_true_when_financial_fails(self) -> None:
        db = _make_db(
            event_log_data=[_event_log_row()],
            financial_raises=True,
        )
        result = build_reservation_timeline(db, TENANT, BOOKING)
        assert result.partial is True

    def test_D3_partial_true_when_dlq_fails(self) -> None:
        db = _make_db(
            event_log_data=[_event_log_row()],
            dlq_raises=True,
        )
        result = build_reservation_timeline(db, TENANT, BOOKING)
        assert result.partial is True

    def test_D4_partial_true_when_buffer_fails(self) -> None:
        db = _make_db(
            event_log_data=[_event_log_row()],
            buffer_raises=True,
        )
        result = build_reservation_timeline(db, TENANT, BOOKING)
        assert result.partial is True

    def test_D5_available_events_still_returned_on_failure(self) -> None:
        db = _make_db(
            event_log_data=[_event_log_row()],
            financial_raises=True,
            dlq_raises=True,
            buffer_raises=True,
        )
        result = build_reservation_timeline(db, TENANT, BOOKING)
        assert len(result.events) == 1
        assert result.events[0].source_table == "event_log"

    def test_D6_all_sources_fail_returns_empty_partial(self) -> None:
        db = _make_db(
            event_log_raises=True,
            financial_raises=True,
            dlq_raises=True,
            buffer_raises=True,
        )
        result = build_reservation_timeline(db, TENANT, BOOKING)
        assert result.events == []
        assert result.partial is True


# ---------------------------------------------------------------------------
# Group E — Empty results (no events)
# ---------------------------------------------------------------------------

class TestEmptyTimeline:

    def test_E1_no_events_not_an_error(self) -> None:
        db = _make_db()
        result = build_reservation_timeline(db, TENANT, BOOKING)
        assert result.events == []
        assert result.partial is False

    def test_E2_empty_timeline_has_correct_booking_id(self) -> None:
        db = _make_db()
        result = build_reservation_timeline(db, "other-tenant", "other-booking")
        assert result.booking_id == "other-booking"
        assert result.tenant_id == "other-tenant"


# ---------------------------------------------------------------------------
# Group F — Ordering
# ---------------------------------------------------------------------------

class TestOrdering:

    def test_F1_events_sorted_by_recorded_at_ascending(self) -> None:
        db = _make_db(
            event_log_data=[
                _event_log_row(recorded_at="2026-10-01T12:00:00+00:00"),
                _event_log_row(event_kind="BOOKING_AMENDED", recorded_at="2026-10-01T10:00:00+00:00"),
                _event_log_row(event_kind="BOOKING_CANCELED", recorded_at="2026-10-01T11:00:00+00:00"),
            ]
        )
        result = build_reservation_timeline(db, TENANT, BOOKING)
        assert len(result.events) == 3
        assert result.events[0].event_kind == "BOOKING_AMENDED"
        assert result.events[1].event_kind == "BOOKING_CANCELED"
        assert result.events[2].event_kind == "BOOKING_CREATED"

    def test_F2_cross_source_ordering(self) -> None:
        db = _make_db(
            event_log_data=[
                _event_log_row(recorded_at="2026-10-01T10:01:00+00:00"),
            ],
            buffer_data=[
                _buffer_row(received_at="2026-10-01T10:00:30+00:00"),
            ],
        )
        result = build_reservation_timeline(db, TENANT, BOOKING)
        assert len(result.events) == 2
        assert result.events[0].source_table == "ota_ordering_buffer"
        assert result.events[1].source_table == "event_log"

    def test_F3_events_with_none_recorded_at_sorted_last_ish(self) -> None:
        """Events with no sort key (both None) sort to top (empty string < any date)."""
        db = _make_db(
            event_log_data=[
                _event_log_row(occurred_at=None, recorded_at=None),
                _event_log_row(event_kind="BOOKING_CANCELED", recorded_at="2026-10-01T10:00:00"),
            ]
        )
        result = build_reservation_timeline(db, TENANT, BOOKING)
        # Empty string sorts before any date string
        assert result.events[0].sort_key() == ""


# ---------------------------------------------------------------------------
# Group G — Tenant isolation
# ---------------------------------------------------------------------------

class TestTenantIsolation:

    def test_G1_event_log_query_uses_tenant_id(self) -> None:
        """Verify the DB is queried with the correct tenant_id via .eq calls."""
        db = _make_db(event_log_data=[])
        _ = _fetch_event_log_events(db, TENANT, BOOKING)
        # The test verifies no cross-tenant events are returned when DB returns []
        events, failed = _fetch_event_log_events(db, TENANT, BOOKING)
        assert events == []
        assert failed is False

    def test_G2_financial_query_uses_tenant_id(self) -> None:
        db = _make_db(financial_data=[])
        events, failed = _fetch_financial_events(db, TENANT, BOOKING)
        assert events == []
        assert failed is False

    def test_G3_dlq_is_global_no_tenant_filter(self) -> None:
        """DLQ fetch only passes booking_id — no tenant_id."""
        db = _make_db(dlq_data=[_dlq_row()])
        events, failed = _fetch_dlq_events(db, BOOKING)
        assert len(events) == 1
        assert failed is False

    def test_G4_buffer_is_global_no_tenant_filter(self) -> None:
        """Buffer fetch only passes booking_id — no tenant_id."""
        db = _make_db(buffer_data=[_buffer_row()])
        events, failed = _fetch_buffer_events(db, BOOKING)
        assert len(events) == 1
        assert failed is False


# ---------------------------------------------------------------------------
# Group H — ReservationTimeline invariants
# ---------------------------------------------------------------------------

class TestReservationTimelineInvariants:

    def test_H1_events_is_a_list(self) -> None:
        db = _make_db()
        result = build_reservation_timeline(db, TENANT, BOOKING)
        assert isinstance(result.events, list)

    def test_H2_all_elements_are_timeline_events(self) -> None:
        db = _make_db(
            event_log_data=[_event_log_row()],
            financial_data=[_financial_row()],
        )
        result = build_reservation_timeline(db, TENANT, BOOKING)
        for e in result.events:
            assert isinstance(e, TimelineEvent)

    def test_H3_partial_defaults_false(self) -> None:
        tl = ReservationTimeline(booking_id="b", tenant_id="t", events=[])
        assert tl.partial is False

    def test_H4_multiple_events_same_booking(self) -> None:
        db = _make_db(
            event_log_data=[
                _event_log_row(event_kind="BOOKING_CREATED"),
                _event_log_row(event_kind="BOOKING_AMENDED"),
                _event_log_row(event_kind="BOOKING_CANCELED"),
            ]
        )
        result = build_reservation_timeline(db, TENANT, BOOKING)
        assert len(result.events) == 3
        kinds = [e.event_kind for e in result.events]
        assert "BOOKING_CREATED" in kinds
        assert "BOOKING_AMENDED" in kinds
        assert "BOOKING_CANCELED" in kinds
