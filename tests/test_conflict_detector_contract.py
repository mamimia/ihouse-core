"""
Phase 86 — Contract tests for conflict_detector.py.

Tests:
  A — Data structures: ConflictKind, ConflictSeverity, Conflict, ConflictReport
  B — _get_field: top-level + state_json fallback
  C — _dates_overlap: overlap logic, edge cases, None handling
  D — _detect_missing_dates: various missing combinations
  E — _detect_missing_property: missing / present
  F — _detect_date_overlaps: overlapping pairs, adjacent (no overlap), multi-property isolation
  G — _detect_duplicate_refs: duplicate detection
  H — detect_conflicts (public API): full scan, partial on failure, sorting, empty
  I — Invariants: never raises, read-only behavior asserted
"""
from __future__ import annotations

from unittest.mock import MagicMock
from typing import List

import pytest

from adapters.ota.conflict_detector import (
    ConflictKind,
    ConflictSeverity,
    Conflict,
    ConflictReport,
    detect_conflicts,
    _get_field,
    _dates_overlap,
    _detect_missing_dates,
    _detect_missing_property,
    _detect_date_overlaps,
    _detect_duplicate_refs,
)

TENANT = "tenant-test"


# ---------------------------------------------------------------------------
# Mock DB helpers
# ---------------------------------------------------------------------------

def _make_db(rows=None, raises=False) -> MagicMock:
    db = MagicMock()
    mock_table = MagicMock()

    def _chain(*args, **kwargs):
        return mock_table

    mock_table.select = _chain
    mock_table.eq = _chain
    mock_table.in_ = _chain
    mock_table.order = _chain
    mock_table.limit = _chain

    def _execute():
        if raises:
            raise RuntimeError("DB unavailable")
        result = MagicMock()
        result.data = rows or []
        return result

    mock_table.execute = _execute
    db.table = lambda _name: mock_table
    return db


def _row(
    booking_id="B-001",
    status="ACTIVE",
    tenant_id=TENANT,
    property_id="PROP-1",
    provider="airbnb",
    reservation_id="RES-001",
    check_in="2026-12-01",
    check_out="2026-12-08",
    state_json=None,
) -> dict:
    """Build a booking_state row with top-level fields."""
    return {
        "booking_id": booking_id,
        "status": status,
        "tenant_id": tenant_id,
        "provider": provider,
        "reservation_id": reservation_id,
        "property_id": property_id,
        "check_in": check_in,
        "check_out": check_out,
        "state_json": state_json or {},
    }


def _row_from_json(
    booking_id="B-001",
    property_id="PROP-1",
    provider="airbnb",
    reservation_id="RES-001",
    check_in="2026-12-01",
    check_out="2026-12-08",
) -> dict:
    """Build a booking_state row with dates inside state_json (not top-level)."""
    return {
        "booking_id": booking_id,
        "status": "ACTIVE",
        "tenant_id": TENANT,
        "provider": provider,
        "reservation_id": reservation_id,
        "property_id": None,  # not top-level
        "check_in": None,     # not top-level
        "check_out": None,    # not top-level
        "state_json": {
            "property_id": property_id,
            "check_in": check_in,
            "check_out": check_out,
        },
    }


# ---------------------------------------------------------------------------
# Group A — Data structures
# ---------------------------------------------------------------------------

