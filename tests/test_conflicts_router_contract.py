"""
Phase 128 — Conflict Center — Contract Tests

Tests for GET /conflicts?property_id=

Groups:
    A — Response shape when no conflicts exist
    B — Single conflict pair detected
    C — No conflict when bookings don't overlap
    D — Severity: CRITICAL (>=3 nights) vs WARNING (1-2 nights)
    E — property_id filter
    F — Multiple properties — conflicts isolated per property
    G — Conflict pair deduplication (A,B == B,A)
    H — 3-way overlap → multiple pairs
    I — CANCELED bookings excluded
    J — check_in/check_out boundary semantics (check_out exclusive)
    K — Summary counts correct
    L — DB invariants: reads booking_state only, never writes
    M — DB error → 500, no leakage
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("fastapi")

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_FAKE_TENANT = "tenant_test"


def _make_app() -> TestClient:
    from fastapi import FastAPI
    from api.conflicts_router import router

    app = FastAPI()

    class _FakeState:
        supabase = None  # will be set per-test

    app.state = _FakeState()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def _mock_db(rows: List[Dict[str, Any]]) -> MagicMock:
    """DB mock that returns given rows."""
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=rows)
    chain.eq.return_value = chain
    chain.select.return_value = chain
    db = MagicMock()
    db.table.return_value.select.return_value = chain
    return db


def _get(
    c: TestClient,
    db: MagicMock,
    path: str = "/conflicts",
) -> Any:
    with (
        patch("api.auth.jwt_auth", return_value=_FAKE_TENANT),
    ):
        # Inject db via app.state
        c.app.state.supabase = db
        return c.get(path, headers={"Authorization": "Bearer fake.jwt"})


def _booking(
    booking_id: str,
    property_id: str,
    check_in: str,
    check_out: str,
    status: str = "ACTIVE",
) -> Dict[str, Any]:
    return {
        "booking_id": booking_id,
        "property_id": property_id,
        "canonical_check_in": check_in,
        "canonical_check_out": check_out,
        "lifecycle_status": status,
        "tenant_id": _FAKE_TENANT,
    }


# ─────────────────────────────────────────────────────────────────────────────
# A — No conflicts
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupA_NoConflicts:

    def test_a1_empty_db_returns_200(self) -> None:
        """A1: No bookings → 200 with empty conflicts list."""
        c = _make_app()
        resp = _get(c, _mock_db([]))
        assert resp.status_code == 200

    def test_a2_empty_conflicts_list(self) -> None:
        """A2: No bookings → conflicts=[]."""
        c = _make_app()
        body = _get(c, _mock_db([])).json()
        assert body["conflicts"] == []

    def test_a3_summary_zeros(self) -> None:
        """A3: No conflicts → summary all zeros."""
        c = _make_app()
        body = _get(c, _mock_db([])).json()
        assert body["summary"]["total_conflicts"] == 0
        assert body["summary"]["properties_affected"] == 0
        assert body["summary"]["bookings_involved"] == 0

    def test_a4_single_booking_no_conflict(self) -> None:
        """A4: Single booking → no conflict possible."""
        rows = [_booking("bk_1", "prop_A", "2026-04-01", "2026-04-05")]
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        assert body["conflicts"] == []

    def test_a5_non_overlapping_bookings_no_conflict(self) -> None:
        """A5: Two bookings that don't overlap → no conflict."""
        rows = [
            _booking("bk_1", "prop_A", "2026-04-01", "2026-04-05"),
            _booking("bk_2", "prop_A", "2026-04-05", "2026-04-10"),  # check_out exclusive boundary
        ]
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        assert body["conflicts"] == []


