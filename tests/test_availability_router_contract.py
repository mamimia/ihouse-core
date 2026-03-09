"""
Phase 126 — Availability Projection Router — Contract Tests

Tests for GET /availability/{property_id}?from=&to=

Groups:
    A — Validation (missing params, invalid dates, bad range, max range)
    B — Happy path — vacant property (no bookings)
    C — Happy path — single booking (OCCUPIED days)
    D — CANCELED bookings are excluded
    E — CONFLICT detection (two bookings on same date)
    F — Date boundary semantics (check_out exclusive)
    G — Response shape invariants
    H — Never reads booking_financial_facts / tasks invariants
"""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("fastapi")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _booking_row(
    booking_id: str = "bookingcom_R001",
    check_in: str = "2026-04-10",
    check_out: str = "2026-04-15",
    lifecycle_status: str = "ACTIVE",
    property_id: str = "prop-1",
    tenant_id: str = "tenant_test",
) -> dict:
    return {
        "booking_id": booking_id,
        "canonical_check_in": check_in,
        "canonical_check_out": check_out,
        "lifecycle_status": lifecycle_status,
        "property_id": property_id,
        "tenant_id": tenant_id,
    }


def _mock_db(rows: list) -> MagicMock:
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=rows)
    chain.eq.return_value = chain
    chain.lt.return_value = chain
    chain.gt.return_value = chain
    chain.select.return_value = chain
    db = MagicMock()
    db.table.return_value.select.return_value = chain
    return db


def _make_app(db=None) -> TestClient:
    from fastapi import FastAPI
    from api.availability_router import router

    app = FastAPI()
    app.include_router(router)
    # Set a default supabase client so request.app.state.supabase doesn't
    # crash before validation runs. Individual tests patch at module level.
    app.state.supabase = db or MagicMock()
    return TestClient(app, raise_server_exceptions=False)


def _url(property_id: str = "prop-1", from_: str = "2026-04-01", to: str = "2026-04-11") -> str:
    return f"/availability/{property_id}?from={from_}&to={to}"


# ===========================================================================
# Group A — Validation
# ===========================================================================

class TestGroupA_Validation:

    def test_a1_missing_from_returns_400(self) -> None:
        """A1: Missing 'from' param → 400 VALIDATION_ERROR."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.availability_router._get_supabase_client", return_value=db):
            resp = c.get("/availability/prop-1?to=2026-04-10")
        assert resp.status_code == 400
        assert resp.json()["code"] == "VALIDATION_ERROR"

    def test_a2_missing_to_returns_400(self) -> None:
        """A2: Missing 'to' param → 400 VALIDATION_ERROR."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.availability_router._get_supabase_client", return_value=db):
            resp = c.get("/availability/prop-1?from=2026-04-01")
        assert resp.status_code == 400
        assert resp.json()["code"] == "VALIDATION_ERROR"

    def test_a3_invalid_from_format_returns_400(self) -> None:
        """A3: Non-ISO 'from' date → 400 VALIDATION_ERROR."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.availability_router._get_supabase_client", return_value=db):
            resp = c.get("/availability/prop-1?from=not-a-date&to=2026-04-10")
        assert resp.status_code == 400
        assert resp.json()["code"] == "VALIDATION_ERROR"

    def test_a4_invalid_to_format_returns_400(self) -> None:
        """A4: Non-ISO 'to' date → 400 VALIDATION_ERROR."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.availability_router._get_supabase_client", return_value=db):
            resp = c.get("/availability/prop-1?from=2026-04-01&to=foobar")
        assert resp.status_code == 400
        assert resp.json()["code"] == "VALIDATION_ERROR"

    def test_a5_from_equals_to_returns_400(self) -> None:
        """A5: from == to → 400 (zero-length range)."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.availability_router._get_supabase_client", return_value=db):
            resp = c.get("/availability/prop-1?from=2026-04-01&to=2026-04-01")
        assert resp.status_code == 400

    def test_a6_from_after_to_returns_400(self) -> None:
        """A6: from > to → 400 VALIDATION_ERROR."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.availability_router._get_supabase_client", return_value=db):
            resp = c.get("/availability/prop-1?from=2026-04-10&to=2026-04-01")
        assert resp.status_code == 400

    def test_a7_max_range_exceeded_returns_400(self) -> None:
        """A7: Range > 366 days → 400 VALIDATION_ERROR."""
        c = _make_app()
        db = _mock_db([])
        from_d = "2026-01-01"
        to_d = "2027-02-02"  # > 366 days
        with patch("api.availability_router._get_supabase_client", return_value=db):
            resp = c.get(f"/availability/prop-1?from={from_d}&to={to_d}")
        assert resp.status_code == 400
        assert resp.json()["code"] == "VALIDATION_ERROR"

    def test_a8_exactly_366_days_is_valid(self) -> None:
        """A8: Exactly 366-day range → 200 (boundary allowed)."""
        c = _make_app()
        db = _mock_db([])
        from_d = "2026-01-01"
        to_d = "2027-01-02"  # 366 days
        with patch("api.availability_router._get_supabase_client", return_value=db):
            resp = c.get(f"/availability/prop-1?from={from_d}&to={to_d}")
        assert resp.status_code == 200


