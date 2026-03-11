"""
Phase 251 — Dynamic Pricing Suggestion Engine
Contract test suite.

Groups:
    A — suggest_prices() pure engine — basic output
    B — suggest_prices() seasonality multiplier
    C — suggest_prices() occupancy multiplier
    D — suggest_prices() lead-time multiplier
    E — suggest_prices() edge cases
    F — summary_stats()
    G — GET /pricing/suggestion/{property_id} — router happy path
    H — GET router — validation errors
    I — GET router — no rate card (404)
    J — Route registration
"""
from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app
from services.pricing_engine import PriceSuggestion, suggest_prices, summary_stats

client = TestClient(app)

_BEARER = {"Authorization": "Bearer test-token"}
_PATCH_DB = "api.pricing_suggestion_router._get_supabase_client"


# ---------------------------------------------------------------------------
# Fake DB helper
# ---------------------------------------------------------------------------

def _make_db(cards=None):
    class _R:
        def __init__(self, d): self.data = d

    class _Q:
        def __init__(self, c): self._c = c
        def select(self, *a): return self
        def eq(self, *a): return self
        def execute(self): return _R(self._c)

    class _DB:
        def __init__(self, c): self._c = c
        def table(self, *a): return _Q(self._c)

    return _DB(cards or [])


def _card(base_rate=10000, currency="THB", room_type="standard"):
    return {"base_rate": base_rate, "currency": currency,
            "room_type": room_type, "season": "high"}


# ---------------------------------------------------------------------------
# Group A — suggest_prices basic
# ---------------------------------------------------------------------------

class TestGroupABasic:
    def test_a1_returns_list(self):
        assert isinstance(suggest_prices(10000), list)

    def test_a2_default_30_days(self):
        assert len(suggest_prices(10000)) == 30

    def test_a3_custom_days(self):
        assert len(suggest_prices(10000, days=7)) == 7

    def test_a4_is_price_suggestion(self):
        s = suggest_prices(10000)[0]
        assert isinstance(s, PriceSuggestion)

    def test_a5_currency_propagated(self):
        s = suggest_prices(10000, currency="USD")[0]
        assert s.currency == "USD"

    def test_a6_suggested_rate_rounded_100(self):
        for s in suggest_prices(8500, days=30):
            assert s.suggested_rate % 100 == 0

    def test_a7_base_rate_zero_returns_empty(self):
        assert suggest_prices(0) == []

    def test_a8_negative_base_rate_returns_empty(self):
        assert suggest_prices(-100) == []

    def test_a9_days_zero_returns_empty(self):
        assert suggest_prices(10000, days=0) == []

    def test_a10_max_days_capped_at_90(self):
        assert len(suggest_prices(10000, days=200)) == 90


# ---------------------------------------------------------------------------
# Group B — seasonality
# ---------------------------------------------------------------------------

class TestGroupBSeasonality:
    def test_b1_december_is_high_season(self):
        d = date(2026, 12, 15)
        s = suggest_prices(10000, from_date=d, days=1)[0]
        assert s.season == "high"
        assert s.seasonality_mult == pytest.approx(1.20)

    def test_b2_july_is_low_season(self):
        d = date(2026, 7, 10)
        s = suggest_prices(10000, from_date=d, days=1)[0]
        assert s.season == "low"
        assert s.seasonality_mult == pytest.approx(0.90)

    def test_b3_november_is_high(self):
        d = date(2026, 11, 1)
        s = suggest_prices(10000, from_date=d, days=1)[0]
        assert s.season == "high"

    def test_b4_april_is_low(self):
        d = date(2026, 4, 1)
        s = suggest_prices(10000, from_date=d, days=1)[0]
        assert s.season == "low"


# ---------------------------------------------------------------------------
# Group C — occupancy multiplier
# ---------------------------------------------------------------------------

class TestGroupCOccupancy:
    def test_c1_high_occupancy_80_plus(self):
        s = suggest_prices(10000, occupancy_pct=85, days=1)[0]
        assert s.occupancy_mult == pytest.approx(1.25)

    def test_c2_mid_occupancy_60_to_79(self):
        s = suggest_prices(10000, occupancy_pct=65, days=1)[0]
        assert s.occupancy_mult == pytest.approx(1.10)

    def test_c3_mid_occupancy_40_to_59(self):
        s = suggest_prices(10000, occupancy_pct=50, days=1)[0]
        assert s.occupancy_mult == pytest.approx(1.00)

    def test_c4_low_occupancy_below_40(self):
        s = suggest_prices(10000, occupancy_pct=30, days=1)[0]
        assert s.occupancy_mult == pytest.approx(0.90)

    def test_c5_no_occupancy_neutral(self):
        s = suggest_prices(10000, occupancy_pct=None, days=1)[0]
        assert s.occupancy_mult == pytest.approx(1.00)


