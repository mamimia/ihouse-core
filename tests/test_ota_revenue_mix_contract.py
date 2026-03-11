"""
Phase 244 — OTA Revenue Mix Analytics API
Contract test suite.

Groups:
    A — Response shape
    B — Empty tenant
    C — Single OTA single currency
    D — Multi-OTA revenue share
    E — Commission / net-to-gross ratios
    F — Multi-currency: no cross-currency mixing
    G — Deduplication
    H — Pure helpers
    I — Route registration
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

_BEARER = {"Authorization": "Bearer test-token"}
_URL = "/admin/ota/revenue-mix"
_PATCH_DB = "api.ota_revenue_mix_router._get_supabase_client"


# ---------------------------------------------------------------------------
# Fake DB helpers
# ---------------------------------------------------------------------------

def _make_db(rows):
    class _R:
        def __init__(self, d): self.data = d
    class _Q:
        def __init__(self, r): self._r = r
        def select(self, *a): return self
        def eq(self, *a): return self
        def order(self, *a, **kw): return self
        def execute(self): return _R(self._r)
    class _DB:
        def __init__(self, r): self._r = r
        def table(self, *a): return _Q(self._r)
    return _DB(rows)


def _row(booking_id, provider, currency, gross, commission, net, recorded_at="2025-01-01T00:00:00Z"):
    return {
        "booking_id": booking_id,
        "provider": provider,
        "currency": currency,
        "total_price": str(gross),
        "ota_commission": str(commission),
        "net_to_property": str(net),
        "recorded_at": recorded_at,
    }


def _airbnb_rows():
    return [
        _row("b1", "airbnb", "THB", 10000, 1500, 8500),
        _row("b2", "airbnb", "THB", 8000, 1200, 6800),
    ]


def _multi_ota_rows():
    return [
        _row("b1", "airbnb", "THB", 10000, 1500, 8500),
        _row("b2", "bookingcom", "THB", 5000, 1000, 4000),
    ]


def _multi_currency_rows():
    return [
        _row("b1", "airbnb", "THB", 10000, 1500, 8500),
        _row("b2", "airbnb", "USD", 500, 75, 425),
    ]


def _dup_rows():
    """b1 appears twice — same booking_id different recorded_at."""
    return [
        _row("b1", "airbnb", "THB", 10000, 1500, 8500, "2025-02-01T00:00:00Z"),
        _row("b1", "airbnb", "THB", 9000, 1350, 7650, "2025-01-01T00:00:00Z"),
    ]


# ---------------------------------------------------------------------------
# Group A — Response shape
# ---------------------------------------------------------------------------

class TestGroupAShape:
    def _body(self):
        with patch(_PATCH_DB, return_value=_make_db([])):
            return client.get(_URL, headers=_BEARER).json()

    def test_a1_returns_200(self):
        with patch(_PATCH_DB, return_value=_make_db([])):
            assert client.get(_URL, headers=_BEARER).status_code == 200

    def test_a2_required_keys(self):
        body = self._body()
        for k in ("tenant_id", "generated_at", "total_bookings",
                   "provider_count", "portfolio_totals", "providers"):
            assert k in body

    def test_a3_tenant_echoed(self):
        assert self._body()["tenant_id"] == "dev-tenant"

    def test_a4_generated_at_iso(self):
        assert "T" in self._body()["generated_at"]

    def test_a5_providers_is_dict(self):
        assert isinstance(self._body()["providers"], dict)

    def test_a6_portfolio_totals_has_currency_dicts(self):
        t = self._body()["portfolio_totals"]
        assert "gross_by_currency" in t
        assert "net_by_currency" in t


# ---------------------------------------------------------------------------
# Group B — Empty tenant
# ---------------------------------------------------------------------------

class TestGroupBEmpty:
    def _body(self):
        with patch(_PATCH_DB, return_value=_make_db([])):
            return client.get(_URL, headers=_BEARER).json()

    def test_b1_total_bookings_zero(self):
        assert self._body()["total_bookings"] == 0

    def test_b2_provider_count_zero(self):
        assert self._body()["provider_count"] == 0

    def test_b3_providers_empty(self):
        assert self._body()["providers"] == {}

    def test_b4_portfolio_totals_empty(self):
        t = self._body()["portfolio_totals"]
        assert t["gross_by_currency"] == {}
        assert t["net_by_currency"] == {}


# ---------------------------------------------------------------------------
# Group C — Single OTA, single currency
# ---------------------------------------------------------------------------

class TestGroupCSingleOTA:
    def _body(self):
        with patch(_PATCH_DB, return_value=_make_db(_airbnb_rows())):
            return client.get(_URL, headers=_BEARER).json()

    def test_c1_one_provider(self):
        assert self._body()["provider_count"] == 1

    def test_c2_two_bookings(self):
        assert self._body()["total_bookings"] == 2

    def test_c3_airbnb_in_providers(self):
        assert "airbnb" in self._body()["providers"]

    def test_c4_thb_gross_total(self):
        p = self._body()["providers"]["airbnb"]["THB"]
        assert p["gross_total"] == "18000.00"

    def test_c5_thb_net_total(self):
        p = self._body()["providers"]["airbnb"]["THB"]
        assert p["net_total"] == "15300.00"

    def test_c6_booking_count_2(self):
        p = self._body()["providers"]["airbnb"]["THB"]
        assert p["booking_count"] == 2

    def test_c7_revenue_share_100pct_sole_provider(self):
        p = self._body()["providers"]["airbnb"]["THB"]
        assert p["revenue_share_pct"] == "100.00"

    def test_c8_provider_entry_has_all_keys(self):
        p = self._body()["providers"]["airbnb"]["THB"]
        for k in ("booking_count", "gross_total", "commission_total", "net_total",
                   "avg_commission_rate", "net_to_gross_ratio", "revenue_share_pct"):
            assert k in p


# ---------------------------------------------------------------------------
# Group D — Multi-OTA revenue share
# ---------------------------------------------------------------------------

class TestGroupDMultiOTA:
    def _body(self):
        with patch(_PATCH_DB, return_value=_make_db(_multi_ota_rows())):
            return client.get(_URL, headers=_BEARER).json()

    def test_d1_two_providers(self):
        assert self._body()["provider_count"] == 2

    def test_d2_total_bookings_2(self):
        assert self._body()["total_bookings"] == 2

    def test_d3_airbnb_share_2thirds(self):
        # airbnb gross=10000, total=15000 → 66.67%
        p = self._body()["providers"]["airbnb"]["THB"]
        assert float(p["revenue_share_pct"]) == pytest.approx(66.67, abs=0.01)

    def test_d4_bookingcom_share_1third(self):
        p = self._body()["providers"]["bookingcom"]["THB"]
        assert float(p["revenue_share_pct"]) == pytest.approx(33.33, abs=0.01)

    def test_d5_portfolio_gross_15000(self):
        t = self._body()["portfolio_totals"]
        assert t["gross_by_currency"]["THB"] == "15000.00"


# ---------------------------------------------------------------------------
# Group E — Commission and net-to-gross ratios
# ---------------------------------------------------------------------------

class TestGroupERatios:
    def _body(self):
        with patch(_PATCH_DB, return_value=_make_db(_airbnb_rows())):
            return client.get(_URL, headers=_BEARER).json()

    def test_e1_avg_commission_rate_present(self):
        p = self._body()["providers"]["airbnb"]["THB"]
        assert p["avg_commission_rate"] is not None

    def test_e2_avg_commission_rate_value(self):
        # b1: 1500/10000=15%, b2: 1200/8000=15% → avg=15%
        p = self._body()["providers"]["airbnb"]["THB"]
        assert float(p["avg_commission_rate"]) == pytest.approx(15.0, abs=0.01)

    def test_e3_net_to_gross_ratio_present(self):
        p = self._body()["providers"]["airbnb"]["THB"]
        assert p["net_to_gross_ratio"] is not None

    def test_e4_net_to_gross_value(self):
        # b1: 8500/10000=85%, b2: 6800/8000=85% → avg=85%
        p = self._body()["providers"]["airbnb"]["THB"]
        assert float(p["net_to_gross_ratio"]) == pytest.approx(85.0, abs=0.01)


# ---------------------------------------------------------------------------
# Group F — Multi-currency
# ---------------------------------------------------------------------------

class TestGroupFMultiCurrency:
    def _body(self):
        with patch(_PATCH_DB, return_value=_make_db(_multi_currency_rows())):
            return client.get(_URL, headers=_BEARER).json()

    def test_f1_two_currencies_for_airbnb(self):
        p = self._body()["providers"]["airbnb"]
        assert "THB" in p and "USD" in p

    def test_f2_thb_and_usd_independent(self):
        p = self._body()["providers"]["airbnb"]
        assert p["THB"]["gross_total"] == "10000.00"
        assert p["USD"]["gross_total"] == "500.00"

    def test_f3_portfolio_totals_has_both_currencies(self):
        t = self._body()["portfolio_totals"]
        assert "THB" in t["gross_by_currency"]
        assert "USD" in t["gross_by_currency"]


# ---------------------------------------------------------------------------
# Group G — Deduplication
# ---------------------------------------------------------------------------

class TestGroupGDedup:
    def test_g1_keeps_first_occurrence_only(self):
        from api.ota_revenue_mix_router import _dedup_latest
        rows = _dup_rows()
        result = _dedup_latest(rows)
        assert len(result) == 1
        assert result[0]["total_price"] == "10000"

    def test_g2_does_not_lose_unique_bookings(self):
        from api.ota_revenue_mix_router import _dedup_latest
        result = _dedup_latest(_airbnb_rows())
        assert len(result) == 2

    def test_g3_dedup_in_endpoint(self):
        # b1 duplicated — should count as 1 booking
        with patch(_PATCH_DB, return_value=_make_db(_dup_rows())):
            body = client.get(_URL, headers=_BEARER).json()
        assert body["total_bookings"] == 1
        p = body["providers"]["airbnb"]["THB"]
        assert p["booking_count"] == 1
        assert p["gross_total"] == "10000.00"


# ---------------------------------------------------------------------------
# Group H — Pure helpers
# ---------------------------------------------------------------------------

class TestGroupHHelpers:
    def test_h1_safe_pct_zero_denominator(self):
        from api.ota_revenue_mix_router import _safe_pct
        assert _safe_pct(Decimal("5"), Decimal("0")) is None

    def test_h2_safe_pct_calculation(self):
        from api.ota_revenue_mix_router import _safe_pct
        assert _safe_pct(Decimal("1"), Decimal("4")) == "25.00"

    def test_h3_avg_pct_empty_list(self):
        from api.ota_revenue_mix_router import _avg_pct
        assert _avg_pct([]) is None

    def test_h4_avg_pct_single(self):
        from api.ota_revenue_mix_router import _avg_pct
        assert _avg_pct([Decimal("0.15")]) == "15.00"

    def test_h5_canonical_currency_uppercases(self):
        from api.ota_revenue_mix_router import _canonical_currency
        assert _canonical_currency("thb") == "THB"

    def test_h6_canonical_currency_none(self):
        from api.ota_revenue_mix_router import _canonical_currency
        assert _canonical_currency(None) == "UNKNOWN"


# ---------------------------------------------------------------------------
# Group I — Route registration
# ---------------------------------------------------------------------------

class TestGroupIRoute:
    def test_i1_route_registered(self):
        routes = [r.path for r in app.routes]
        assert _URL in routes

    def test_i2_returns_200_with_bearer(self):
        with patch(_PATCH_DB, return_value=_make_db([])):
            assert client.get(_URL, headers=_BEARER).status_code == 200
