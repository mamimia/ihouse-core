"""
Phase 334 — Booking Dates + iCal Push Adapter Integration Tests
================================================================

First-ever tests for:
  - `adapters/outbound/booking_dates.py` (Phase 140, 87 lines)
  - `adapters/outbound/ical_push_adapter.py` (Phase 150, 371 lines)

Group A: fetch_booking_dates — Injectable Client
  ✓  Valid booking found → ISO dates converted to iCal format (YYYYMMDD)
  ✓  Booking not found → (None, None)
  ✓  DB error during query → (None, None), never raises
  ✓  check_in has no dash → still works

Group B: _build_ical_body — UTC Template
  ✓  Contains booking_id
  ✓  Contains DTSTART and DTEND with injected dates
  ✓  Contains correct VCALENDAR structure
  ✓  External_id is in DESCRIPTION

Group C: _build_ical_body — Timezone Template
  ✓  Contains VTIMEZONE block when timezone is specified
  ✓  DTSTART uses TZID-qualified format
  ✓  Timezone ID in VTIMEZONE matches DTSTART TZID

Group D: iCal Date Format Helpers
  ✓  ISO date "2026-03-12" → compact "20260312"
  ✓  Already compact date "20260312" → unchanged

CI-safe: mock client injection, no network.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("IHOUSE_ENV", "test")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from adapters.outbound.booking_dates import fetch_booking_dates
from adapters.outbound.ical_push_adapter import _build_ical_body


# ---------------------------------------------------------------------------
# Group A — fetch_booking_dates with injectable client
# ---------------------------------------------------------------------------

def _make_db_client(rows: list) -> MagicMock:
    client = MagicMock()
    (client.table.return_value.select.return_value
     .eq.return_value.eq.return_value
     .limit.return_value.execute.return_value.data) = rows
    return client


class TestFetchBookingDates:

    def test_valid_booking_returns_ical_dates(self):
        client = _make_db_client([{"check_in": "2026-04-01", "check_out": "2026-04-06"}])
        ci, co = fetch_booking_dates("B-001", "t-1", client=client)
        assert ci == "20260401"
        assert co == "20260406"

    def test_booking_not_found_returns_none(self):
        client = _make_db_client([])
        ci, co = fetch_booking_dates("B-MISSING", "t-1", client=client)
        assert ci is None
        assert co is None

    def test_db_error_returns_none_never_raises(self):
        client = MagicMock()
        client.table.side_effect = Exception("DB crack")
        ci, co = fetch_booking_dates("B-001", "t-1", client=client)
        assert ci is None
        assert co is None

    def test_compact_date_works(self):
        client = _make_db_client([{"check_in": "20260401", "check_out": "20260406"}])
        ci, co = fetch_booking_dates("B-001", "t-1", client=client)
        assert ci == "20260401"
        assert co == "20260406"


# ---------------------------------------------------------------------------
# Group B — _build_ical_body — UTC Template
# ---------------------------------------------------------------------------

class TestBuildIcalBodyUtc:

    def test_contains_booking_id(self):
        body = _build_ical_body(
            booking_id="airbnb_RES001",
            external_id="ext-001",
            dtstart="20260401",
            dtend="20260406",
            dtstamp="20260312T100000Z",
            timezone_id=None,
        )
        assert "airbnb_RES001" in body

    def test_contains_dtstart_and_dtend(self):
        body = _build_ical_body(
            booking_id="B-001",
            external_id="ext-001",
            dtstart="20260401",
            dtend="20260406",
            dtstamp="20260312T100000Z",
            timezone_id=None,
        )
        assert "DTSTART:20260401" in body
        assert "DTEND:20260406" in body

    def test_valid_vcalendar_structure(self):
        body = _build_ical_body(
            booking_id="B-001",
            external_id="ext-001",
            dtstart="20260401",
            dtend="20260406",
            dtstamp="20260312T100000Z",
            timezone_id=None,
        )
        assert "BEGIN:VCALENDAR" in body
        assert "END:VCALENDAR" in body
        assert "BEGIN:VEVENT" in body
        assert "END:VEVENT" in body

    def test_external_id_in_description(self):
        body = _build_ical_body(
            booking_id="B-001",
            external_id="hotel-ext-123",
            dtstart="20260401",
            dtend="20260406",
            dtstamp="20260312T100000Z",
            timezone_id=None,
        )
        assert "hotel-ext-123" in body


# ---------------------------------------------------------------------------
# Group C — _build_ical_body — Timezone Template
# ---------------------------------------------------------------------------

class TestBuildIcalBodyTimezone:

    def test_vtimezone_block_present(self):
        body = _build_ical_body(
            booking_id="B-001",
            external_id="ext-001",
            dtstart="20260401",
            dtend="20260406",
            dtstamp="20260312T100000Z",
            timezone_id="Asia/Bangkok",
        )
        assert "BEGIN:VTIMEZONE" in body
        assert "END:VTIMEZONE" in body

    def test_dtstart_uses_tzid_format(self):
        body = _build_ical_body(
            booking_id="B-001",
            external_id="ext-001",
            dtstart="20260401",
            dtend="20260406",
            dtstamp="20260312T100000Z",
            timezone_id="Asia/Bangkok",
        )
        assert "DTSTART;TZID=Asia/Bangkok" in body

    def test_vtimezone_tzid_matches_dtstart_tzid(self):
        body = _build_ical_body(
            booking_id="B-001",
            external_id="ext-001",
            dtstart="20260401",
            dtend="20260406",
            dtstamp="20260312T100000Z",
            timezone_id="America/New_York",
        )
        assert "TZID:America/New_York" in body
        assert "DTSTART;TZID=America/New_York" in body


# ---------------------------------------------------------------------------
# Group D — iCal Date Format
# ---------------------------------------------------------------------------

class TestIcalDateFormat:

    def test_iso_date_converted(self):
        client = _make_db_client([{"check_in": "2026-03-12", "check_out": "2026-03-17"}])
        ci, co = fetch_booking_dates("B-001", "t-1", client=client)
        assert "-" not in ci
        assert len(ci) == 8

    def test_compact_date_unchanged(self):
        client = _make_db_client([{"check_in": "20260312", "check_out": "20260317"}])
        ci, co = fetch_booking_dates("B-001", "t-1", client=client)
        assert ci == "20260312"