# ---------------------------------------------------------------------------
# Group D — lead-time multiplier
# ---------------------------------------------------------------------------

class TestGroupDLeadTime:
    def test_d1_today_flash_deal(self):
        s = suggest_prices(10000, from_date=date.today(), days=1)[0]
        assert s.lead_time_mult == pytest.approx(0.85)

    def test_d2_advance_14_plus(self):
        from datetime import timedelta
        d = date.today() + timedelta(days=20)
        s = suggest_prices(10000, from_date=d, days=1)[0]
        assert s.lead_time_mult == pytest.approx(1.05)


# ---------------------------------------------------------------------------
# Group E — edge cases
# ---------------------------------------------------------------------------

class TestGroupEEdge:
    def test_e1_from_date_respected(self):
        d = date(2026, 6, 1)
        s = suggest_prices(10000, from_date=d, days=1)[0]
        assert s.date == "2026-06-01"

    def test_e2_day_of_week_present(self):
        s = suggest_prices(10000, days=1)[0]
        assert s.day_of_week in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


# ---------------------------------------------------------------------------
# Group F — summary_stats
# ---------------------------------------------------------------------------

class TestGroupFSummary:
    def test_f1_empty_returns_none(self):
        s = summary_stats([])
        assert s["min"] is None and s["max"] is None

    def test_f2_count_correct(self):
        suggestions = suggest_prices(10000, days=10)
        assert summary_stats(suggestions)["count"] == 10

    def test_f3_avg_present(self):
        suggestions = suggest_prices(10000, days=5)
        assert summary_stats(suggestions)["avg"] is not None


# ---------------------------------------------------------------------------
# Group G — Router happy path
# ---------------------------------------------------------------------------

class TestGroupGRouter:
    def _get(self, cards=None, **kw):
        db = _make_db(cards or [_card()])
        with patch(_PATCH_DB, return_value=db):
            url = "/pricing/suggestion/prop-1"
            if kw:
                url += "?" + "&".join(f"{k}={v}" for k, v in kw.items())
            return client.get(url, headers=_BEARER)

    def test_g1_returns_200(self):
        assert self._get().status_code == 200

    def test_g2_has_suggestions(self):
        b = self._get().json()
        assert "suggestions" in b and len(b["suggestions"]) == 30

    def test_g3_has_summary(self):
        b = self._get().json()
        assert "summary" in b and b["summary"]["count"] == 30

    def test_g4_property_id_echoed(self):
        assert self._get().json()["property_id"] == "prop-1"

    def test_g5_custom_days(self):
        b = self._get(days=7).json()
        assert len(b["suggestions"]) == 7

    def test_g6_currency_from_card(self):
        b = self._get(cards=[_card(currency="USD")]).json()
        assert b["currency"] == "USD"


# ---------------------------------------------------------------------------
# Group H — Router validation errors
# ---------------------------------------------------------------------------

class TestGroupHValidation:
    def test_h1_days_above_90(self):
        db = _make_db([_card()])
        with patch(_PATCH_DB, return_value=db):
            r = client.get("/pricing/suggestion/p1?days=100", headers=_BEARER)
        assert r.status_code == 400

    def test_h2_days_zero(self):
        db = _make_db([_card()])
        with patch(_PATCH_DB, return_value=db):
            r = client.get("/pricing/suggestion/p1?days=0", headers=_BEARER)
        assert r.status_code == 400

    def test_h3_occupancy_above_100(self):
        db = _make_db([_card()])
        with patch(_PATCH_DB, return_value=db):
            r = client.get("/pricing/suggestion/p1?occupancy_pct=110", headers=_BEARER)
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Group I — No rate card → 404
# ---------------------------------------------------------------------------

class TestGroupINoCard:
    def test_i1_no_card_404(self):
        with patch(_PATCH_DB, return_value=_make_db([])):
            r = client.get("/pricing/suggestion/unknown-prop", headers=_BEARER)
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Group J — Route registration
# ---------------------------------------------------------------------------

class TestGroupJRoutes:
    def test_j1_route_registered(self):
        routes = [r.path for r in app.routes]
        assert "/pricing/suggestion/{property_id}" in routes