# ===========================================================================
# Group B — Happy path — no bookings (all VACANT)
# ===========================================================================

class TestGroupB_VacantProperty:

    def test_b1_no_bookings_all_vacant(self) -> None:
        """B1: No ACTIVE bookings → all dates VACANT."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.availability_router._get_supabase_client", return_value=db):
            resp = c.get(_url(from_="2026-04-01", to="2026-04-05"))
        assert resp.status_code == 200
        body = resp.json()
        assert all(d["status"] == "VACANT" for d in body["dates"])

    def test_b2_response_has_property_id(self) -> None:
        """B2: Response contains property_id."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.availability_router._get_supabase_client", return_value=db):
            body = c.get(_url(property_id="villa-5")).json()
        assert body["property_id"] == "villa-5"

    def test_b3_days_count_matches_range(self) -> None:
        """B3: days = (to - from) in days."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.availability_router._get_supabase_client", return_value=db):
            body = c.get(_url(from_="2026-04-01", to="2026-04-06")).json()
        assert body["days"] == 5

    def test_b4_summary_vacant_matches_days(self) -> None:
        """B4: summary.vacant == days (all vacant)."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.availability_router._get_supabase_client", return_value=db):
            body = c.get(_url(from_="2026-04-01", to="2026-04-06")).json()
        assert body["summary"]["vacant"] == body["days"]
        assert body["summary"]["occupied"] == 0
        assert body["summary"]["conflict"] == 0

    def test_b5_each_date_has_required_fields(self) -> None:
        """B5: Each date entry has date, occupied, booking_id, status."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.availability_router._get_supabase_client", return_value=db):
            body = c.get(_url(from_="2026-04-01", to="2026-04-03")).json()
        for d in body["dates"]:
            assert "date" in d
            assert "occupied" in d
            assert "booking_id" in d
            assert "status" in d


# ===========================================================================
# Group C — Single ACTIVE booking
# ===========================================================================

class TestGroupC_ActiveBooking:

    def test_c1_booking_dates_marked_occupied(self) -> None:
        """C1: ACTIVE booking [Apr10,Apr13) → Apr10,11,12 = OCCUPIED."""
        c = _make_app()
        row = _booking_row(check_in="2026-04-10", check_out="2026-04-13")
        db = _mock_db([row])
        with patch("api.availability_router._get_supabase_client", return_value=db):
            body = c.get(_url(from_="2026-04-08", to="2026-04-15")).json()
        dates_by_date = {d["date"]: d for d in body["dates"]}
        assert dates_by_date["2026-04-10"]["status"] == "OCCUPIED"
        assert dates_by_date["2026-04-11"]["status"] == "OCCUPIED"
        assert dates_by_date["2026-04-12"]["status"] == "OCCUPIED"

    def test_c2_check_out_date_is_vacant(self) -> None:
        """C2: check_out date itself is VACANT (exclusive upper bound)."""
        c = _make_app()
        row = _booking_row(check_in="2026-04-10", check_out="2026-04-13")
        db = _mock_db([row])
        with patch("api.availability_router._get_supabase_client", return_value=db):
            body = c.get(_url(from_="2026-04-08", to="2026-04-15")).json()
        dates_by_date = {d["date"]: d for d in body["dates"]}
        assert dates_by_date["2026-04-13"]["status"] == "VACANT"

    def test_c3_booking_id_on_occupied_days(self) -> None:
        """C3: Occupied days have the correct booking_id."""
        c = _make_app()
        row = _booking_row(booking_id="bookingcom_R001", check_in="2026-04-10", check_out="2026-04-12")
        db = _mock_db([row])
        with patch("api.availability_router._get_supabase_client", return_value=db):
            body = c.get(_url(from_="2026-04-10", to="2026-04-13")).json()
        dates_by_date = {d["date"]: d for d in body["dates"]}
        assert dates_by_date["2026-04-10"]["booking_id"] == "bookingcom_R001"

    def test_c4_days_outside_booking_are_vacant(self) -> None:
        """C4: Days outside booking range are still VACANT."""
        c = _make_app()
        row = _booking_row(check_in="2026-04-10", check_out="2026-04-12")
        db = _mock_db([row])
        with patch("api.availability_router._get_supabase_client", return_value=db):
            body = c.get(_url(from_="2026-04-08", to="2026-04-15")).json()
        dates_by_date = {d["date"]: d for d in body["dates"]}
        assert dates_by_date["2026-04-08"]["status"] == "VACANT"
        assert dates_by_date["2026-04-14"]["status"] == "VACANT"

    def test_c5_summary_reflects_occupation(self) -> None:
        """C5: summary.occupied > 0 when booking present."""
        c = _make_app()
        row = _booking_row(check_in="2026-04-10", check_out="2026-04-12")
        db = _mock_db([row])
        with patch("api.availability_router._get_supabase_client", return_value=db):
            body = c.get(_url(from_="2026-04-08", to="2026-04-15")).json()
        assert body["summary"]["occupied"] == 2  # Apr10, Apr11


# ===========================================================================
# Group D — CANCELED bookings excluded
# ===========================================================================

class TestGroupD_CanceledExcluded:

    def test_d1_canceled_booking_dates_are_vacant(self) -> None:
        """D1: CANCELED booking → dates remain VACANT (filtered by DB query)."""
        c = _make_app()
        # DB returns [] because lifecycle_status=ACTIVE filter excludes CANCELED
        db = _mock_db([])
        with patch("api.availability_router._get_supabase_client", return_value=db):
            body = c.get(_url(from_="2026-04-01", to="2026-04-10")).json()
        assert body["summary"]["vacant"] == 9
        assert body["summary"]["occupied"] == 0

    def test_d2_db_queried_with_lifecycle_active(self) -> None:
        """D2: DB query uses lifecycle_status=ACTIVE filter (not in-memory)."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.availability_router._get_supabase_client", return_value=db):
            c.get(_url(from_="2026-04-01", to="2026-04-10"))
        # Verify .eq("lifecycle_status", "ACTIVE") was called
        calls = str(db.table.return_value.select.return_value.eq.call_args_list)
        assert "ACTIVE" in calls