class TestDataStructures:

    def test_A1_conflict_kinds_exist(self) -> None:
        assert ConflictKind.DATE_OVERLAP
        assert ConflictKind.MISSING_DATES
        assert ConflictKind.MISSING_PROPERTY
        assert ConflictKind.DUPLICATE_REF

    def test_A2_conflict_severities_exist(self) -> None:
        assert ConflictSeverity.ERROR
        assert ConflictSeverity.WARNING

    def test_A3_conflict_is_frozen(self) -> None:
        c = Conflict(
            kind=ConflictKind.MISSING_DATES,
            severity=ConflictSeverity.WARNING,
            booking_id_a="B-001",
            detail="test",
        )
        with pytest.raises((AttributeError, TypeError)):
            c.detail = "mutated"  # type: ignore

    def test_A4_conflict_optional_fields_default_none(self) -> None:
        c = Conflict(
            kind=ConflictKind.MISSING_PROPERTY,
            severity=ConflictSeverity.ERROR,
            booking_id_a="B-001",
            detail="test",
        )
        assert c.booking_id_b is None
        assert c.property_id is None
        assert c.metadata == {}

    def test_A5_conflict_report_error_count(self) -> None:
        errors = [
            Conflict(ConflictKind.DATE_OVERLAP, ConflictSeverity.ERROR, "B-001", "detail"),
            Conflict(ConflictKind.DATE_OVERLAP, ConflictSeverity.ERROR, "B-002", "detail"),
        ]
        warnings = [
            Conflict(ConflictKind.MISSING_DATES, ConflictSeverity.WARNING, "B-003", "detail"),
        ]
        report = ConflictReport(TENANT, errors + warnings)
        assert report.error_count == 2
        assert report.warning_count == 1

    def test_A6_conflict_report_has_errors_flag(self) -> None:
        report = ConflictReport(TENANT, [
            Conflict(ConflictKind.DATE_OVERLAP, ConflictSeverity.ERROR, "B-001", "detail"),
        ])
        assert report.has_errors is True

    def test_A7_conflict_report_no_errors(self) -> None:
        report = ConflictReport(TENANT, [])
        assert report.has_errors is False
        assert report.error_count == 0
        assert report.warning_count == 0

    def test_A8_conflict_report_partial_defaults_false(self) -> None:
        report = ConflictReport(TENANT, [])
        assert report.partial is False


# ---------------------------------------------------------------------------
# Group B — _get_field
# ---------------------------------------------------------------------------

class TestGetField:

    def test_B1_reads_top_level_field(self) -> None:
        row = {"check_in": "2026-12-01", "state_json": {}}
        assert _get_field(row, "check_in") == "2026-12-01"

    def test_B2_falls_back_to_state_json(self) -> None:
        row = {"check_in": None, "state_json": {"check_in": "2026-12-15"}}
        assert _get_field(row, "check_in") == "2026-12-15"

    def test_B3_top_level_takes_priority(self) -> None:
        row = {"property_id": "PROP-TOP", "state_json": {"property_id": "PROP-JSON"}}
        assert _get_field(row, "property_id") == "PROP-TOP"

    def test_B4_none_when_absent_everywhere(self) -> None:
        row = {"state_json": {}}
        assert _get_field(row, "check_in") is None

    def test_B5_none_when_state_json_missing(self) -> None:
        row = {}
        assert _get_field(row, "check_in") is None

    def test_B6_converts_to_str(self) -> None:
        row = {"guest_count": 3, "state_json": {}}
        assert _get_field(row, "guest_count") == "3"


# ---------------------------------------------------------------------------
# Group C — _dates_overlap
# ---------------------------------------------------------------------------

class TestDatesOverlap:

    def test_C1_clear_overlap(self) -> None:
        assert _dates_overlap("2026-12-01", "2026-12-10", "2026-12-05", "2026-12-15") is True

    def test_C2_no_overlap_sequential(self) -> None:
        # A ends before B starts
        assert _dates_overlap("2026-12-01", "2026-12-08", "2026-12-08", "2026-12-14") is False

    def test_C3_no_overlap_before(self) -> None:
        # B ends before A starts
        assert _dates_overlap("2026-12-10", "2026-12-17", "2026-12-01", "2026-12-08") is False

    def test_C4_contained_overlap(self) -> None:
        # B fully inside A
        assert _dates_overlap("2026-12-01", "2026-12-31", "2026-12-10", "2026-12-20") is True

    def test_C5_same_dates_overlap(self) -> None:
        assert _dates_overlap("2026-12-01", "2026-12-08", "2026-12-01", "2026-12-08") is True

    def test_C6_none_date_returns_false(self) -> None:
        """If any date is None, cannot determine overlap — returns False."""
        assert _dates_overlap(None, "2026-12-08", "2026-12-01", "2026-12-08") is False
        assert _dates_overlap("2026-12-01", None, "2026-12-01", "2026-12-08") is False

    def test_C7_one_day_gap_no_overlap(self) -> None:
        # A check_out == B check_in → guest departs, new guest arrives same day → valid
        assert _dates_overlap("2026-12-01", "2026-12-08", "2026-12-08", "2026-12-15") is False

    def test_C8_partial_overlap_start(self) -> None:
        # B starts during A
        assert _dates_overlap("2026-12-01", "2026-12-10", "2026-12-09", "2026-12-15") is True


