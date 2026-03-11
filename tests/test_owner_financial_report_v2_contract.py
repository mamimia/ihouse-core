"""
Phase 252 — Owner Financial Report API v2
Contract test suite.

Groups:
    A — GET /owner/financial-report happy path — drill_down=property
    B — drill_down=ota
    C — drill_down=booking (raw paginated)
    D — summary fields
    E — validation errors
    F — pagination
    G — filters (property_id, ota)
    H — empty result
    I — Route registration
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

_BEARER = {"Authorization": "Bearer test-token"}
_URL = "/owner/financial-report"
_PATCH_DB = "api.owner_financial_report_v2_router._get_supabase_client"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row(**kw):
    base = {
        "property_id": "prop-1", "ota_name": "airbnb",
        "booking_ref": "AB123", "gross_revenue": 10000,
        "net_revenue": 8500, "commission": 1200, "tax_amount": 300,
        "management_fee": 850, "check_in": "2026-01-15",
    }
    return {**base, **kw}


def _make_db(rows):
    class _R:
        def __init__(self, d): self.data = d
    class _Q:
        def __init__(self, c): self._c = c
        def select(self, *a): return self
        def eq(self, *a): return self
        def gte(self, *a): return self
        def lte(self, *a): return self
        def execute(self): return _R(self._c)
    class _DB:
        def __init__(self, c): self._c = c
        def table(self, *a): return _Q(self._c)
    return _DB(rows)


def _get(rows=None, **params):
    db = _make_db(rows if rows is not None else [_row()])
    base_params = {"date_from": "2026-01-01", "date_to": "2026-03-31"}
    base_params.update(params)
    qs = "&".join(f"{k}={v}" for k, v in base_params.items())
    with patch(_PATCH_DB, return_value=db):
        return client.get(f"{_URL}?{qs}", headers=_BEARER)


# ---------------------------------------------------------------------------
# Group A — property drill-down happy path
# ---------------------------------------------------------------------------

class TestGroupAProperty:
    def test_a1_returns_200(self):
        assert _get().status_code == 200

    def test_a2_has_summary(self):
        b = _get().json()
        assert "summary" in b

    def test_a3_has_breakdown(self):
        b = _get().json()
        assert "breakdown" in b and isinstance(b["breakdown"], list)

    def test_a4_has_pagination(self):
        b = _get().json()
        assert "pagination" in b

    def test_a5_breakdown_key_is_property_id(self):
        b = _get().json()
        assert b["breakdown"][0]["key"] == "prop-1"

    def test_a6_gross_revenue_correct(self):
        b = _get().json()
        assert b["breakdown"][0]["gross_revenue"] == 10000.0


# ---------------------------------------------------------------------------
# Group B — ota drill-down
# ---------------------------------------------------------------------------

class TestGroupBOta:
    def test_b1_returns_200(self):
        assert _get(drill_down="ota").status_code == 200

    def test_b2_breakdown_key_is_ota(self):
        b = _get(drill_down="ota").json()
        assert b["breakdown"][0]["key"] == "airbnb"

    def test_b3_multiple_otas_aggregated(self):
        rows = [
            _row(ota_name="airbnb", gross_revenue=10000),
            _row(ota_name="booking", gross_revenue=5000),
            _row(ota_name="airbnb", gross_revenue=2000),
        ]
        b = _get(rows=rows, drill_down="ota").json()
        keys = [x["key"] for x in b["breakdown"]]
        assert set(keys) == {"airbnb", "booking"}
        airbnb = next(x for x in b["breakdown"] if x["key"] == "airbnb")
        assert airbnb["gross_revenue"] == 12000.0


# ---------------------------------------------------------------------------
# Group C — booking drill-down
# ---------------------------------------------------------------------------

class TestGroupCBooking:
    def test_c1_returns_200(self):
        assert _get(drill_down="booking").status_code == 200

    def test_c2_breakdown_has_booking_ref(self):
        b = _get(drill_down="booking").json()
        assert b["breakdown"][0]["key"] == "AB123"

    def test_c3_has_check_in(self):
        b = _get(drill_down="booking").json()
        assert "check_in" in b["breakdown"][0]

    def test_c4_booking_count_is_1_per_row(self):
        b = _get(drill_down="booking").json()
        assert b["breakdown"][0]["booking_count"] == 1


# ---------------------------------------------------------------------------
# Group D — summary
# ---------------------------------------------------------------------------

class TestGroupDSummary:
    def test_d1_total_gross_correct(self):
        b = _get().json()
        assert b["summary"]["total_gross"] == 10000.0

    def test_d2_booking_count_correct(self):
        b = _get().json()
        assert b["summary"]["booking_count"] == 1

    def test_d3_date_range_echoed(self):
        b = _get().json()
        assert b["summary"]["date_from"] == "2026-01-01"
        assert b["summary"]["date_to"] == "2026-03-31"

    def test_d4_management_fee_in_summary(self):
        b = _get().json()
        assert "management_fee_total" in b["summary"]


# ---------------------------------------------------------------------------
# Group E — validation errors
# ---------------------------------------------------------------------------

class TestGroupEValidation:
    def test_e1_missing_date_from_400(self):
        db = _make_db([])
        with patch(_PATCH_DB, return_value=db):
            r = client.get(f"{_URL}?date_to=2026-03-31", headers=_BEARER)
        assert r.status_code == 400

    def test_e2_missing_date_to_400(self):
        db = _make_db([])
        with patch(_PATCH_DB, return_value=db):
            r = client.get(f"{_URL}?date_from=2026-01-01", headers=_BEARER)
        assert r.status_code == 400

    def test_e3_date_from_after_date_to_400(self):
        db = _make_db([])
        with patch(_PATCH_DB, return_value=db):
            r = client.get(f"{_URL}?date_from=2026-12-01&date_to=2026-01-01", headers=_BEARER)
        assert r.status_code == 400

    def test_e4_invalid_drill_down_400(self):
        db = _make_db([])
        with patch(_PATCH_DB, return_value=db):
            r = client.get(f"{_URL}?date_from=2026-01-01&date_to=2026-03-31&drill_down=blah", headers=_BEARER)
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Group F — pagination
# ---------------------------------------------------------------------------

class TestGroupFPagination:
    def test_f1_has_more_false_single_item(self):
        b = _get().json()
        assert b["pagination"]["has_more"] is False

    def test_f2_total_count_correct(self):
        b = _get().json()
        assert b["pagination"]["total_count"] == 1

    def test_f3_page_size_capped_at_200(self):
        rows = [_row(booking_ref=f"B{i}") for i in range(10)]
        b = _get(rows=rows, page_size=500, drill_down="booking").json()
        assert b["pagination"]["page_size"] <= 200


# ---------------------------------------------------------------------------
# Group G — filters
# ---------------------------------------------------------------------------

class TestGroupGFilters:
    def test_g1_property_filter_propagated(self):
        # DB mock ignores filters but endpoint should add the filter
        b = _get(property_id="prop-1").json()
        assert b["filters"]["property_id"] == "prop-1"

    def test_g2_ota_filter_propagated(self):
        b = _get(ota="airbnb").json()
        assert b["filters"]["ota"] == "airbnb"

    def test_g3_csv_url_null(self):
        b = _get().json()
        assert b["exported_csv_url"] is None


# ---------------------------------------------------------------------------
# Group H — empty result
# ---------------------------------------------------------------------------

class TestGroupHEmpty:
    def test_h1_empty_rows_200(self):
        assert _get(rows=[]).status_code == 200

    def test_h2_empty_total_gross_zero(self):
        b = _get(rows=[]).json()
        assert b["summary"]["total_gross"] == 0.0

    def test_h3_empty_breakdown_list(self):
        b = _get(rows=[]).json()
        assert b["breakdown"] == []


# ---------------------------------------------------------------------------
# Group I — Route registration
# ---------------------------------------------------------------------------

class TestGroupIRoutes:
    def test_i1_route_registered(self):
        routes = [r.path for r in app.routes]
        assert "/owner/financial-report" in routes