# ===========================================================================
# Group E — CONFLICT detection
# ===========================================================================

class TestGroupE_ConflictDetection:

    def test_e1_two_bookings_same_date_marked_conflict(self) -> None:
        """E1: Two ACTIVE bookings overlapping same date → CONFLICT."""
        c = _make_app()
        rows = [
            _booking_row(booking_id="B001", check_in="2026-04-10", check_out="2026-04-12"),
            _booking_row(booking_id="B002", check_in="2026-04-11", check_out="2026-04-14"),
        ]
        db = _mock_db(rows)
        with patch("api.availability_router._get_supabase_client", return_value=db):
            body = c.get(_url(from_="2026-04-08", to="2026-04-15")).json()
        dates_by_date = {d["date"]: d for d in body["dates"]}
        assert dates_by_date["2026-04-11"]["status"] == "CONFLICT"

    def test_e2_conflict_summary_incremented(self) -> None:
        """E2: summary.conflict > 0 when conflict detected."""
        c = _make_app()
        rows = [
            _booking_row(booking_id="B001", check_in="2026-04-10", check_out="2026-04-12"),
            _booking_row(booking_id="B002", check_in="2026-04-11", check_out="2026-04-14"),
        ]
        db = _mock_db(rows)
        with patch("api.availability_router._get_supabase_client", return_value=db):
            body = c.get(_url(from_="2026-04-08", to="2026-04-15")).json()
        assert body["summary"]["conflict"] >= 1

    def test_e3_non_overlapping_bookings_no_conflict(self) -> None:
        """E3: Adjacent (non-overlapping) bookings → no CONFLICT."""
        c = _make_app()
        rows = [
            _booking_row(booking_id="B001", check_in="2026-04-10", check_out="2026-04-12"),
            _booking_row(booking_id="B002", check_in="2026-04-12", check_out="2026-04-15"),
        ]
        db = _mock_db(rows)
        with patch("api.availability_router._get_supabase_client", return_value=db):
            body = c.get(_url(from_="2026-04-08", to="2026-04-16")).json()
        assert body["summary"]["conflict"] == 0


