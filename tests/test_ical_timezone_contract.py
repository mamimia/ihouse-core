"""
Phase 150 — iCal VTIMEZONE Contract Tests

Groups:
  A — UTC fallback (no timezone param): existing behaviour unchanged
  B — VTIMEZONE component present when timezone provided
  C — TZID format correct on DTSTART/DTEND
  D — CRLF throughout the output
  E — PRODID updated to Phase 150
  F — UTC template structure (all RFC 5545 required fields)
  G — TZID template structure
  H — _build_ical_body helper isolation
  I — push() dry-run: timezone param accepted, doesn't affect dry-run logic
  J — Fallback dates still work with timezone provided
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from adapters.outbound.ical_push_adapter import (
    ICalPushAdapter,
    _build_ical_body,
    _FALLBACK_DTSTART,
    _FALLBACK_DTEND,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _body(
    *,
    booking_id: str = "airbnb_ABC123",
    external_id: str = "EXT-001",
    dtstart: str = "20260115",
    dtend: str = "20260120",
    dtstamp: str = "20260115T060000Z",
    timezone_id: str | None = None,
) -> str:
    return _build_ical_body(
        booking_id=booking_id,
        external_id=external_id,
        dtstart=dtstart,
        dtend=dtend,
        dtstamp=dtstamp,
        timezone_id=timezone_id,
    )


# ===========================================================================
# Group A — UTC fallback (no timezone param)
# ===========================================================================

class TestGroupA_UTCFallback:
    """When timezone_id is None, output unchanged from Phase 149 baseline."""

    def test_a1_no_vtimezone_block_when_no_tz(self):
        body = _body()
        assert "BEGIN:VTIMEZONE" not in body

    def test_a2_no_tzid_in_dtstart_when_no_tz(self):
        body = _body()
        assert "DTSTART;TZID" not in body

    def test_a3_no_tzid_in_dtend_when_no_tz(self):
        body = _body()
        assert "DTEND;TZID" not in body

    def test_a4_plain_dtstart_present(self):
        body = _body(dtstart="20260115")
        assert "DTSTART:20260115" in body

    def test_a5_plain_dtend_present(self):
        body = _body(dtend="20260120")
        assert "DTEND:20260120" in body

    def test_a6_empty_string_timezone_treated_as_absent(self):
        body = _body(timezone_id="")
        assert "BEGIN:VTIMEZONE" not in body
        assert "DTSTART;TZID" not in body


# ===========================================================================
# Group B — VTIMEZONE component present when timezone provided
# ===========================================================================

class TestGroupB_VTimezonPresent:
    """VTIMEZONE block is emitted when timezone_id is given."""

    def test_b1_vtimezone_block_present(self):
        body = _body(timezone_id="Asia/Bangkok")
        assert "BEGIN:VTIMEZONE" in body

    def test_b2_end_vtimezone_present(self):
        body = _body(timezone_id="Asia/Bangkok")
        assert "END:VTIMEZONE" in body

    def test_b3_tzid_line_in_vtimezone(self):
        body = _body(timezone_id="Asia/Bangkok")
        assert "TZID:Asia/Bangkok" in body

    def test_b4_standard_subcomponent_present(self):
        body = _body(timezone_id="Asia/Bangkok")
        assert "BEGIN:STANDARD" in body
        assert "END:STANDARD" in body

    def test_b5_vtimezone_before_vevent(self):
        body = _body(timezone_id="Asia/Bangkok")
        tz_pos = body.index("BEGIN:VTIMEZONE")
        ve_pos = body.index("BEGIN:VEVENT")
        assert tz_pos < ve_pos

    def test_b6_different_timezone_emitted_correctly(self):
        body = _body(timezone_id="America/New_York")
        assert "TZID:America/New_York" in body

    def test_b7_europe_timezone(self):
        body = _body(timezone_id="Europe/London")
        assert "TZID:Europe/London" in body


# ===========================================================================
# Group C — TZID format correct on DTSTART/DTEND
# ===========================================================================

class TestGroupC_TZIDFormat:
    """DTSTART;TZID= and T000000 suffix correct for timezone-aware output."""

    def test_c1_dtstart_has_tzid_param(self):
        body = _body(dtstart="20260115", timezone_id="Asia/Bangkok")
        assert "DTSTART;TZID=Asia/Bangkok:20260115T000000" in body

    def test_c2_dtend_has_tzid_param(self):
        body = _body(dtend="20260120", timezone_id="Asia/Bangkok")
        assert "DTEND;TZID=Asia/Bangkok:20260120T000000" in body

    def test_c3_tzid_value_matches_vtimezone(self):
        tz = "America/Chicago"
        body = _body(timezone_id=tz)
        assert f"TZID:{tz}" in body
        assert f"DTSTART;TZID={tz}:" in body
        assert f"DTEND;TZID={tz}:" in body

    def test_c4_t000000_suffix_on_dtstart(self):
        body = _body(dtstart="20260115", timezone_id="Asia/Tokyo")
        assert "DTSTART;TZID=Asia/Tokyo:20260115T000000" in body

    def test_c5_t000000_suffix_on_dtend(self):
        body = _body(dtend="20260116", timezone_id="Asia/Tokyo")
        assert "DTEND;TZID=Asia/Tokyo:20260116T000000" in body


# ===========================================================================
# Group D — CRLF throughout
# ===========================================================================

class TestGroupD_CRLF:
    """RFC 5545 §3.1 requires CRLF line endings throughout."""

    def test_d1_crlf_in_utc_output(self):
        body = _body()
        assert "\r\n" in body

    def test_d2_no_bare_lf_in_utc_output(self):
        body = _body()
        lines = body.split("\r\n")
        for line in lines:
            assert "\n" not in line, f"Bare LF found in line: {line!r}"

    def test_d3_crlf_in_timezone_output(self):
        body = _body(timezone_id="Asia/Bangkok")
        assert "\r\n" in body

    def test_d4_no_bare_lf_in_timezone_output(self):
        body = _body(timezone_id="Asia/Bangkok")
        lines = body.split("\r\n")
        for line in lines:
            assert "\n" not in line, f"Bare LF found in line: {line!r}"

    def test_d5_vtimezone_lines_crlf_terminated(self):
        body = _body(timezone_id="Asia/Bangkok")
        assert "BEGIN:VTIMEZONE\r\n" in body
        assert "END:VTIMEZONE\r\n" in body


# ===========================================================================
# Group E — PRODID updated to Phase 150
# ===========================================================================

class TestGroupE_PRODID:
    """PRODID contains Phase 150 in both templates."""

    def test_e1_prodid_phase_150_utc_output(self):
        body = _body()
        assert "Phase 150" in body

    def test_e2_prodid_phase_150_tzid_output(self):
        body = _body(timezone_id="Asia/Bangkok")
        assert "Phase 150" in body

    def test_e3_prodid_full_string_utc(self):
        body = _body()
        assert "PRODID:-//iHouse Core//Phase 150//EN" in body

    def test_e4_prodid_full_string_tzid(self):
        body = _body(timezone_id="Asia/Seoul")
        assert "PRODID:-//iHouse Core//Phase 150//EN" in body


# ===========================================================================
# Group F — UTC template structure (all RFC 5545 required fields)
# ===========================================================================

class TestGroupF_UTCStructure:
    """UTC output contains all RFC 5545 required iCal fields."""

    def test_f1_begin_vcalendar(self):
        body = _body()
        assert "BEGIN:VCALENDAR" in body

    def test_f2_end_vcalendar(self):
        body = _body()
        assert "END:VCALENDAR" in body

    def test_f3_version_2(self):
        body = _body()
        assert "VERSION:2.0" in body

    def test_f4_calscale_gregorian(self):
        body = _body()
        assert "CALSCALE:GREGORIAN" in body

    def test_f5_method_publish(self):
        body = _body()
        assert "METHOD:PUBLISH" in body

    def test_f6_sequence_zero(self):
        body = _body()
        assert "SEQUENCE:0" in body

    def test_f7_dtstamp_present(self):
        body = _body(dtstamp="20260115T060000Z")
        assert "DTSTAMP:20260115T060000Z" in body

    def test_f8_uid_present(self):
        body = _body(booking_id="airbnb_TEST1")
        assert "UID:airbnb_TEST1@ihouse.core" in body


# ===========================================================================
# Group G — TZID template structure
# ===========================================================================

class TestGroupG_TZIDStructure:
    """TZID output contains all required fields including VTIMEZONE."""

    def test_g1_begin_vcalendar(self):
        body = _body(timezone_id="Asia/Bangkok")
        assert "BEGIN:VCALENDAR" in body

    def test_g2_calscale_gregorian(self):
        body = _body(timezone_id="Asia/Bangkok")
        assert "CALSCALE:GREGORIAN" in body

    def test_g3_method_publish(self):
        body = _body(timezone_id="Asia/Bangkok")
        assert "METHOD:PUBLISH" in body

    def test_g4_sequence_zero(self):
        body = _body(timezone_id="Asia/Bangkok")
        assert "SEQUENCE:0" in body

    def test_g5_dtstamp_present(self):
        body = _body(dtstamp="20260115T060000Z", timezone_id="Asia/Bangkok")
        assert "DTSTAMP:20260115T060000Z" in body

    def test_g6_uid_present(self):
        body = _body(booking_id="airbnb_TEST2", timezone_id="Asia/Bangkok")
        assert "UID:airbnb_TEST2@ihouse.core" in body

    def test_g7_tzoffsetfrom_present(self):
        body = _body(timezone_id="Asia/Bangkok")
        assert "TZOFFSETFROM:" in body

    def test_g8_tzoffsetto_present(self):
        body = _body(timezone_id="Asia/Bangkok")
        assert "TZOFFSETTO:" in body


# ===========================================================================
# Group H — _build_ical_body helper isolation
# ===========================================================================

class TestGroupH_BuildIcalBodyHelper:
    """Direct unit tests for the _build_ical_body helper."""

    def test_h1_returns_string(self):
        result = _build_ical_body(
            booking_id="a_b", external_id="x", dtstart="20260101",
            dtend="20260102", dtstamp="20260101T000000Z", timezone_id=None,
        )
        assert isinstance(result, str)

    def test_h2_none_tz_uses_utc_template(self):
        body = _build_ical_body(
            booking_id="a_b", external_id="x", dtstart="20260101",
            dtend="20260102", dtstamp="20260101T000000Z", timezone_id=None,
        )
        assert "BEGIN:VTIMEZONE" not in body

    def test_h3_tz_provided_uses_tzid_template(self):
        body = _build_ical_body(
            booking_id="a_b", external_id="x", dtstart="20260101",
            dtend="20260102", dtstamp="20260101T000000Z",
            timezone_id="Asia/Bangkok",
        )
        assert "BEGIN:VTIMEZONE" in body

    def test_h4_booking_id_in_uid(self):
        body = _build_ical_body(
            booking_id="despegar_XYZ", external_id="EXT",
            dtstart="20260101", dtend="20260102",
            dtstamp="20260101T000000Z", timezone_id=None,
        )
        assert "despegar_XYZ@ihouse.core" in body


# ===========================================================================
# Group I — push() dry-run: timezone param accepted
# ===========================================================================

class TestGroupI_DryRunAcceptsTimezone:
    """push() accepts timezone param without error in dry-run mode."""

    def test_i1_push_dry_run_no_timezone(self):
        adapter = ICalPushAdapter("hotelbeds")
        result = adapter.push(
            external_id="EXT1", booking_id="hotelbeds_001", dry_run=True,
        )
        assert result.status == "dry_run"

    def test_i2_push_dry_run_with_timezone(self):
        adapter = ICalPushAdapter("hotelbeds")
        result = adapter.push(
            external_id="EXT1", booking_id="hotelbeds_001",
            dry_run=True, timezone="Asia/Bangkok",
        )
        assert result.status == "dry_run"

    def test_i3_provider_in_result(self):
        adapter = ICalPushAdapter("tripadvisor")
        result = adapter.push(
            external_id="EXT1", booking_id="tripadvisor_001",
            dry_run=True, timezone="America/New_York",
        )
        assert result.provider == "tripadvisor"
        assert result.status == "dry_run"


# ===========================================================================
# Group J — Fallback dates work with timezone provided
# ===========================================================================

class TestGroupJ_FallbackDatesWithTimezone:
    """When check_in/check_out omitted, fallback dates used correctly."""

    def test_j1_fallback_dtstart_used_with_tz(self):
        body = _body(dtstart=_FALLBACK_DTSTART, timezone_id="Asia/Bangkok")
        assert _FALLBACK_DTSTART in body

    def test_j2_fallback_dtend_used_with_tz(self):
        body = _body(dtend=_FALLBACK_DTEND, timezone_id="Asia/Bangkok")
        assert _FALLBACK_DTEND in body

    def test_j3_fallback_no_vtimezone_when_no_tz(self):
        body = _body(dtstart=_FALLBACK_DTSTART, dtend=_FALLBACK_DTEND, timezone_id=None)
        assert "BEGIN:VTIMEZONE" not in body

    def test_j4_fallback_with_tz_has_vtimezone(self):
        body = _body(dtstart=_FALLBACK_DTSTART, dtend=_FALLBACK_DTEND, timezone_id="UTC")
        assert "BEGIN:VTIMEZONE" in body
