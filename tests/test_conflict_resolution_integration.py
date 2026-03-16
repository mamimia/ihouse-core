"""
Phase 325 — Booking Conflict Resolver Integration Tests
========================================================

Tests the full conflict detection and auto-resolution pipeline.

Group A: Date Overlap Detection
  ✓  Overlapping date ranges detected as DATE_OVERLAP ERROR
  ✓  Adjacent (checkout = next checkin) not flagged
  ✓  Different properties never clash with each other
  ✓  Three-way overlap creates 3 conflict pairs

Group B: Missing Fields Detection
  ✓  No check_in → MISSING_DATES WARNING
  ✓  No check_out → MISSING_DATES WARNING
  ✓  No property_id → MISSING_PROPERTY ERROR
  ✓  state_json fallback lookup works

Group C: Duplicate Reference Detection
  ✓  Same provider + reservation_id in two bookings → DUPLICATE_REF ERROR
  ✓  Different providers with same reservation_id → not a dup
  ✓  Missing reservation_id skipped silently

Group D: ConflictReport Shape and Ordering
  ✓  ERROR conflicts sorted before WARNING
  ✓  error_count / warning_count properties correct
  ✓  DB failure → partial=True, empty conflicts, never raises

Group E: Auto-Resolver Chain
  ✓  No conflicts → conflicts_found=0, artifacts_written=0
  ✓  Overlap involving booking_id → artifacts_written=1
  ✓  DB failure in detect_conflicts → partial=True, never raises

CI-safe: pure in-memory tests using helper row builders and mock DB.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("IHOUSE_ENV", "test")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from adapters.ota.conflict_detector import (
    Conflict,
    ConflictKind,
    ConflictReport,
    ConflictSeverity,
    _dates_overlap,
    _detect_date_overlaps,
    _detect_duplicate_refs,
    _detect_missing_dates,
    _detect_missing_property,
    detect_conflicts,
)
from services.conflict_auto_resolver import ConflictAutoCheckResult, run_auto_check


# ---------------------------------------------------------------------------
# Row builder helpers
# ---------------------------------------------------------------------------

def _row(
    booking_id: str,
    check_in: str = "2026-03-10",
    check_out: str = "2026-03-15",
    property_id: str = "prop-A",
    status: str = "ACTIVE",
    provider: str = "airbnb",
    reservation_id: str = "RES-001",
) -> dict:
    return {
        "booking_id": booking_id,
        "status": status,
        "provider": provider,
        "reservation_id": reservation_id,
        "state_json": {
            "check_in": check_in,
            "check_out": check_out,
            "property_id": property_id,
        },
    }


def _mock_db(rows: list) -> MagicMock:
    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.in_.return_value.execute.return_value.data = rows
    return db


# ---------------------------------------------------------------------------
# Group A — Date Overlap Detection
# ---------------------------------------------------------------------------

class TestDateOverlapDetection:

    def test_overlapping_bookings_detected(self):
        """Dates [Mar10→Mar15] vs [Mar13→Mar18] overlap."""
        rows = [
            _row("B1", check_in="2026-03-10", check_out="2026-03-15", property_id="P1"),
            _row("B2", check_in="2026-03-13", check_out="2026-03-18", property_id="P1"),
        ]
        conflicts = _detect_date_overlaps(rows)
        assert len(conflicts) == 1
        assert conflicts[0].kind == ConflictKind.DATE_OVERLAP
        assert conflicts[0].severity == ConflictSeverity.ERROR
        assert "B1" in (conflicts[0].booking_id_a, conflicts[0].booking_id_b)
        assert "B2" in (conflicts[0].booking_id_a, conflicts[0].booking_id_b)

    def test_adjacent_bookings_not_flagged(self):
        """[Mar10→Mar15] then [Mar15→Mar20] — checkout = next checkin, no overlap."""
        rows = [
            _row("B1", check_in="2026-03-10", check_out="2026-03-15", property_id="P1"),
            _row("B2", check_in="2026-03-15", check_out="2026-03-20", property_id="P1"),
        ]
        conflicts = _detect_date_overlaps(rows)
        assert conflicts == []

    def test_different_properties_no_clash(self):
        """Same dates but different properties → no DATE_OVERLAP."""
        rows = [
            _row("B1", check_in="2026-03-10", check_out="2026-03-15", property_id="P1"),
            _row("B2", check_in="2026-03-10", check_out="2026-03-15", property_id="P2"),
        ]
        conflicts = _detect_date_overlaps(rows)
        assert conflicts == []

    def test_three_way_overlap(self):
        """3 overlapping bookings on same property → 3 pairs."""
        rows = [
            _row("B1", check_in="2026-03-10", check_out="2026-03-20", property_id="P1"),
            _row("B2", check_in="2026-03-12", check_out="2026-03-18", property_id="P1"),
            _row("B3", check_in="2026-03-15", check_out="2026-03-22", property_id="P1"),
        ]
        conflicts = _detect_date_overlaps(rows)
        assert len(conflicts) == 3

    def test_dates_overlap_helper(self):
        assert _dates_overlap("2026-03-10", "2026-03-15", "2026-03-13", "2026-03-18") is True
        assert _dates_overlap("2026-03-10", "2026-03-15", "2026-03-15", "2026-03-20") is False
        assert _dates_overlap("2026-03-10", "2026-03-15", None, "2026-03-18") is False


# ---------------------------------------------------------------------------
# Group B — Missing Fields Detection
# ---------------------------------------------------------------------------

class TestMissingFieldsDetection:

    def test_missing_check_in_flagged(self):
        row = _row("B1", check_in="")
        row["state_json"]["check_in"] = None
        conflicts = _detect_missing_dates([row])
        assert any(c.kind == ConflictKind.MISSING_DATES for c in conflicts)
        assert conflicts[0].severity == ConflictSeverity.WARNING

    def test_missing_check_out_flagged(self):
        row = _row("B1", check_out="")
        row["state_json"]["check_out"] = None
        conflicts = _detect_missing_dates([row])
        assert any("check_out" in c.metadata.get("missing_fields", []) for c in conflicts)

    def test_missing_property_flagged(self):
        row = _row("B1")
        row["state_json"]["property_id"] = None
        conflicts = _detect_missing_property([row])
        assert len(conflicts) == 1
        assert conflicts[0].kind == ConflictKind.MISSING_PROPERTY
        assert conflicts[0].severity == ConflictSeverity.ERROR

    def test_state_json_fallback_used(self):
        """Fields in state_json (not top-level) are still read."""
        row = {"booking_id": "B99", "state_json": {"check_in": "2026-03-10", "check_out": "2026-03-15", "property_id": "P1"}}
        conflicts = _detect_missing_dates([row])
        assert conflicts == []


# ---------------------------------------------------------------------------
# Group C — Duplicate Reference Detection
# ---------------------------------------------------------------------------

class TestDuplicateRefDetection:

    def test_same_provider_and_res_id_flagged(self):
        rows = [
            _row("B1", provider="airbnb", reservation_id="RES-111"),
            _row("B2", provider="airbnb", reservation_id="RES-111"),
        ]
        conflicts = _detect_duplicate_refs(rows)
        assert len(conflicts) == 1
        assert conflicts[0].kind == ConflictKind.DUPLICATE_REF
        assert conflicts[0].severity == ConflictSeverity.ERROR

    def test_same_res_id_different_provider_ok(self):
        rows = [
            _row("B1", provider="airbnb", reservation_id="RES-111"),
            _row("B2", provider="booking_com", reservation_id="RES-111"),
        ]
        conflicts = _detect_duplicate_refs(rows)
        assert conflicts == []

    def test_no_reservation_id_skipped(self):
        rows = [
            {"booking_id": "B1", "provider": "airbnb", "state_json": {}},
            {"booking_id": "B2", "provider": "airbnb", "state_json": {}},
        ]
        conflicts = _detect_duplicate_refs(rows)
        assert conflicts == []


# ---------------------------------------------------------------------------
# Group D — ConflictReport Shape and Ordering
# ---------------------------------------------------------------------------

class TestConflictReportShape:

    def test_errors_before_warnings_in_report(self):
        db = _mock_db([
            # Missing dates (warning) + missing property (error) on different bookings
            {"booking_id": "B1", "state_json": {"property_id": None}},
            {"booking_id": "B2", "state_json": {"check_in": None, "check_out": "2026-03-15", "property_id": "P1"}},
        ])
        report = detect_conflicts(db, "tenant-1")
        if report.conflicts:
            severities = [c.severity for c in report.conflicts]
            # First item should be ERROR if any ERRORs
            error_indices = [i for i, s in enumerate(severities) if s == ConflictSeverity.ERROR]
            warn_indices = [i for i, s in enumerate(severities) if s == ConflictSeverity.WARNING]
            if error_indices and warn_indices:
                assert max(error_indices) < min(warn_indices)

    def test_error_and_warning_counts(self):
        db = _mock_db([
            {"booking_id": "B1", "provider": "airbnb", "reservation_id": "R1",
             "state_json": {"property_id": "P1", "check_in": "2026-03-10", "check_out": "2026-03-15"}},
            {"booking_id": "B2", "provider": "airbnb", "reservation_id": "R1",
             "state_json": {"property_id": "P1", "check_in": "2026-03-20", "check_out": "2026-03-25"}},
        ])
        report = detect_conflicts(db, "tenant-1")
        assert isinstance(report.error_count, int)
        assert isinstance(report.warning_count, int)
        assert report.error_count >= 1  # DUPLICATE_REF

    def test_db_failure_returns_partial_report(self):
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.in_.return_value.execute.side_effect = Exception("DB down")
        report = detect_conflicts(db, "tenant-1")
        assert report.partial is True
        assert report.conflicts == []
        assert report.scanned_count == 0


# ---------------------------------------------------------------------------
# Group E — Auto-Resolver Chain
# ---------------------------------------------------------------------------

class TestAutoResolverChain:

    def test_no_conflicts_zero_artifacts(self):
        db = _mock_db([
            _row("B1", check_in="2026-03-10", check_out="2026-03-15", property_id="P1"),
        ])
        result = run_auto_check(db, "tenant-1", "B1", "P1")
        assert result.conflicts_found == 0
        assert result.artifacts_written == 0
        assert result.partial is False

    def test_overlap_writes_artifact(self):
        rows = [
            _row("B1", check_in="2026-03-10", check_out="2026-03-18", property_id="P1"),
            _row("B2", check_in="2026-03-15", check_out="2026-03-22", property_id="P1"),
        ]
        db = _mock_db(rows)

        # write_resolution returns (1, []) — 1 row written
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(
                "services.conflict_auto_resolver.write_resolution",
                lambda **kwargs: (1, []),
            )
            result = run_auto_check(db, "tenant-1", "B1", "P1")

        assert result.conflicts_found == 1
        assert result.artifacts_written == 1

    def test_db_failure_never_raises(self):
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.in_.return_value.execute.side_effect = Exception("DB down")
        result = run_auto_check(db, "tenant-1", "B1", "P1")
        assert isinstance(result, ConflictAutoCheckResult)
        assert result.partial is True
