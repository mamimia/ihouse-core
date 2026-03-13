"""
Phase 129 — Booking Search Enhancement — Contract Tests

Tests for GET /bookings additions:
  - source (OTA provider) filter
  - check_out_from / check_out_to date range
  - sort_by (check_in | check_out | updated_at | created_at)
  - sort_dir (asc | desc)
  - sort_by and sort_dir reflected in response
  - validation for new parameters

Groups:
    A — source filter
    B — check_out range filters
    C — sort_by validation and forwarding
    D — sort_dir validation and forwarding
    E — combined filters (source + check_out + sort)
    F — response shape includes sort_by and sort_dir
    G — backward compatibility (existing callers unaffected)
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
    from api.bookings_router import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def _mock_db(rows: List[Dict[str, Any]]) -> MagicMock:
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=rows)
    chain.eq.return_value = chain
    chain.gte.return_value = chain
    chain.lte.return_value = chain
    chain.limit.return_value = chain
    chain.order.return_value = chain
    chain.select.return_value = chain
    db = MagicMock()
    db.table.return_value.select.return_value = chain
    return db


def _get(
    c: TestClient,
    db: MagicMock,
    path: str = "/bookings",
) -> Any:
    with (
        patch("api.bookings_router._get_supabase_client", return_value=db),
        patch("api.auth.jwt_auth", return_value=_FAKE_TENANT),
    ):
        return c.get(path, headers={"Authorization": "Bearer fake.jwt"})


def _booking_row(
    booking_id: str = "bk_1",
    source: str = "bookingcom",
    check_in: str = "2026-04-01",
    check_out: str = "2026-04-07",
) -> Dict[str, Any]:
    return {
        "booking_id": booking_id,
        "tenant_id": _FAKE_TENANT,
        "source": source,
        "reservation_ref": "R001",
        "property_id": "prop_A",
        "status": "active",
        "check_in": check_in,
        "check_out": check_out,
        "lifecycle_status": "ACTIVE",
        "version": 1,
        "created_at": "2026-03-01T00:00:00Z",
        "updated_at": "2026-03-09T00:00:00Z",
    }


# ─────────────────────────────────────────────────────────────────────────────
# A — source filter
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupA_SourceFilter:

    def test_a1_source_filter_forwarded_to_db(self) -> None:
        """A1: ?source=airbnb → .eq('source', 'airbnb') called on DB query."""
        db = _mock_db([])
        c = _make_app()
        _get(c, db, "/bookings?source=airbnb")
        eq_calls = [str(call) for call in db.table.return_value.select.return_value.eq.call_args_list]
        assert any("airbnb" in call for call in eq_calls)

    def test_a2_no_source_filter_not_forwarded(self) -> None:
        """A2: No source param → .eq('source', ...) not called."""
        db = _mock_db([])
        c = _make_app()
        _get(c, db, "/bookings")
        eq_calls = [str(call) for call in db.table.return_value.select.return_value.eq.call_args_list]
        source_filters = [c for c in eq_calls if "'source'" in c]
        assert len(source_filters) == 0

    def test_a3_source_filter_returns_200(self) -> None:
        """A3: Valid source filter → 200 OK."""
        db = _mock_db([_booking_row(source="airbnb")])
        c = _make_app()
        resp = _get(c, db, "/bookings?source=airbnb")
        assert resp.status_code == 200

    def test_a4_all_providers_accepted(self) -> None:
        """A4: Any provider string accepted (no whitelist — DB handles it)."""
        for provider in ["bookingcom", "airbnb", "expedia", "agoda", "tripcom",
                         "hotelbeds", "rakuten", "despegar"]:
            db = _mock_db([])
            c = _make_app()
            resp = _get(c, db, f"/bookings?source={provider}")
            assert resp.status_code == 200, f"Failed for provider: {provider}"


# ─────────────────────────────────────────────────────────────────────────────
# B — check_out range filters
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupB_CheckOutRange:

    def test_b1_check_out_from_forwarded(self) -> None:
        """B1: ?check_out_from=2026-04-01 → .gte('check_out', '2026-04-01') called."""
        db = _mock_db([])
        c = _make_app()
        _get(c, db, "/bookings?check_out_from=2026-04-01")
        gte_calls = [str(call) for call in db.table.return_value.select.return_value.gte.call_args_list]
        assert any("check_out" in call and "2026-04-01" in call for call in gte_calls)

    def test_b2_check_out_to_forwarded(self) -> None:
        """B2: ?check_out_to=2026-04-30 → .lte('check_out', '2026-04-30') called."""
        db = _mock_db([])
        c = _make_app()
        _get(c, db, "/bookings?check_out_to=2026-04-30")
        lte_calls = [str(call) for call in db.table.return_value.select.return_value.lte.call_args_list]
        assert any("check_out" in call and "2026-04-30" in call for call in lte_calls)

    def test_b3_invalid_check_out_from_returns_400(self) -> None:
        """B3: Invalid check_out_from format → 400 VALIDATION_ERROR."""
        db = _mock_db([])
        c = _make_app()
        resp = _get(c, db, "/bookings?check_out_from=not-a-date")
        assert resp.status_code == 400

    def test_b4_invalid_check_out_to_returns_400(self) -> None:
        """B4: Invalid check_out_to format → 400 VALIDATION_ERROR."""
        db = _mock_db([])
        c = _make_app()
        resp = _get(c, db, "/bookings?check_out_to=2026-13-01")
        assert resp.status_code == 400

    def test_b5_check_out_range_returns_200(self) -> None:
        """B5: Valid check_out range → 200 OK."""
        db = _mock_db([])
        c = _make_app()
        resp = _get(c, db, "/bookings?check_out_from=2026-04-01&check_out_to=2026-04-30")
        assert resp.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# C — sort_by validation and forwarding
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupC_SortBy:

    def test_c1_sort_by_check_in_forwarded(self) -> None:
        """C1: ?sort_by=check_in → .order('check_in', ...) called."""
        db = _mock_db([])
        c = _make_app()
        _get(c, db, "/bookings?sort_by=check_in")
        order_calls = [str(call) for call in db.table.return_value.select.return_value.order.call_args_list]
        assert any("check_in" in call for call in order_calls)

    def test_c2_sort_by_check_out_forwarded(self) -> None:
        """C2: ?sort_by=check_out → .order('check_out', ...) called."""
        db = _mock_db([])
        c = _make_app()
        _get(c, db, "/bookings?sort_by=check_out")
        order_calls = [str(call) for call in db.table.return_value.select.return_value.order.call_args_list]
        assert any("check_out" in call for call in order_calls)

    def test_c3_sort_by_updated_at_forwarded(self) -> None:
        """C3: ?sort_by=updated_at → .order('updated_at', ...) called."""
        db = _mock_db([])
        c = _make_app()
        _get(c, db, "/bookings?sort_by=updated_at")
        order_calls = [str(call) for call in db.table.return_value.select.return_value.order.call_args_list]
        assert any("updated_at" in call for call in order_calls)

    def test_c4_sort_by_created_at_forwarded(self) -> None:
        """C4: ?sort_by=created_at → .order('created_at', ...) called."""
        db = _mock_db([])
        c = _make_app()
        _get(c, db, "/bookings?sort_by=created_at")
        order_calls = [str(call) for call in db.table.return_value.select.return_value.order.call_args_list]
        assert any("created_at" in call for call in order_calls)

    def test_c5_invalid_sort_by_returns_400(self) -> None:
        """C5: ?sort_by=invalid_field → 400 VALIDATION_ERROR."""
        db = _mock_db([])
        c = _make_app()
        resp = _get(c, db, "/bookings?sort_by=invalid_field")
        assert resp.status_code == 400

    def test_c6_default_sort_is_updated_at(self) -> None:
        """C6: No sort_by → defaults to updated_at ordering."""
        db = _mock_db([])
        c = _make_app()
        _get(c, db, "/bookings")
        order_calls = [str(call) for call in db.table.return_value.select.return_value.order.call_args_list]
        assert any("updated_at" in call for call in order_calls)


# ─────────────────────────────────────────────────────────────────────────────
# D — sort_dir validation and forwarding
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupD_SortDir:

    def test_d1_sort_dir_asc_forwarded(self) -> None:
        """D1: ?sort_dir=asc → .order(..., desc=False) called."""
        db = _mock_db([])
        c = _make_app()
        _get(c, db, "/bookings?sort_dir=asc")
        order_calls = [str(call) for call in db.table.return_value.select.return_value.order.call_args_list]
        # Should have desc=False somewhere
        assert any("False" in call for call in order_calls)

    def test_d2_sort_dir_desc_forwarded(self) -> None:
        """D2: ?sort_dir=desc → .order(..., desc=True) called."""
        db = _mock_db([])
        c = _make_app()
        _get(c, db, "/bookings?sort_dir=desc")
        order_calls = [str(call) for call in db.table.return_value.select.return_value.order.call_args_list]
        assert any("True" in call for call in order_calls)

    def test_d3_invalid_sort_dir_returns_400(self) -> None:
        """D3: ?sort_dir=sideways → 400 VALIDATION_ERROR."""
        db = _mock_db([])
        c = _make_app()
        resp = _get(c, db, "/bookings?sort_dir=sideways")
        assert resp.status_code == 400

    def test_d4_default_sort_dir_is_desc(self) -> None:
        """D4: No sort_dir → defaults to desc."""
        db = _mock_db([])
        c = _make_app()
        _get(c, db, "/bookings")
        order_calls = [str(call) for call in db.table.return_value.select.return_value.order.call_args_list]
        assert any("True" in call for call in order_calls)


# ─────────────────────────────────────────────────────────────────────────────
# E — combined filters
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupE_CombinedFilters:

    def test_e1_source_and_check_out_combined(self) -> None:
        """E1: source + check_out_from → both filters applied."""
        db = _mock_db([])
        c = _make_app()
        resp = _get(c, db, "/bookings?source=airbnb&check_out_from=2026-04-01")
        assert resp.status_code == 200
        eq_calls = [str(call) for call in db.table.return_value.select.return_value.eq.call_args_list]
        gte_calls = [str(call) for call in db.table.return_value.select.return_value.gte.call_args_list]
        assert any("airbnb" in c for c in eq_calls)
        assert any("check_out" in c for c in gte_calls)

    def test_e2_all_filters_combined_returns_200(self) -> None:
        """E2: All filters at once → 200 OK."""
        db = _mock_db([])
        c = _make_app()
        path = (
            "/bookings"
            "?source=bookingcom"
            "&property_id=prop_A"
            "&status=active"
            "&check_in_from=2026-04-01"
            "&check_in_to=2026-04-30"
            "&check_out_from=2026-04-05"
            "&check_out_to=2026-05-10"
            "&sort_by=check_in"
            "&sort_dir=asc"
            "&limit=10"
        )
        resp = _get(c, db, path)
        assert resp.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# F — response shape
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupF_ResponseShape:

    def test_f1_response_includes_sort_by(self) -> None:
        """F1: Response body includes sort_by field."""
        db = _mock_db([])
        c = _make_app()
        body = _get(c, db, "/bookings?sort_by=check_in").json()["data"]
        assert "sort_by" in body
        assert body["sort_by"] == "check_in"

    def test_f2_response_includes_sort_dir(self) -> None:
        """F2: Response body includes sort_dir field."""
        db = _mock_db([])
        c = _make_app()
        body = _get(c, db, "/bookings?sort_dir=asc").json()["data"]
        assert "sort_dir" in body
        assert body["sort_dir"] == "asc"

    def test_f3_default_sort_by_in_response(self) -> None:
        """F3: No sort_by → response.sort_by = 'updated_at'."""
        db = _mock_db([])
        c = _make_app()
        body = _get(c, db, "/bookings").json()["data"]
        assert body["sort_by"] == "updated_at"

    def test_f4_default_sort_dir_in_response(self) -> None:
        """F4: No sort_dir → response.sort_dir = 'desc'."""
        db = _mock_db([])
        c = _make_app()
        body = _get(c, db, "/bookings").json()["data"]
        assert body["sort_dir"] == "desc"

    def test_f5_existing_fields_still_present(self) -> None:
        """F5: Existing response fields (tenant_id, count, limit, bookings) still present."""
        db = _mock_db([])
        c = _make_app()
        body = _get(c, db, "/bookings").json()["data"]
        assert {"tenant_id", "count", "limit", "bookings"}.issubset(body.keys())


# ─────────────────────────────────────────────────────────────────────────────
# G — backward compatibility
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupG_BackwardCompatibility:

    def test_g1_no_params_still_works(self) -> None:
        """G1: GET /bookings with no params → 200 (backward compatible)."""
        db = _mock_db([])
        c = _make_app()
        resp = _get(c, db, "/bookings")
        assert resp.status_code == 200

    def test_g2_existing_status_filter_still_works(self) -> None:
        """G2: ?status=active → still works exactly as before."""
        db = _mock_db([_booking_row()])
        c = _make_app()
        resp = _get(c, db, "/bookings?status=active")
        assert resp.status_code == 200

    def test_g3_existing_check_in_filters_still_work(self) -> None:
        """G3: ?check_in_from=...&check_in_to=... → still works."""
        db = _mock_db([])
        c = _make_app()
        resp = _get(c, db, "/bookings?check_in_from=2026-04-01&check_in_to=2026-04-30")
        assert resp.status_code == 200

    def test_g4_invalid_status_still_returns_400(self) -> None:
        """G4: Invalid status → 400 (unchanged behavior)."""
        db = _mock_db([])
        c = _make_app()
        resp = _get(c, db, "/bookings?status=invalid")
        assert resp.status_code == 400

    def test_g5_never_writes_to_any_table(self) -> None:
        """G5: GET /bookings never writes to any table."""
        db = _mock_db([])
        c = _make_app()
        _get(c, db, "/bookings?source=airbnb&sort_by=check_in&sort_dir=asc")
        assert db.table.return_value.insert.call_count == 0
        assert db.table.return_value.update.call_count == 0