# ===========================================================================
# Group F — Date boundary semantics
# ===========================================================================

class TestGroupF_DateBoundary:

    def test_f1_single_day_range(self) -> None:
        """F1: from=2026-04-10, to=2026-04-11 → 1 day."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.availability_router._get_supabase_client", return_value=db):
            body = c.get("/availability/prop-1?from=2026-04-10&to=2026-04-11").json()
        assert body["days"] == 1
        assert body["dates"][0]["date"] == "2026-04-10"

    def test_f2_booking_starting_at_from_date(self) -> None:
        """F2: Booking starting exactly at 'from' date is included."""
        c = _make_app()
        row = _booking_row(check_in="2026-04-01", check_out="2026-04-03")
        db = _mock_db([row])
        with patch("api.availability_router._get_supabase_client", return_value=db):
            body = c.get("/availability/prop-1?from=2026-04-01&to=2026-04-05").json()
        dates_by_date = {d["date"]: d for d in body["dates"]}
        assert dates_by_date["2026-04-01"]["status"] == "OCCUPIED"

    def test_f3_booking_ending_at_to_date_checkout_exclusive(self) -> None:
        """F3: Booking ending at 'to' date — check_out exclusive, so last day vacant."""
        c = _make_app()
        row = _booking_row(check_in="2026-04-01", check_out="2026-04-05")
        db = _mock_db([row])
        with patch("api.availability_router._get_supabase_client", return_value=db):
            body = c.get("/availability/prop-1?from=2026-04-01&to=2026-04-05").json()
        dates_by_date = {d["date"]: d for d in body["dates"]}
        # Apr04 should be OCCUPIED, Apr05 is not in range (to exclusive)
        assert dates_by_date["2026-04-04"]["status"] == "OCCUPIED"
        assert "2026-04-05" not in dates_by_date


# ===========================================================================
# Group G — Response shape invariants
# ===========================================================================

class TestGroupG_ResponseShape:

    def test_g1_response_has_from_to_fields(self) -> None:
        """G1: Response contains 'from' and 'to' fields."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.availability_router._get_supabase_client", return_value=db):
            body = c.get(_url(from_="2026-04-01", to="2026-04-05")).json()
        assert "from" in body
        assert "to" in body

    def test_g2_dates_sorted_chronologically(self) -> None:
        """G2: dates list is in chronological order."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.availability_router._get_supabase_client", return_value=db):
            body = c.get(_url(from_="2026-04-01", to="2026-04-06")).json()
        date_strs = [d["date"] for d in body["dates"]]
        assert date_strs == sorted(date_strs)

    def test_g3_booking_id_null_for_vacant(self) -> None:
        """G3: booking_id is null for VACANT days."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.availability_router._get_supabase_client", return_value=db):
            body = c.get(_url(from_="2026-04-01", to="2026-04-03")).json()
        for d in body["dates"]:
            assert d["booking_id"] is None

    def test_g4_summary_keys_present(self) -> None:
        """G4: summary has vacant, occupied, conflict keys."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.availability_router._get_supabase_client", return_value=db):
            body = c.get(_url()).json()
        assert "vacant" in body["summary"]
        assert "occupied" in body["summary"]
        assert "conflict" in body["summary"]

    def test_g5_status_values_are_valid_enum(self) -> None:
        """G5: All status values are one of VACANT/OCCUPIED/CONFLICT."""
        c = _make_app()
        row = _booking_row(check_in="2026-04-03", check_out="2026-04-05")
        db = _mock_db([row])
        with patch("api.availability_router._get_supabase_client", return_value=db):
            body = c.get(_url(from_="2026-04-01", to="2026-04-08")).json()
        valid = {"VACANT", "OCCUPIED", "CONFLICT"}
        for d in body["dates"]:
            assert d["status"] in valid


# ===========================================================================
# Group H — DB table invariants
# ===========================================================================

class TestGroupH_DBInvariants:

    def test_h1_never_queries_booking_financial_facts(self) -> None:
        """H1: /availability never reads booking_financial_facts."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.availability_router._get_supabase_client", return_value=db):
            c.get(_url())
        calls = [str(c) for c in db.table.call_args_list]
        assert not any("booking_financial_facts" in c for c in calls)

    def test_h2_never_queries_tasks(self) -> None:
        """H2: /availability never reads tasks table."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.availability_router._get_supabase_client", return_value=db):
            c.get(_url())
        calls = [str(c) for c in db.table.call_args_list]
        assert not any("tasks" in c for c in calls)

    def test_h3_never_writes_to_booking_state(self) -> None:
        """H3: /availability never calls .insert() or .update() on booking_state."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.availability_router._get_supabase_client", return_value=db):
            c.get(_url())
        # Should not have called .insert or .update
        insert_calls = db.table.return_value.insert.call_count
        update_calls = db.table.return_value.update.call_count
        assert insert_calls == 0
        assert update_calls == 0

    def test_h4_500_on_db_error(self) -> None:
        """H4: DB exception → 500 INTERNAL_ERROR."""
        chain = MagicMock()
        chain.execute.side_effect = RuntimeError("db exploded")
        chain.eq.return_value = chain
        chain.lt.return_value = chain
        chain.gt.return_value = chain
        chain.select.return_value = chain
        db = MagicMock()
        db.table.return_value.select.return_value = chain
        c = _make_app(db=db)
        resp = c.get(_url())
        assert resp.status_code == 500
        if resp.content:
            body = resp.json()
            assert body.get("code") == "INTERNAL_ERROR"

    def test_h5_500_does_not_leak_db_error(self) -> None:
        """H5: 500 body does not contain raw exception text."""
        chain = MagicMock()
        chain.execute.side_effect = RuntimeError("secret_connection_string")
        chain.eq.return_value = chain
        chain.lt.return_value = chain
        chain.gt.return_value = chain
        chain.select.return_value = chain
        db = MagicMock()
        db.table.return_value.select.return_value = chain
        c = _make_app(db=db)
        resp = c.get(_url())
        assert resp.status_code == 500
        assert "secret_connection_string" not in str(resp.content)