# ---------------------------------------------------------------------------
# Group D — _detect_missing_dates
# ---------------------------------------------------------------------------

class TestDetectMissingDates:

    def test_D1_no_conflicts_when_dates_present(self) -> None:
        rows = [_row()]
        assert _detect_missing_dates(rows) == []

    def test_D2_missing_check_in(self) -> None:
        rows = [_row(check_in=None)]
        result = _detect_missing_dates(rows)
        assert len(result) == 1
        assert result[0].kind == ConflictKind.MISSING_DATES
        assert "check_in" in result[0].metadata["missing_fields"]

    def test_D3_missing_check_out(self) -> None:
        rows = [_row(check_out=None)]
        result = _detect_missing_dates(rows)
        assert len(result) == 1
        assert "check_out" in result[0].metadata["missing_fields"]

    def test_D4_missing_both(self) -> None:
        rows = [_row(check_in=None, check_out=None)]
        result = _detect_missing_dates(rows)
        assert len(result) == 1
        missing = result[0].metadata["missing_fields"]
        assert "check_in" in missing
        assert "check_out" in missing

    def test_D5_severity_is_warning(self) -> None:
        rows = [_row(check_in=None)]
        result = _detect_missing_dates(rows)
        assert result[0].severity == ConflictSeverity.WARNING

    def test_D6_multiple_rows_each_detected(self) -> None:
        rows = [
            _row(booking_id="B-001", check_in=None),
            _row(booking_id="B-002", check_out=None),
            _row(booking_id="B-003"),  # fine
        ]
        result = _detect_missing_dates(rows)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Group E — _detect_missing_property
# ---------------------------------------------------------------------------

class TestDetectMissingProperty:

    def test_E1_no_conflict_when_property_present(self) -> None:
        rows = [_row(property_id="PROP-1")]
        assert _detect_missing_property(rows) == []

    def test_E2_missing_top_level_property_id(self) -> None:
        row = _row(property_id=None)
        row["state_json"] = {}  # ensure state_json also empty
        result = _detect_missing_property([row])
        assert len(result) == 1
        assert result[0].kind == ConflictKind.MISSING_PROPERTY
        assert result[0].severity == ConflictSeverity.ERROR

    def test_E3_property_in_state_json_not_flagged(self) -> None:
        row = _row_from_json(property_id="PROP-JSON")
        result = _detect_missing_property([row])
        assert result == []

    def test_E4_booking_id_preserved(self) -> None:
        row = _row(booking_id="B-MISSING", property_id=None)
        row["state_json"] = {}
        result = _detect_missing_property([row])
        assert result[0].booking_id_a == "B-MISSING"


# ---------------------------------------------------------------------------
# Group F — _detect_date_overlaps
# ---------------------------------------------------------------------------

