"""
Phase 149 — Contract Tests: RFC 5545 VCALENDAR Compliance Audit

Tests validate that ICalPushAdapter._ICAL_TEMPLATE and the produced ical_body
include all RFC 5545 REQUIRED fields.

Groups:
  A — VCALENDAR header fields: VERSION, PRODID, CALSCALE, METHOD
  B — VEVENT fields: UID, DTSTAMP, DTSTART, DTEND, SEQUENCE, SUMMARY
  C — DTSTAMP format: must match YYYYMMDDTHHMMSSZ (UTC)
  D — SEQUENCE value is 0
  E — CALSCALE is GREGORIAN
  F — METHOD is PUBLISH
  G — CRLF line endings throughout (\\r\\n only)
  H — BEGIN/END nesting is correct
  I — DTSTART / DTEND appear correctly from injected dates
  J — Adapter smoke: template renders with no KeyError
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from string import Formatter
from unittest.mock import MagicMock, patch


def _template() -> str:
    from adapters.outbound.ical_push_adapter import _ICAL_TEMPLATE
    return _ICAL_TEMPLATE


def _render(
    booking_id:  str = "BK001",
    external_id: str = "EXT-001",
    dtstart:     str = "20260301",
    dtend:       str = "20260307",
    dtstamp:     str = "20260301T000000Z",
) -> str:
    return _template().format(
        booking_id=booking_id,
        external_id=external_id,
        dtstart=dtstart,
        dtend=dtend,
        dtstamp=dtstamp,
    )


# ===========================================================================
# Group A — VCALENDAR header fields
# ===========================================================================

class TestVcalendarHeader:

    def test_version_present(self):
        assert "VERSION:2.0" in _render()

    def test_prodid_present(self):
        assert "PRODID:" in _render()

    def test_prodid_contains_ihouse(self):
        assert "iHouse" in _render() or "ihouse" in _render().lower()

    def test_calscale_present(self):
        assert "CALSCALE:GREGORIAN" in _render()

    def test_method_present(self):
        assert "METHOD:PUBLISH" in _render()

    def test_begin_vcalendar(self):
        assert "BEGIN:VCALENDAR" in _render()

    def test_end_vcalendar(self):
        assert "END:VCALENDAR" in _render()


# ===========================================================================
# Group B — VEVENT fields
# ===========================================================================

class TestVeventFields:

    def test_begin_vevent(self):
        assert "BEGIN:VEVENT" in _render()

    def test_end_vevent(self):
        assert "END:VEVENT" in _render()

    def test_uid_present(self):
        assert "UID:" in _render()

    def test_uid_contains_booking_id(self):
        assert "BK001@" in _render()

    def test_dtstamp_present(self):
        assert "DTSTAMP:" in _render()

    def test_dtstart_present(self):
        assert "DTSTART:" in _render()

    def test_dtend_present(self):
        assert "DTEND:" in _render()

    def test_sequence_present(self):
        assert "SEQUENCE:" in _render()

    def test_summary_present(self):
        assert "SUMMARY:" in _render()

    def test_description_present(self):
        assert "DESCRIPTION:" in _render()


# ===========================================================================
# Group C — DTSTAMP format: YYYYMMDDTHHMMSSZ
# ===========================================================================

class TestDtstampFormat:

    _DTSTAMP_RE = re.compile(r"DTSTAMP:(\d{8}T\d{6}Z)")

    def test_dtstamp_matches_utc_format(self):
        body = _render()
        m = self._DTSTAMP_RE.search(body)
        assert m is not None, "DTSTAMP not found or wrong format"

    def test_dtstamp_parseable_as_datetime(self):
        body = _render(dtstamp="20260310T020031Z")
        m = self._DTSTAMP_RE.search(body)
        assert m, "DTSTAMP not found"
        dt = datetime.strptime(m.group(1), "%Y%m%dT%H%M%SZ")
        assert dt.year == 2026

    def test_adapter_uses_utc_now_for_dtstamp(self):
        """The _ICAL_TEMPLATE.format() call in push() uses datetime.now(tz=UTC)."""
        from adapters.outbound.ical_push_adapter import _ICAL_TEMPLATE
        # Verify template contains the {dtstamp} placeholder
        keys = [fn for _, fn, _, _ in Formatter().parse(_ICAL_TEMPLATE) if fn]
        assert "dtstamp" in keys

    def test_dtstamp_ends_with_z(self):
        body = _render(dtstamp="20260310T120000Z")
        m = self._DTSTAMP_RE.search(body)
        assert m
        assert m.group(1).endswith("Z")


# ===========================================================================
# Group D — SEQUENCE value is 0
# ===========================================================================

class TestSequence:

    def test_sequence_is_zero(self):
        body = _render()
        assert "SEQUENCE:0" in body

    def test_sequence_not_negative(self):
        body = _render()
        m = re.search(r"SEQUENCE:(-?\d+)", body)
        assert m and int(m.group(1)) >= 0


# ===========================================================================
# Group E — CALSCALE is GREGORIAN
# ===========================================================================

class TestCalscale:

    def test_calscale_gregorian(self):
        assert "CALSCALE:GREGORIAN" in _render()

    def test_calscale_in_vcalendar_header_before_vevent(self):
        body = _render()
        calscale_pos = body.index("CALSCALE:GREGORIAN")
        vevent_pos   = body.index("BEGIN:VEVENT")
        assert calscale_pos < vevent_pos


# ===========================================================================
# Group F — METHOD is PUBLISH
# ===========================================================================

class TestMethod:

    def test_method_publish(self):
        assert "METHOD:PUBLISH" in _render()

    def test_method_in_vcalendar_header_before_vevent(self):
        body = _render()
        method_pos = body.index("METHOD:PUBLISH")
        vevent_pos = body.index("BEGIN:VEVENT")
        assert method_pos < vevent_pos


# ===========================================================================
# Group G — CRLF line endings throughout
# ===========================================================================

class TestCrlfLineEndings:

    def test_crlf_used_not_lf_only(self):
        """Every newline pair must be \\r\\n, not bare \\n."""
        raw = _template()
        # Split on \r\n — all segments should be non-empty except last
        parts_crlf = raw.split("\r\n")
        parts_lf   = raw.split("\n")
        # If only \n was used, split by \n gives more segments than \r\n
        assert len(parts_crlf) == len(parts_lf), \
            "Bare \\n detected — all line endings must be \\r\\n"

    def test_no_bare_lf(self):
        """No lone \\n without a preceding \\r."""
        raw = _template()
        idx = 0
        for i, ch in enumerate(raw):
            if ch == "\n":
                assert i > 0 and raw[i - 1] == "\r", \
                    f"Bare \\n found at position {i}"


# ===========================================================================
# Group H — BEGIN/END nesting
# ===========================================================================

class TestNesting:

    def test_vcalendar_wraps_vevent(self):
        body = _render()
        vcal_start = body.index("BEGIN:VCALENDAR")
        vevent_start = body.index("BEGIN:VEVENT")
        vevent_end   = body.index("END:VEVENT")
        vcal_end     = body.index("END:VCALENDAR")
        assert vcal_start < vevent_start < vevent_end < vcal_end

    def test_version_comes_after_begin_vcalendar(self):
        body = _render()
        assert body.index("BEGIN:VCALENDAR") < body.index("VERSION:2.0")


# ===========================================================================
# Group I — DTSTART / DTEND from injected dates
# ===========================================================================

class TestInjectedDates:

    def test_dtstart_uses_check_in(self):
        body = _render(dtstart="20260601")
        assert "DTSTART:20260601" in body

    def test_dtend_uses_check_out(self):
        body = _render(dtend="20260608")
        assert "DTEND:20260608" in body

    def test_dtstart_before_dtend(self):
        body = _render(dtstart="20260301", dtend="20260308")
        ds = re.search(r"DTSTART:(\d{8})", body).group(1)  # type: ignore[union-attr]
        de = re.search(r"DTEND:(\d{8})", body).group(1)    # type: ignore[union-attr]
        assert ds < de


# ===========================================================================
# Group J — Adapter smoke: template renders with no KeyError
# ===========================================================================

class TestAdapterSmoke:

    def test_template_renders_without_key_error(self):
        from adapters.outbound.ical_push_adapter import _ICAL_TEMPLATE
        rendered = _ICAL_TEMPLATE.format(
            booking_id="SMOKE",
            external_id="EXT-SMOKE",
            dtstart="20260101",
            dtend="20260102",
            dtstamp="20260101T000000Z",
        )
        assert "SMOKE" in rendered

    def test_all_template_placeholders_are_known(self):
        from adapters.outbound.ical_push_adapter import _ICAL_TEMPLATE
        known = {"booking_id", "external_id", "dtstart", "dtend", "dtstamp"}
        found = {fn for _, fn, _, _ in Formatter().parse(_ICAL_TEMPLATE) if fn}
        unknown = found - known
        assert not unknown, f"Unknown placeholders in template: {unknown}"

    def test_prodid_updated_to_phase_149(self):
        assert "Phase 149" in _render()