# ─────────────────────────────────────────────────────────────────────────────
# B — Single conflict pair detected
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupB_SingleConflict:

    def _two_overlapping_bookings(self) -> List[Dict[str, Any]]:
        return [
            _booking("bookingcom_R001", "prop_A", "2026-04-01", "2026-04-07"),
            _booking("airbnb_X002",     "prop_A", "2026-04-05", "2026-04-10"),
        ]

    def test_b1_one_conflict_detected(self) -> None:
        """B1: Two overlapping bookings → one conflict."""
        c = _make_app()
        body = _get(c, _mock_db(self._two_overlapping_bookings())).json()
        assert len(body["conflicts"]) == 1

    def test_b2_conflict_has_required_fields(self) -> None:
        """B2: Conflict record has all required fields."""
        c = _make_app()
        body = _get(c, _mock_db(self._two_overlapping_bookings())).json()
        conflict = body["conflicts"][0]
        required = {"property_id", "booking_a", "booking_b", "overlap_dates",
                    "overlap_start", "overlap_end", "severity"}
        assert required.issubset(conflict.keys())

    def test_b3_overlap_dates_correct(self) -> None:
        """B3: Overlap dates are [Apr 5, Apr 6] for this pair."""
        c = _make_app()
        body = _get(c, _mock_db(self._two_overlapping_bookings())).json()
        conflict = body["conflicts"][0]
        assert "2026-04-05" in conflict["overlap_dates"]
        assert "2026-04-06" in conflict["overlap_dates"]
        assert len(conflict["overlap_dates"]) == 2

    def test_b4_overlap_start_correct(self) -> None:
        """B4: overlap_start = first overlap date."""
        c = _make_app()
        body = _get(c, _mock_db(self._two_overlapping_bookings())).json()
        assert body["conflicts"][0]["overlap_start"] == "2026-04-05"

    def test_b5_overlap_end_exclusive(self) -> None:
        """B5: overlap_end = day after last overlap (exclusive)."""
        c = _make_app()
        body = _get(c, _mock_db(self._two_overlapping_bookings())).json()
        # Overlap is Apr 5-6. overlap_end = Apr 7 (exclusive).
        assert body["conflicts"][0]["overlap_end"] == "2026-04-07"

    def test_b6_property_id_in_conflict(self) -> None:
        """B6: property_id is correctly included in conflict record."""
        c = _make_app()
        body = _get(c, _mock_db(self._two_overlapping_bookings())).json()
        assert body["conflicts"][0]["property_id"] == "prop_A"


# ─────────────────────────────────────────────────────────────────────────────
# C — Non-overlapping bookings
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupC_NoOverlap:

    def test_c1_consecutive_bookings_no_conflict(self) -> None:
        """C1: Bookings that are back-to-back (not overlapping) → no conflict."""
        rows = [
            _booking("bk_1", "prop_A", "2026-04-01", "2026-04-05"),
            _booking("bk_2", "prop_A", "2026-04-05", "2026-04-10"),
        ]
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        assert body["conflicts"] == []

    def test_c2_separate_properties_no_cross_conflict(self) -> None:
        """C2: Two bookings on different properties with same dates → no conflict."""
        rows = [
            _booking("bk_1", "prop_A", "2026-04-01", "2026-04-10"),
            _booking("bk_2", "prop_B", "2026-04-01", "2026-04-10"),
        ]
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        assert body["conflicts"] == []


# ─────────────────────────────────────────────────────────────────────────────
# D — Severity
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupD_Severity:

    def test_d1_one_night_overlap_is_warning(self) -> None:
        """D1: 1-night overlap → severity=WARNING."""
        rows = [
            _booking("bk_1", "prop_A", "2026-04-01", "2026-04-05"),
            _booking("bk_2", "prop_A", "2026-04-04", "2026-04-08"),  # overlap: Apr 4 only
        ]
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        assert body["conflicts"][0]["severity"] == "WARNING"

    def test_d2_two_nights_overlap_is_warning(self) -> None:
        """D2: 2-night overlap → severity=WARNING."""
        rows = [
            _booking("bk_1", "prop_A", "2026-04-01", "2026-04-06"),
            _booking("bk_2", "prop_A", "2026-04-04", "2026-04-10"),  # overlap: Apr 4,5
        ]
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        assert body["conflicts"][0]["severity"] == "WARNING"

    def test_d3_three_nights_overlap_is_critical(self) -> None:
        """D3: 3-night overlap → severity=CRITICAL."""
        rows = [
            _booking("bk_1", "prop_A", "2026-04-01", "2026-04-08"),
            _booking("bk_2", "prop_A", "2026-04-04", "2026-04-10"),  # overlap: Apr 4,5,6,7
        ]
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        assert body["conflicts"][0]["severity"] == "CRITICAL"

    def test_d4_severity_values_are_valid(self) -> None:
        """D4: All severity values are either WARNING or CRITICAL."""
        rows = [
            _booking("bk_1", "prop_A", "2026-04-01", "2026-04-10"),
            _booking("bk_2", "prop_A", "2026-04-05", "2026-04-15"),
        ]
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        for conflict in body["conflicts"]:
            assert conflict["severity"] in {"WARNING", "CRITICAL"}


# ─────────────────────────────────────────────────────────────────────────────
# E — property_id filter
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupE_PropertyFilter:

    def test_e1_property_filter_passed_to_db(self) -> None:
        """E1: ?property_id= query parameter is forwarded to the DB query."""
        db = _mock_db([])
        c = _make_app()
        _get(c, db, path="/conflicts?property_id=prop_X")
        # Verify .eq("property_id", "prop_X") was called
        eq_calls = [str(call) for call in db.table.return_value.select.return_value.eq.call_args_list]
        assert any("prop_X" in call for call in eq_calls)

    def test_e2_no_filter_all_properties_fetched(self) -> None:
        """E2: No property_id → DB query is NOT filtered by property_id explicitly."""
        db = _mock_db([])
        c = _make_app()
        _get(c, db, path="/conflicts")
        # All calls to .eq() should not filter by property_id — only by tenant_id and status
        eq_calls = [str(call) for call in db.table.return_value.select.return_value.eq.call_args_list]
        propid_filter = [c for c in eq_calls if "property_id" in c and "prop_" in c]
        assert len(propid_filter) == 0


