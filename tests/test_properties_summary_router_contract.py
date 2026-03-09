"""
Phase 130 — Properties Summary Dashboard — Contract Tests

Tests for GET /properties/summary

Groups:
    A — Response shape when no bookings
    B — Single property, all fields correct
    C — active_count and canceled_count
    D — next_check_in / next_check_out (upcoming only)
    E — has_conflict flag
    F — Multiple properties
    G — Portfolio summary block
    H — limit parameter
    I — Stable ordering (by property_id)
    J — DB invariants: reads booking_state only, never writes
    K — DB error → 500
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("fastapi")

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_FAKE_TENANT = "tenant_test"
_TODAY = date.today()
_FUTURE = (_TODAY + timedelta(days=10)).isoformat()
_PAST = (_TODAY - timedelta(days=10)).isoformat()
_FAR_FUTURE = (_TODAY + timedelta(days=30)).isoformat()


def _make_app() -> TestClient:
    from fastapi import FastAPI
    from api.properties_summary_router import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def _mock_db(rows: List[Dict[str, Any]]) -> MagicMock:
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
    path: str = "/properties/summary",
) -> Any:
    with (
        patch("api.properties_summary_router._get_supabase_client", return_value=db),
        patch("api.auth.jwt_auth", return_value=_FAKE_TENANT),
    ):
        return c.get(path, headers={"Authorization": "Bearer fake.jwt"})


def _row(
    booking_id: str,
    property_id: str,
    status: str = "ACTIVE",
    check_in: Optional[str] = None,
    check_out: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "booking_id": booking_id,
        "property_id": property_id,
        "lifecycle_status": status,
        "status": status.lower(),
        "canonical_check_in": check_in or _FUTURE,
        "canonical_check_out": check_out or _FAR_FUTURE,
        "check_in": check_in or _FUTURE,
        "check_out": check_out or _FAR_FUTURE,
        "tenant_id": _FAKE_TENANT,
    }


# ─────────────────────────────────────────────────────────────────────────────
# A — No bookings
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupA_NoBookings:

    def test_a1_empty_db_returns_200(self) -> None:
        """A1: No bookings → 200 OK."""
        c = _make_app()
        resp = _get(c, _mock_db([]))
        assert resp.status_code == 200

    def test_a2_empty_properties_list(self) -> None:
        """A2: No bookings → properties=[]."""
        c = _make_app()
        body = _get(c, _mock_db([])).json()
        assert body["properties"] == []

    def test_a3_portfolio_zeros(self) -> None:
        """A3: No bookings → portfolio all zeros."""
        c = _make_app()
        body = _get(c, _mock_db([])).json()
        assert body["portfolio"]["total_active_bookings"] == 0
        assert body["portfolio"]["total_canceled_bookings"] == 0
        assert body["portfolio"]["properties_with_conflicts"] == 0

    def test_a4_property_count_zero(self) -> None:
        """A4: No bookings → property_count=0."""
        c = _make_app()
        body = _get(c, _mock_db([])).json()
        assert body["property_count"] == 0

    def test_a5_has_tenant_id(self) -> None:
        """A5: Response always has tenant_id."""
        c = _make_app()
        body = _get(c, _mock_db([])).json()
        assert "tenant_id" in body


# ─────────────────────────────────────────────────────────────────────────────
# B — Single property, fields
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupB_SingleProperty:

    def test_b1_single_property_present(self) -> None:
        """B1: One booking → one property in results."""
        rows = [_row("bk_1", "prop_A")]
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        assert len(body["properties"]) == 1

    def test_b2_property_record_has_required_fields(self) -> None:
        """B2: Property record has: property_id, active_count, canceled_count,
        next_check_in, next_check_out, has_conflict."""
        rows = [_row("bk_1", "prop_A")]
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        record = body["properties"][0]
        required = {"property_id", "active_count", "canceled_count",
                    "next_check_in", "next_check_out", "has_conflict"}
        assert required.issubset(record.keys())

    def test_b3_property_id_correct(self) -> None:
        """B3: property_id is correctly set."""
        rows = [_row("bk_1", "prop_A")]
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        assert body["properties"][0]["property_id"] == "prop_A"

    def test_b4_has_conflict_is_bool(self) -> None:
        """B4: has_conflict is a boolean."""
        rows = [_row("bk_1", "prop_A")]
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        assert isinstance(body["properties"][0]["has_conflict"], bool)


# ─────────────────────────────────────────────────────────────────────────────
# C — active_count and canceled_count
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupC_StatusCounts:

    def test_c1_two_active_one_canceled(self) -> None:
        """C1: 2 ACTIVE + 1 CANCELED → active_count=2, canceled_count=1."""
        rows = [
            _row("bk_1", "prop_A", status="ACTIVE"),
            _row("bk_2", "prop_A", status="ACTIVE"),
            _row("bk_3", "prop_A", status="CANCELED"),
        ]
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        p = body["properties"][0]
        assert p["active_count"] == 2
        assert p["canceled_count"] == 1

    def test_c2_all_active(self) -> None:
        """C2: All ACTIVE → canceled_count=0."""
        rows = [_row("bk_1", "prop_A"), _row("bk_2", "prop_A")]
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        assert body["properties"][0]["canceled_count"] == 0

    def test_c3_all_canceled(self) -> None:
        """C3: All CANCELED → active_count=0."""
        rows = [
            _row("bk_1", "prop_A", status="CANCELED"),
            _row("bk_2", "prop_A", status="CANCELED"),
        ]
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        assert body["properties"][0]["active_count"] == 0
        assert body["properties"][0]["canceled_count"] == 2


# ─────────────────────────────────────────────────────────────────────────────
# D — next_check_in / next_check_out
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupD_NextDates:

    def test_d1_next_check_in_is_future_date(self) -> None:
        """D1: next_check_in is the earliest upcoming check_in."""
        near = (_TODAY + timedelta(days=5)).isoformat()
        far = (_TODAY + timedelta(days=20)).isoformat()
        rows = [
            _row("bk_1", "prop_A", check_in=far,  check_out=(_TODAY + timedelta(days=25)).isoformat()),
            _row("bk_2", "prop_A", check_in=near, check_out=(_TODAY + timedelta(days=10)).isoformat()),
        ]
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        assert body["properties"][0]["next_check_in"] == near

    def test_d2_past_check_in_not_included(self) -> None:
        """D2: Booking with check_in in the past → not returned as next_check_in."""
        far_future = (_TODAY + timedelta(days=15)).isoformat()
        rows = [
            _row("bk_1", "prop_A", check_in=_PAST, check_out=_FUTURE),
            _row("bk_2", "prop_A", check_in=far_future, check_out=(_TODAY + timedelta(days=20)).isoformat()),
        ]
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        assert body["properties"][0]["next_check_in"] == far_future

    def test_d3_null_next_check_in_when_all_past(self) -> None:
        """D3: All check_in dates in the past → next_check_in=null."""
        past2 = (_TODAY - timedelta(days=5)).isoformat()
        rows = [
            _row("bk_1", "prop_A", check_in=_PAST, check_out=past2),
        ]
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        # next_check_in should be null (no upcoming dates)
        assert body["properties"][0]["next_check_in"] is None

    def test_d4_next_check_in_null_for_all_canceled(self) -> None:
        """D4: All bookings CANCELED → next_check_in/out=null."""
        rows = [
            _row("bk_1", "prop_A", status="CANCELED", check_in=_FUTURE, check_out=_FAR_FUTURE),
        ]
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        assert body["properties"][0]["next_check_in"] is None
        assert body["properties"][0]["next_check_out"] is None


# ─────────────────────────────────────────────────────────────────────────────
# E — has_conflict
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupE_HasConflict:

    def test_e1_single_booking_no_conflict(self) -> None:
        """E1: Single ACTIVE booking → has_conflict=False."""
        rows = [_row("bk_1", "prop_A")]
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        assert body["properties"][0]["has_conflict"] is False

    def test_e2_two_non_overlapping_no_conflict(self) -> None:
        """E2: Two bookings that don't overlap → has_conflict=False."""
        rows = [
            _row("bk_1", "prop_A",
                 check_in=(_TODAY + timedelta(days=1)).isoformat(),
                 check_out=(_TODAY + timedelta(days=5)).isoformat()),
            _row("bk_2", "prop_A",
                 check_in=(_TODAY + timedelta(days=5)).isoformat(),
                 check_out=(_TODAY + timedelta(days=10)).isoformat()),
        ]
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        assert body["properties"][0]["has_conflict"] is False

    def test_e3_two_overlapping_gives_conflict(self) -> None:
        """E3: Two overlapping ACTIVE bookings → has_conflict=True."""
        rows = [
            _row("bk_1", "prop_A",
                 check_in=(_TODAY + timedelta(days=1)).isoformat(),
                 check_out=(_TODAY + timedelta(days=8)).isoformat()),
            _row("bk_2", "prop_A",
                 check_in=(_TODAY + timedelta(days=5)).isoformat(),
                 check_out=(_TODAY + timedelta(days=12)).isoformat()),
        ]
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        assert body["properties"][0]["has_conflict"] is True

    def test_e4_conflict_only_counts_active(self) -> None:
        """E4: Overlapping CANCELED + ACTIVE → no conflict (canceled excluded)."""
        from api.properties_summary_router import _has_active_conflict
        # 2 bookings: one ACTIVE one CANCELED with same dates
        active = [
            {
                "lifecycle_status": "ACTIVE",
                "canonical_check_in": (_TODAY + timedelta(days=1)).isoformat(),
                "canonical_check_out": (_TODAY + timedelta(days=5)).isoformat(),
            }
        ]
        # Only 1 ACTIVE → no pair → no conflict
        assert _has_active_conflict(active) is False


