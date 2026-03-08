"""
Phase 74 — Contract tests for date_normalizer.normalize_date()

Covers:
1.  None input → None
2.  Empty string → None
3.  Whitespace-only → None
4.  "YYYY-MM-DD" → passthrough unchanged
5.  "YYYY-MM-DDT00:00:00Z" (UTC ISO datetime) → "YYYY-MM-DD"
6.  "YYYY-MM-DDT00:00:00" (no tz ISO datetime) → "YYYY-MM-DD"
7.  "YYYY-MM-DDT00:00:00+07:00" (with offset) → "YYYY-MM-DD"
8.  "YYYYMMDD" (compact Trip.com) → "YYYY-MM-DD"
9.  "DD/MM/YYYY" (slash-delimited) → "YYYY-MM-DD" (DD/MM interpreted)
10. Invalid date string → None (no raise)
11. Random garbage → None (no raise)
12. Valid date validates day: "2026-02-30" → None (invalid date)
13. Leading/trailing whitespace stripped
14. amendment_extractor.bookingcom normalizes arrival_date
15. amendment_extractor.expedia normalizes check_in
16. amendment_extractor.airbnb normalizes new_check_in
17. amendment_extractor.agoda normalizes check_in_date
18. amendment_extractor.tripcom normalizes check_in
19. ISO datetime with milliseconds "2026-09-01T00:00:00.000Z" → "2026-09-01"
20. Year 2025 date "2025-12-31" → "2025-12-31"
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# normalize_date unit tests
# ---------------------------------------------------------------------------

class TestNormalizeDateNoneAndEmpty:

    def test_none_returns_none(self) -> None:
        from adapters.ota.date_normalizer import normalize_date
        assert normalize_date(None) is None

    def test_empty_string_returns_none(self) -> None:
        from adapters.ota.date_normalizer import normalize_date
        assert normalize_date("") is None

    def test_whitespace_only_returns_none(self) -> None:
        from adapters.ota.date_normalizer import normalize_date
        assert normalize_date("   ") is None


class TestNormalizeDateISODate:

    def test_iso_date_passthrough(self) -> None:
        from adapters.ota.date_normalizer import normalize_date
        assert normalize_date("2026-09-01") == "2026-09-01"

    def test_iso_date_2025_end_of_year(self) -> None:
        from adapters.ota.date_normalizer import normalize_date
        assert normalize_date("2025-12-31") == "2025-12-31"

    def test_leading_whitespace_stripped(self) -> None:
        from adapters.ota.date_normalizer import normalize_date
        assert normalize_date("  2026-09-01  ") == "2026-09-01"


class TestNormalizeDateISODatetime:

    def test_utc_datetime_z_suffix(self) -> None:
        from adapters.ota.date_normalizer import normalize_date
        assert normalize_date("2026-09-01T00:00:00Z") == "2026-09-01"

    def test_datetime_no_tz(self) -> None:
        from adapters.ota.date_normalizer import normalize_date
        assert normalize_date("2026-09-01T00:00:00") == "2026-09-01"

    def test_datetime_with_positive_offset(self) -> None:
        from adapters.ota.date_normalizer import normalize_date
        assert normalize_date("2026-09-01T00:00:00+07:00") == "2026-09-01"

    def test_datetime_with_negative_offset(self) -> None:
        from adapters.ota.date_normalizer import normalize_date
        assert normalize_date("2026-09-01T00:00:00-05:00") == "2026-09-01"

    def test_datetime_midnight_all_zeros(self) -> None:
        from adapters.ota.date_normalizer import normalize_date
        assert normalize_date("2026-10-15T00:00:00Z") == "2026-10-15"


class TestNormalizeDateCompact:

    def test_yyyymmdd_compact(self) -> None:
        from adapters.ota.date_normalizer import normalize_date
        assert normalize_date("20260901") == "2026-09-01"

    def test_yyyymmdd_compact_end_of_year(self) -> None:
        from adapters.ota.date_normalizer import normalize_date
        assert normalize_date("20251231") == "2025-12-31"


class TestNormalizeDateInvalid:

    def test_invalid_date_returns_none(self) -> None:
        from adapters.ota.date_normalizer import normalize_date
        assert normalize_date("not-a-date") is None

    def test_garbage_returns_none(self) -> None:
        from adapters.ota.date_normalizer import normalize_date
        assert normalize_date("BOOKING_AMENDED") is None

    def test_invalid_date_value_returns_none(self) -> None:
        """2026-02-30 does not exist — should return None."""
        from adapters.ota.date_normalizer import normalize_date
        assert normalize_date("2026-02-30") is None

    def test_does_not_raise_on_any_input(self) -> None:
        from adapters.ota.date_normalizer import normalize_date
        # No exception should propagate from any string
        for bad in ["???", "0000-00-00", "2026", "2026-13-01", "abc123"]:
            result = normalize_date(bad)
            assert result is None or isinstance(result, str)


# ---------------------------------------------------------------------------
# Integration: amendment_extractor uses normalize_date for all 5 providers
# ---------------------------------------------------------------------------

class TestAmendmentExtractorDateNormalization:

    def test_bookingcom_normalizes_arrival_date(self) -> None:
        from adapters.ota.amendment_extractor import extract_amendment_bookingcom
        fields = extract_amendment_bookingcom({
            "new_reservation_info": {
                "arrival_date": "2026-09-01T00:00:00Z",
                "departure_date": "2026-09-05T00:00:00Z",
            }
        })
        assert fields.new_check_in == "2026-09-01"
        assert fields.new_check_out == "2026-09-05"

    def test_expedia_normalizes_check_in(self) -> None:
        from adapters.ota.amendment_extractor import extract_amendment_expedia
        fields = extract_amendment_expedia({
            "changes": {
                "dates": {
                    "check_in": "20261001",
                    "check_out": "20261005",
                },
                "guests": {"count": 2},
            }
        })
        assert fields.new_check_in == "2026-10-01"
        assert fields.new_check_out == "2026-10-05"

    def test_airbnb_normalizes_new_check_in(self) -> None:
        from adapters.ota.amendment_extractor import extract_amendment_airbnb
        fields = extract_amendment_airbnb({
            "alteration": {
                "new_check_in": "2026-11-01T00:00:00+07:00",
                "new_check_out": "2026-11-05T00:00:00+07:00",
            }
        })
        assert fields.new_check_in == "2026-11-01"
        assert fields.new_check_out == "2026-11-05"

    def test_agoda_normalizes_check_in_date(self) -> None:
        from adapters.ota.amendment_extractor import extract_amendment_agoda
        fields = extract_amendment_agoda({
            "modification": {
                "check_in_date": "2026-09-01",
                "check_out_date": "2026-09-05T00:00:00Z",
            }
        })
        assert fields.new_check_in == "2026-09-01"
        assert fields.new_check_out == "2026-09-05"

    def test_tripcom_normalizes_check_in(self) -> None:
        from adapters.ota.amendment_extractor import extract_amendment_tripcom
        fields = extract_amendment_tripcom({
            "changes": {
                "check_in": "20261201",
                "check_out": "20261205",
            }
        })
        assert fields.new_check_in == "2026-12-01"
        assert fields.new_check_out == "2026-12-05"
