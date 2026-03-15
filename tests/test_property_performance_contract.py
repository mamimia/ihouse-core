"""
Phase 243 — Property Performance Analytics API
Contract test suite.

Groups:
    A — Response shape
    B — Empty tenant
    C — State-only (no financial facts): booking counts, top_provider
    D — Financial data: revenue per currency, avg_booking_value
    E — Portfolio totals
    F — Deduplication of financial facts
    G — Edge cases (pure helpers)
    H — Route registration
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

_BEARER = {"Authorization": "Bearer test-token"}
_URL = "/admin/properties/performance"
_PATCH_DB = "api.property_performance_router._get_supabase_client"


# ---------------------------------------------------------------------------
# Fake DB helpers
# ---------------------------------------------------------------------------

def _make_db(state_rows, financial_rows):
    class _R:
        def __init__(self, d): self.data = d
    class _Q:
        def __init__(self, t, sr, fr):
            self._t = t; self._sr = sr; self._fr = fr
        def select(self, *a): return self
        def eq(self, *a): return self
        def order(self, *a, **kw): return self
        def execute(self):
            if "booking_state" in self._t:
                return _R(self._sr)
            return _R(self._fr)
    class _DB:
        def __init__(self, sr, fr): self._sr = sr; self._fr = fr
        def table(self, name): return _Q(name, self._sr, self._fr)
    return _DB(state_rows, financial_rows)


def _empty_db():
    return _make_db([], [])


def _state_rows():
    return [
        {"booking_id": "b1", "property_id": "prop_a", "source": "airbnb", "status": "active"},
        {"booking_id": "b2", "property_id": "prop_a", "source": "airbnb", "status": "active"},
        {"booking_id": "b3", "property_id": "prop_a", "source": "bookingcom", "status": "canceled"},
        {"booking_id": "b4", "property_id": "prop_b", "source": "bookingcom", "status": "active"},
    ]


def _financial_rows():
    """Financial rows — b1 and b4 have data. Each unique booking_id once."""
    return [
        {
            "booking_id": "b1", "property_id": "prop_a",
            "currency": "THB", "total_price": "10000.00",
            "net_to_property": "8500.00", "recorded_at": "2025-02-01T00:00:00Z",
        },
        {
            "booking_id": "b4", "property_id": "prop_b",
            "currency": "THB", "total_price": "5000.00",
            "net_to_property": "4200.00", "recorded_at": "2025-02-01T00:00:00Z",
        },
    ]


def _dup_financial_rows():
    """b1 appears twice — should be deduplicated (first = latest after ordering)."""
    return [
        {
            "booking_id": "b1", "property_id": "prop_a",
            "currency": "THB", "total_price": "12000.00",
            "net_to_property": "10000.00", "recorded_at": "2025-03-01T00:00:00Z",
        },
        {
            "booking_id": "b1", "property_id": "prop_a",
            "currency": "THB", "total_price": "10000.00",
            "net_to_property": "8500.00", "recorded_at": "2025-02-01T00:00:00Z",
        },
    ]


# ---------------------------------------------------------------------------
# Group A — Response shape
# ---------------------------------------------------------------------------

class TestGroupAShape:
    def _body(self):
        with patch(_PATCH_DB, return_value=_empty_db()):
            return client.get(_URL, headers=_BEARER).json()

    def test_a1_returns_200(self):
        with patch(_PATCH_DB, return_value=_empty_db()):
            assert client.get(_URL, headers=_BEARER).status_code == 200

    def test_a2_required_keys(self):
        body = self._body()
        for k in ("tenant_id", "generated_at", "property_count", "portfolio_totals", "properties"):
            assert k in body

    def test_a3_tenant_echoed(self):
        import os; expected = os.environ.get("IHOUSE_TENANT_ID", "dev-tenant")
        assert self._body()["tenant_id"] == expected

    def test_a4_generated_at_iso(self):
        assert "T" in self._body()["generated_at"]

    def test_a5_properties_is_list(self):
        assert isinstance(self._body()["properties"], list)

    def test_a6_portfolio_totals_is_dict(self):
        assert isinstance(self._body()["portfolio_totals"], dict)


# ---------------------------------------------------------------------------
# Group B — Empty tenant
# ---------------------------------------------------------------------------

class TestGroupBEmpty:
    def _body(self):
        with patch(_PATCH_DB, return_value=_empty_db()):
            return client.get(_URL, headers=_BEARER).json()

    def test_b1_property_count_zero(self):
        assert self._body()["property_count"] == 0

    def test_b2_properties_empty(self):
        assert self._body()["properties"] == []

    def test_b3_portfolio_totals_zero(self):
        body = self._body()
        t = body["portfolio_totals"]
        assert t["total_active_bookings"] == 0
        assert t["total_canceled_bookings"] == 0


# ---------------------------------------------------------------------------
# Group C — State data: counts, cancellation_rate, top_provider
# ---------------------------------------------------------------------------

class TestGroupCStateCounts:
    def _body(self):
        with patch(_PATCH_DB, return_value=_make_db(_state_rows(), [])):
            return client.get(_URL, headers=_BEARER).json()

    def test_c1_two_properties(self):
        assert self._body()["property_count"] == 2

    def test_c2_prop_a_active_2(self):
        props = {p["property_id"]: p for p in self._body()["properties"]}
        assert props["prop_a"]["active_bookings"] == 2

    def test_c3_prop_a_canceled_1(self):
        props = {p["property_id"]: p for p in self._body()["properties"]}
        assert props["prop_a"]["canceled_bookings"] == 1

    def test_c4_prop_a_top_provider_airbnb(self):
        props = {p["property_id"]: p for p in self._body()["properties"]}
        assert props["prop_a"]["top_provider"] == "airbnb"

    def test_c5_cancellation_rate_pct(self):
        props = {p["property_id"]: p for p in self._body()["properties"]}
        # 1 canceled / 3 total = 33.3%
        assert props["prop_a"]["cancellation_rate_pct"] == pytest.approx(33.3, abs=0.1)

    def test_c6_prop_b_active_1_canceled_0(self):
        props = {p["property_id"]: p for p in self._body()["properties"]}
        assert props["prop_b"]["active_bookings"] == 1
        assert props["prop_b"]["canceled_bookings"] == 0

    def test_c7_property_record_has_required_keys(self):
        p = self._body()["properties"][0]
        for k in ("property_id", "active_bookings", "canceled_bookings",
                   "total_gross_revenue", "total_net_revenue", "avg_booking_value",
                   "cancellation_rate_pct", "top_provider"):
            assert k in p

    def test_c8_sorted_by_active_bookings_desc(self):
        actives = [p["active_bookings"] for p in self._body()["properties"]]
        assert actives == sorted(actives, reverse=True)


# ---------------------------------------------------------------------------
# Group D — Financial revenue per currency
# ---------------------------------------------------------------------------

class TestGroupDRevenue:
    def _body(self):
        with patch(_PATCH_DB, return_value=_make_db(_state_rows(), _financial_rows())):
            return client.get(_URL, headers=_BEARER).json()

    def test_d1_prop_a_gross_revenue_thb(self):
        props = {p["property_id"]: p for p in self._body()["properties"]}
        assert "THB" in props["prop_a"]["total_gross_revenue"]

    def test_d2_prop_a_gross_10000(self):
        props = {p["property_id"]: p for p in self._body()["properties"]}
        assert props["prop_a"]["total_gross_revenue"]["THB"] == "10000.00"

    def test_d3_prop_a_net_8500(self):
        props = {p["property_id"]: p for p in self._body()["properties"]}
        assert props["prop_a"]["total_net_revenue"]["THB"] == "8500.00"

    def test_d4_avg_booking_value_present(self):
        props = {p["property_id"]: p for p in self._body()["properties"]}
        # prop_a has 2 active, gross=10000, avg=5000
        assert props["prop_a"]["avg_booking_value"]["THB"] == "5000.00"

    def test_d5_prop_b_net_4200(self):
        props = {p["property_id"]: p for p in self._body()["properties"]}
        assert props["prop_b"]["total_net_revenue"]["THB"] == "4200.00"


# ---------------------------------------------------------------------------
# Group E — Portfolio totals
# ---------------------------------------------------------------------------

class TestGroupEPortfolioTotals:
    def _body(self):
        with patch(_PATCH_DB, return_value=_make_db(_state_rows(), _financial_rows())):
            return client.get(_URL, headers=_BEARER).json()

    def test_e1_total_active_3(self):
        assert self._body()["portfolio_totals"]["total_active_bookings"] == 3

    def test_e2_total_canceled_1(self):
        assert self._body()["portfolio_totals"]["total_canceled_bookings"] == 1

    def test_e3_portfolio_gross_revenue(self):
        t = self._body()["portfolio_totals"]
        assert "THB" in t["gross_revenue_by_currency"]
        # prop_a 10000 + prop_b 5000 = 15000
        assert t["gross_revenue_by_currency"]["THB"] == "15000.00"

    def test_e4_currencies_list(self):
        t = self._body()["portfolio_totals"]
        assert "currencies" in t
        assert "THB" in t["currencies"]


# ---------------------------------------------------------------------------
# Group F — Deduplication
# ---------------------------------------------------------------------------

class TestGroupFDedup:
    def test_f1_dedup_keeps_first_only(self):
        from api.property_performance_router import _dedup_latest_financial
        rows = _dup_financial_rows()
        result = _dedup_latest_financial(rows)
        assert len(result) == 1
        # First row is the most recent (order assumed to come from DB)
        assert result[0]["total_price"] == "12000.00"

    def test_f2_dedup_doesnt_lose_unique_bookings(self):
        from api.property_performance_router import _dedup_latest_financial
        rows = _financial_rows()
        result = _dedup_latest_financial(rows)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Group G — Pure helper edge cases
# ---------------------------------------------------------------------------

class TestGroupGHelpers:
    def test_g1_to_decimal_handles_none(self):
        from api.property_performance_router import _to_decimal
        assert _to_decimal(None) == Decimal("0")

    def test_g2_to_decimal_handles_string(self):
        from api.property_performance_router import _to_decimal
        assert _to_decimal("12345.67") == Decimal("12345.67")

    def test_g3_fmt_two_decimal_places(self):
        from api.property_performance_router import _fmt
        assert _fmt(Decimal("1000")) == "1000.00"

    def test_g4_cancellation_rate_none_when_no_bookings(self):
        from api.property_performance_router import _build_property_record
        rec = _build_property_record("empty_prop", [], [])
        assert rec["cancellation_rate_pct"] is None

    def test_g5_top_provider_none_when_no_state(self):
        from api.property_performance_router import _build_property_record
        rec = _build_property_record("p1", [], [])
        assert rec["top_provider"] is None


# ---------------------------------------------------------------------------
# Group H — Route registration
# ---------------------------------------------------------------------------

class TestGroupHRoute:
    def test_h1_route_registered(self):
        routes = [r.path for r in app.routes]
        assert _URL in routes

    def test_h2_returns_200_with_bearer(self):
        with patch(_PATCH_DB, return_value=_empty_db()):
            assert client.get(_URL, headers=_BEARER).status_code == 200