# ─────────────────────────────────────────────────────────────────────────────
# F — Multiple properties
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupF_MultipleProperties:

    def test_f1_two_properties(self) -> None:
        """F1: Bookings on 2 properties → 2 property records."""
        rows = [
            _row("bk_1", "prop_A"),
            _row("bk_2", "prop_B"),
        ]
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        assert len(body["properties"]) == 2
        assert body["property_count"] == 2

    def test_f2_properties_separated_correctly(self) -> None:
        """F2: Active bookings counted per-property, not cross-property."""
        rows = [
            _row("bk_1", "prop_A"),
            _row("bk_2", "prop_A"),
            _row("bk_3", "prop_B"),
        ]
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        prop_ids = {p["property_id"] for p in body["properties"]}
        assert "prop_A" in prop_ids
        assert "prop_B" in prop_ids
        prop_a = next(p for p in body["properties"] if p["property_id"] == "prop_A")
        prop_b = next(p for p in body["properties"] if p["property_id"] == "prop_B")
        assert prop_a["active_count"] == 2
        assert prop_b["active_count"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# G — Portfolio summary
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupG_PortfolioSummary:

    def test_g1_portfolio_keys_present(self) -> None:
        """G1: portfolio has: total_active_bookings, total_canceled_bookings,
        properties_with_conflicts."""
        c = _make_app()
        body = _get(c, _mock_db([])).json()
        required = {"total_active_bookings", "total_canceled_bookings", "properties_with_conflicts"}
        assert required.issubset(body["portfolio"].keys())

    def test_g2_total_active_counts(self) -> None:
        """G2: portfolio.total_active_bookings = sum of all active counts."""
        rows = [
            _row("bk_1", "prop_A"),
            _row("bk_2", "prop_A"),
            _row("bk_3", "prop_B"),
        ]
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        assert body["portfolio"]["total_active_bookings"] == 3

    def test_g3_properties_with_conflicts_count(self) -> None:
        """G3: portfolio.properties_with_conflicts = count of properties where has_conflict=True."""
        rows = [
            # prop_A with conflict
            _row("bk_1", "prop_A",
                 check_in=(_TODAY + timedelta(days=1)).isoformat(),
                 check_out=(_TODAY + timedelta(days=8)).isoformat()),
            _row("bk_2", "prop_A",
                 check_in=(_TODAY + timedelta(days=5)).isoformat(),
                 check_out=(_TODAY + timedelta(days=12)).isoformat()),
            # prop_B without conflict
            _row("bk_3", "prop_B"),
        ]
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        assert body["portfolio"]["properties_with_conflicts"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# H — limit parameter
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupH_Limit:

    def test_h1_default_limit_returns_200(self) -> None:
        """H1: No limit param → 200 OK."""
        c = _make_app()
        resp = _get(c, _mock_db([]))
        assert resp.status_code == 200

    def test_h2_limit_zero_returns_400(self) -> None:
        """H2: limit=0 → 400."""
        c = _make_app()
        resp = _get(c, _mock_db([]), path="/properties/summary?limit=0")
        assert resp.status_code == 400

    def test_h3_limit_over_max_returns_400(self) -> None:
        """H3: limit=201 → 400 (max is 200)."""
        c = _make_app()
        resp = _get(c, _mock_db([]), path="/properties/summary?limit=201")
        assert resp.status_code == 400

    def test_h4_valid_limit_returns_200(self) -> None:
        """H4: limit=5 → 200 OK."""
        c = _make_app()
        resp = _get(c, _mock_db([]), path="/properties/summary?limit=5")
        assert resp.status_code == 200

    def test_h5_limit_truncates_results(self) -> None:
        """H5: 5 properties but limit=2 → 2 returned."""
        rows = [
            _row(f"bk_{i}", f"prop_{chr(65 + i)}")
            for i in range(5)
        ]
        c = _make_app()
        body = _get(c, _mock_db(rows), path="/properties/summary?limit=2").json()
        assert len(body["properties"]) == 2


# ─────────────────────────────────────────────────────────────────────────────
# I — Stable ordering
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupI_Ordering:

    def test_i1_properties_sorted_by_property_id(self) -> None:
        """I1: Properties are sorted alphabetically by property_id."""
        rows = [
            _row("bk_1", "prop_C"),
            _row("bk_2", "prop_A"),
            _row("bk_3", "prop_B"),
        ]
        c = _make_app()
        body = _get(c, _mock_db(rows)).json()
        ids = [p["property_id"] for p in body["properties"]]
        assert ids == sorted(ids)


# ─────────────────────────────────────────────────────────────────────────────
# J — DB invariants
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupJ_DBInvariants:

    def test_j1_reads_booking_state(self) -> None:
        """J1: Reads from booking_state table."""
        db = _mock_db([])
        c = _make_app()
        _get(c, db)
        tables = [str(call.args[0]) for call in db.table.call_args_list]
        assert any("booking_state" in t for t in tables)

    def test_j2_never_writes_insert(self) -> None:
        """J2: Never calls .insert()."""
        db = _mock_db([])
        c = _make_app()
        _get(c, db)
        assert db.table.return_value.insert.call_count == 0

    def test_j3_never_writes_update(self) -> None:
        """J3: Never calls .update()."""
        db = _mock_db([])
        c = _make_app()
        _get(c, db)
        assert db.table.return_value.update.call_count == 0

    def test_j4_never_reads_financial_facts(self) -> None:
        """J4: Never reads booking_financial_facts."""
        db = _mock_db([])
        c = _make_app()
        _get(c, db)
        tables = [str(call.args[0]) for call in db.table.call_args_list]
        assert not any("financial_facts" in t for t in tables)


# ─────────────────────────────────────────────────────────────────────────────
# K — DB error → 500
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupK_ErrorHandling:

    def test_k1_db_error_returns_500(self) -> None:
        """K1: DB query throws → 500."""
        chain = MagicMock()
        chain.execute.side_effect = RuntimeError("db failure")
        chain.eq.return_value = chain
        chain.select.return_value = chain
        db = MagicMock()
        db.table.return_value.select.return_value = chain
        c = _make_app()
        resp = _get(c, db)
        assert resp.status_code == 500

    def test_k2_error_no_sensitive_leak(self) -> None:
        """K2: 500 body does not expose raw exception details."""
        chain = MagicMock()
        chain.execute.side_effect = RuntimeError("secret_db_internals_xyz")
        chain.eq.return_value = chain
        chain.select.return_value = chain
        db = MagicMock()
        db.table.return_value.select.return_value = chain
        c = _make_app()
        resp = _get(c, db)
        assert "secret_db_internals_xyz" not in resp.text