class TestDetectDateOverlaps:

    def test_F1_no_overlap_no_conflict(self) -> None:
        rows = [
            _row(booking_id="B-001", check_in="2026-12-01", check_out="2026-12-08"),
            _row(booking_id="B-002", check_in="2026-12-08", check_out="2026-12-15"),
        ]
        assert _detect_date_overlaps(rows) == []

    def test_F2_overlap_detected(self) -> None:
        rows = [
            _row(booking_id="B-001", check_in="2026-12-01", check_out="2026-12-10"),
            _row(booking_id="B-002", check_in="2026-12-05", check_out="2026-12-15"),
        ]
        result = _detect_date_overlaps(rows)
        assert len(result) == 1
        assert result[0].kind == ConflictKind.DATE_OVERLAP
        assert result[0].severity == ConflictSeverity.ERROR

    def test_F3_overlap_conflict_has_both_booking_ids(self) -> None:
        rows = [
            _row(booking_id="B-001", check_in="2026-12-01", check_out="2026-12-10"),
            _row(booking_id="B-002", check_in="2026-12-05", check_out="2026-12-15"),
        ]
        result = _detect_date_overlaps(rows)
        assert result[0].booking_id_a in ("B-001", "B-002")
        assert result[0].booking_id_b in ("B-001", "B-002")

    def test_F4_different_properties_do_not_conflict(self) -> None:
        rows = [
            _row(booking_id="B-001", property_id="PROP-A", check_in="2026-12-01", check_out="2026-12-10"),
            _row(booking_id="B-002", property_id="PROP-B", check_in="2026-12-05", check_out="2026-12-15"),
        ]
        assert _detect_date_overlaps(rows) == []

    def test_F5_property_id_in_conflict(self) -> None:
        rows = [
            _row(booking_id="B-001", property_id="PROP-X", check_in="2026-12-01", check_out="2026-12-10"),
            _row(booking_id="B-002", property_id="PROP-X", check_in="2026-12-05", check_out="2026-12-15"),
        ]
        result = _detect_date_overlaps(rows)
        assert result[0].property_id == "PROP-X"

    def test_F6_missing_dates_skipped_in_overlap(self) -> None:
        """Rows with None dates don't crash and are skipped for overlap."""
        rows = [
            _row(booking_id="B-001", check_in=None, check_out=None),
            _row(booking_id="B-002", check_in="2026-12-05", check_out="2026-12-15"),
        ]
        result = _detect_date_overlaps(rows)
        assert result == []

    def test_F7_metadata_contains_dates(self) -> None:
        rows = [
            _row(booking_id="B-001", check_in="2026-12-01", check_out="2026-12-10"),
            _row(booking_id="B-002", check_in="2026-12-05", check_out="2026-12-15"),
        ]
        result = _detect_date_overlaps(rows)
        meta = result[0].metadata
        assert "check_in_a" in meta
        assert "check_out_b" in meta

    def test_F8_three_way_overlap_all_pairs_detected(self) -> None:
        rows = [
            _row(booking_id="B-001", check_in="2026-12-01", check_out="2026-12-20"),
            _row(booking_id="B-002", check_in="2026-12-05", check_out="2026-12-15"),
            _row(booking_id="B-003", check_in="2026-12-10", check_out="2026-12-25"),
        ]
        result = _detect_date_overlaps(rows)
        # 3 overlapping bookings → 3 pairs
        assert len(result) == 3


# ---------------------------------------------------------------------------
# Group G — _detect_duplicate_refs
# ---------------------------------------------------------------------------

class TestDetectDuplicateRefs:

    def test_G1_no_duplicate_no_conflict(self) -> None:
        rows = [
            _row(booking_id="B-001", provider="airbnb", reservation_id="RES-A"),
            _row(booking_id="B-002", provider="airbnb", reservation_id="RES-B"),
        ]
        assert _detect_duplicate_refs(rows) == []

    def test_G2_same_ref_detected(self) -> None:
        rows = [
            _row(booking_id="B-001", provider="airbnb", reservation_id="RES-SAME"),
            _row(booking_id="B-002", provider="airbnb", reservation_id="RES-SAME"),
        ]
        result = _detect_duplicate_refs(rows)
        assert len(result) == 1
        assert result[0].kind == ConflictKind.DUPLICATE_REF
        assert result[0].severity == ConflictSeverity.ERROR

    def test_G3_same_ref_different_provider_not_flagged(self) -> None:
        rows = [
            _row(booking_id="B-001", provider="airbnb", reservation_id="RES-001"),
            _row(booking_id="B-002", provider="bookingcom", reservation_id="RES-001"),
        ]
        assert _detect_duplicate_refs(rows) == []

    def test_G4_duplicate_ref_metadata(self) -> None:
        rows = [
            _row(booking_id="B-001", provider="expedia", reservation_id="EXP-999"),
            _row(booking_id="B-002", provider="expedia", reservation_id="EXP-999"),
        ]
        result = _detect_duplicate_refs(rows)
        assert result[0].metadata["provider"] == "expedia"
        assert result[0].metadata["reservation_id"] == "EXP-999"

    def test_G5_missing_provider_skipped(self) -> None:
        row = _row(booking_id="B-001")
        row["provider"] = None
        result = _detect_duplicate_refs([row])
        assert result == []


# ---------------------------------------------------------------------------
# Group H — detect_conflicts (public API)
# ---------------------------------------------------------------------------