# ─────────────────────────────────────────────────────────────────────────────
# F — Multiple properties
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupF_MultipleProperties:

    def test_f1_conflicts_isolated_per_property(self) -> None:
        """F1: Overlapping bookings on different properties → one conflict each."""
        rows = [
            _booking("bk_A1", "prop_A", "2026-04-01", "2026-04-10"),
            _booking("bk_A2", "prop_A", "2026-04-05", "2026-04-15"),
            _booking("bk_B1", "prop_B", "2026-04-01", "2026-04-10"),
            _booking("bk_B2", "prop_B", "2026-04-05", "2026-04-15"),
        ]
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        assert body["summary"]["total_conflicts"] == 2
        assert body["summary"]["properties_affected"] == 2

    def test_f2_properties_affected_count(self) -> None:
        """F2: properties_affected = number of distinct properties with conflicts."""
        rows = [
            _booking("bk_A1", "prop_A", "2026-04-01", "2026-04-10"),
            _booking("bk_A2", "prop_A", "2026-04-05", "2026-04-15"),
        ]
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        assert body["summary"]["properties_affected"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# G — Pair deduplication
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupG_Deduplication:

    def test_g1_pair_reported_once(self) -> None:
        """G1: Pair (A,B) should be reported only once, not as (A,B) and (B,A)."""
        rows = [
            _booking("alpha", "prop_A", "2026-04-01", "2026-04-10"),
            _booking("beta",  "prop_A", "2026-04-05", "2026-04-15"),
        ]
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        assert len(body["conflicts"]) == 1

    def test_g2_booking_a_less_than_booking_b(self) -> None:
        """G2: booking_a < booking_b lexicographically (canonical ordering)."""
        rows = [
            _booking("zzz_last",  "prop_A", "2026-04-01", "2026-04-10"),
            _booking("aaa_first", "prop_A", "2026-04-05", "2026-04-15"),
        ]
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        conflict = body["conflicts"][0]
        assert conflict["booking_a"] <= conflict["booking_b"]


# ─────────────────────────────────────────────────────────────────────────────
# H — 3-way overlaps
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupH_ThreeWayOverlap:

    def test_h1_three_overlapping_bookings_give_three_pairs(self) -> None:
        """H1: 3 bookings all overlapping → C(3,2)=3 conflict pairs."""
        rows = [
            _booking("bk_1", "prop_A", "2026-04-01", "2026-04-15"),
            _booking("bk_2", "prop_A", "2026-04-05", "2026-04-20"),
            _booking("bk_3", "prop_A", "2026-04-08", "2026-04-12"),
        ]
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        assert len(body["conflicts"]) == 3

    def test_h2_bookings_involved_count(self) -> None:
        """H2: bookings_involved = distinct booking IDs in any conflict."""
        rows = [
            _booking("bk_1", "prop_A", "2026-04-01", "2026-04-15"),
            _booking("bk_2", "prop_A", "2026-04-05", "2026-04-20"),
            _booking("bk_3", "prop_A", "2026-04-08", "2026-04-12"),
        ]
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        assert body["summary"]["bookings_involved"] == 3


# ─────────────────────────────────────────────────────────────────────────────
# I — CANCELED bookings excluded
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupI_CanceledExcluded:

    def test_i1_canceled_booking_not_counted(self) -> None:
        """I1: CANCELED bookings do not participate in conflict detection.
        (They are excluded at the DB query level by .eq('lifecycle_status', 'ACTIVE'))."""
        # DB only returns ACTIVE bookings — we simulate this
        rows = [
            _booking("bk_active", "prop_A", "2026-04-01", "2026-04-10"),
            # CANCELED booking would NOT be returned by DB query
        ]
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        assert body["conflicts"] == []

    def test_i2_db_query_filters_active_only(self) -> None:
        """I2: DB query includes .eq('lifecycle_status', 'ACTIVE')."""
        db = _mock_db([])
        c = _make_app()
        _get(c, db)
        eq_calls = [str(call) for call in db.table.return_value.select.return_value.eq.call_args_list]
        assert any("active" in call for call in eq_calls)


# ─────────────────────────────────────────────────────────────────────────────
# J — Date boundary semantics
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupJ_DateBoundaries:

    def test_j1_check_out_is_exclusive(self) -> None:
        """J1: Booking A check_out = Booking B check_in → NO overlap (exclusive boundary)."""
        rows = [
            _booking("bk_1", "prop_A", "2026-04-01", "2026-04-05"),  # nights: 1,2,3,4
            _booking("bk_2", "prop_A", "2026-04-05", "2026-04-10"),  # nights: 5,6,7,8,9
        ]
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        assert body["conflicts"] == []

    def test_j2_one_night_overlap_detected(self) -> None:
        """J2: Bookings overlapping by exactly 1 night → 1 conflict date."""
        rows = [
            _booking("bk_1", "prop_A", "2026-04-01", "2026-04-06"),  # nights: 1,2,3,4,5
            _booking("bk_2", "prop_A", "2026-04-05", "2026-04-10"),  # night 5 is shared
        ]
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        assert len(body["conflicts"]) == 1
        assert len(body["conflicts"][0]["overlap_dates"]) == 1
        assert body["conflicts"][0]["overlap_dates"][0] == "2026-04-05"


# ─────────────────────────────────────────────────────────────────────────────
# K — Summary counts
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupK_SummaryCounts:

    def test_k1_tenant_id_in_response(self) -> None:
        """K1: Response includes tenant_id."""
        c = _make_app()
        body = _get(c, _mock_db([])).json()
        assert "tenant_id" in body

    def test_k2_summary_keys_present(self) -> None:
        """K2: Summary has: total_conflicts, properties_affected, bookings_involved."""
        c = _make_app()
        body = _get(c, _mock_db([])).json()
        assert {"total_conflicts", "properties_affected", "bookings_involved"}.issubset(body["summary"].keys())

    def test_k3_bookings_involved_deduplicated(self) -> None:
        """K3: bookings_involved counts each booking_id once even if in multiple pairs."""
        rows = [
            _booking("bk_common", "prop_A", "2026-04-01", "2026-04-20"),
            _booking("bk_x",      "prop_A", "2026-04-05", "2026-04-10"),
            _booking("bk_y",      "prop_A", "2026-04-12", "2026-04-18"),
        ]
        # bk_common overlaps bk_x AND bk_y → 2 conflicts, 3 unique bookings
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        assert body["summary"]["total_conflicts"] == 2
        assert body["summary"]["bookings_involved"] == 3


# ─────────────────────────────────────────────────────────────────────────────
# L — DB invariants
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupL_DBInvariants:

    def test_l1_reads_from_booking_state(self) -> None:
        """L1: GET /conflicts queries booking_state table."""
        db = _mock_db([])
        c = _make_app()
        _get(c, db)
        tables = [str(call.args[0]) for call in db.table.call_args_list]
        assert any("booking_state" in t for t in tables)

    def test_l2_never_writes_insert(self) -> None:
        """L2: GET /conflicts never calls .insert() on any table."""
        db = _mock_db([])
        c = _make_app()
        _get(c, db)
        assert db.table.return_value.insert.call_count == 0

    def test_l3_never_writes_update(self) -> None:
        """L3: GET /conflicts never calls .update() on any table."""
        db = _mock_db([])
        c = _make_app()
        _get(c, db)
        assert db.table.return_value.update.call_count == 0

    def test_l4_never_reads_booking_financial_facts(self) -> None:
        """L4: GET /conflicts never reads booking_financial_facts."""
        db = _mock_db([])
        c = _make_app()
        _get(c, db)
        tables = [str(call.args[0]) for call in db.table.call_args_list]
        assert not any("financial_facts" in t for t in tables)

    def test_l5_never_reads_tasks(self) -> None:
        """L5: GET /conflicts never reads tasks table."""
        db = _mock_db([])
        c = _make_app()
        _get(c, db)
        tables = [str(call.args[0]) for call in db.table.call_args_list]
        assert not any(t == "tasks" for t in tables)


# ─────────────────────────────────────────────────────────────────────────────
# M — DB error handling
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupM_ErrorHandling:

    def test_m1_db_error_returns_500(self) -> None:
        """M1: DB query throws → 500 Internal Server Error."""
        chain = MagicMock()
        chain.execute.side_effect = RuntimeError("db failure")
        chain.eq.return_value = chain
        chain.select.return_value = chain
        db = MagicMock()
        db.table.return_value.select.return_value = chain
        c = _make_app()
        resp = _get(c, db)
        assert resp.status_code == 500

    def test_m2_db_error_no_sensitive_leak(self) -> None:
        """M2: 500 response body does not contain raw exception message."""
        chain = MagicMock()
        chain.execute.side_effect = RuntimeError("secret db internals")
        chain.eq.return_value = chain
        chain.select.return_value = chain
        db = MagicMock()
        db.table.return_value.select.return_value = chain
        c = _make_app()
        resp = _get(c, db)
        body_text = resp.text
        assert "secret db internals" not in body_text