class TestDetectConflictsPublicAPI:

    def test_H1_returns_conflict_report(self) -> None:
        db = _make_db(rows=[])
        result = detect_conflicts(db, TENANT)
        assert isinstance(result, ConflictReport)

    def test_H2_tenant_id_preserved(self) -> None:
        db = _make_db(rows=[])
        result = detect_conflicts(db, TENANT)
        assert result.tenant_id == TENANT

    def test_H3_empty_returns_no_conflicts(self) -> None:
        db = _make_db(rows=[])
        result = detect_conflicts(db, TENANT)
        assert result.conflicts == []
        assert result.partial is False

    def test_H4_scanned_count_matches_rows(self) -> None:
        rows = [_row(booking_id=f"B-{i:03d}") for i in range(5)]
        db = _make_db(rows=rows)
        result = detect_conflicts(db, TENANT)
        assert result.scanned_count == 5

    def test_H5_partial_true_on_db_failure(self) -> None:
        db = _make_db(raises=True)
        result = detect_conflicts(db, TENANT)
        assert result.partial is True
        assert result.conflicts == []
        assert result.scanned_count == 0

    def test_H6_errors_sorted_before_warnings(self) -> None:
        rows = [
            _row(booking_id="B-001", check_in=None),           # WARNING: missing date
            _row(booking_id="B-002", property_id=None),         # ERROR: missing property
        ]
        # Ensure B-002 state_json is also missing property
        rows[1]["state_json"] = {}
        db = _make_db(rows=rows)
        result = detect_conflicts(db, TENANT)
        assert result.conflicts[0].severity == ConflictSeverity.ERROR

    def test_H7_clean_bookings_no_conflicts(self) -> None:
        rows = [
            _row(booking_id="B-001", reservation_id="RES-001", check_in="2026-12-01", check_out="2026-12-08"),
            _row(booking_id="B-002", reservation_id="RES-002", check_in="2026-12-08", check_out="2026-12-15"),
        ]
        db = _make_db(rows=rows)
        result = detect_conflicts(db, TENANT)
        assert result.conflicts == []
        assert result.has_errors is False

    def test_H8_overlap_detected_end_to_end(self) -> None:
        rows = [
            _row(booking_id="B-001", check_in="2026-12-01", check_out="2026-12-10"),
            _row(booking_id="B-002", check_in="2026-12-05", check_out="2026-12-15"),
        ]
        db = _make_db(rows=rows)
        result = detect_conflicts(db, TENANT)
        assert result.has_errors is True
        kinds = {c.kind for c in result.conflicts}
        assert ConflictKind.DATE_OVERLAP in kinds


# ---------------------------------------------------------------------------
# Group I — Invariants
# ---------------------------------------------------------------------------

class TestInvariants:

    def test_I1_never_raises_on_empty(self) -> None:
        db = _make_db(rows=[])
        result = detect_conflicts(db, TENANT)
        assert isinstance(result, ConflictReport)

    def test_I2_never_raises_on_malformed_rows(self) -> None:
        """Should not crash even with completely unexpected row shapes."""
        rows = [{"unexpected_key": "garbage"}, {}, {"booking_id": None}]
        db = _make_db(rows=rows)
        result = detect_conflicts(db, TENANT)
        assert isinstance(result, ConflictReport)

    def test_I3_conflict_report_has_no_write_methods(self) -> None:
        """ConflictReport must not expose any write/mutate methods to tables."""
        report = ConflictReport(TENANT, [])
        # These must not exist
        assert not hasattr(report, "write")
        assert not hasattr(report, "save")
        assert not hasattr(report, "apply")
        assert not hasattr(report, "execute")

    def test_I4_conflict_is_immutable(self) -> None:
        c = Conflict(
            kind=ConflictKind.DATE_OVERLAP,
            severity=ConflictSeverity.ERROR,
            booking_id_a="B-001",
            detail="test",
        )
        with pytest.raises((AttributeError, TypeError)):
            c.kind = ConflictKind.MISSING_DATES  # type: ignore

    def test_I5_detect_conflicts_never_raises_on_db_error(self) -> None:
        db = _make_db(raises=True)
        # Must not raise
        result = detect_conflicts(db, TENANT)
        assert result.partial is True
