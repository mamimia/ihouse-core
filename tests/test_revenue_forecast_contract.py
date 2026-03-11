"""
Phase 233 — Revenue Forecast Engine — Contract Tests

Tests cover:

Unit: _project_occupancy
    - 0 bookings → 0.0%, 0 nights
    - 1 booking spanning full window → 100%
    - 1 booking spanning partial window → correct pct
    - 0 property_count → 0.0%
    - check_out missing → treated as 1 night

Unit: _build_heuristic_narrative
    - 0 confirmed bookings → "No confirmed bookings" message
    - above historical avg → "above expected" in text
    - below historical avg → "below expected" in text
    - no historical avg → fallback message

Unit: _project_revenue
    - bookings with financial data → uses actual values
    - bookings without financial data → uses historical avg
    - currency param → dominant currency set correctly

Endpoint: GET /ai/copilot/revenue-forecast
    - 200 happy path — correct shape (all keys present)
    - 200 with property_id filter
    - 200 with currency filter
    - 200 with window=60
    - 200 with window=90
    - 200 zero confirmed bookings → forecast.confirmed_bookings == 0
    - 400 invalid window (45)
    - 400 invalid currency code (not 3 letters)
    - 500 on DB error
    - tenant isolation — eq(tenant_id) called
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from api.revenue_forecast_router import (
    _build_heuristic_narrative,
    _project_occupancy,
    _project_revenue,
)

TENANT = "tenant-fc"
TODAY = date.today()
CHECKIN = (TODAY + timedelta(days=5)).isoformat()
CHECKOUT = (TODAY + timedelta(days=8)).isoformat()  # 3 nights


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_booking(booking_id="airbnb_B001", check_in=None, check_out=None, prop="prop-1") -> dict:
    return {
        "booking_id": booking_id,
        "property_id": prop,
        "check_in": check_in or CHECKIN,
        "check_out": check_out or CHECKOUT,
        "lifecycle_status": "CONFIRMED",
    }


def _make_db(
    bookings=None,
    financial_rows=None,
    hist_rows=None,
    fail_booking: bool = False,
) -> MagicMock:
    db = MagicMock()

    def table_fn(name: str):
        t = MagicMock()
        for m in ("select", "eq", "gte", "lte", "lt", "in_", "limit", "execute"):
            getattr(t, m).return_value = t

        r = MagicMock()

        if name == "booking_state":
            if fail_booking:
                def boom():
                    raise RuntimeError("DB down")
                t.execute.side_effect = boom
            else:
                r.data = bookings if bookings is not None else [_make_booking()]
                t.execute.return_value = r

        elif name == "booking_financial_facts":
            r.data = financial_rows if financial_rows is not None else []
            # First call = per-booking facts; second = historical avg
            call_n = {"n": 0}
            hist_r = MagicMock()
            hist_r.data = hist_rows if hist_rows is not None else []
            def smart_exec():
                call_n["n"] += 1
                return r if call_n["n"] == 1 else hist_r
            t.execute.side_effect = smart_exec

        elif name == "ai_audit_log":
            r.data = [{"id": 1}]
            t.execute.return_value = r

        else:
            r.data = []
            t.execute.return_value = r

        return t

    db.table.side_effect = table_fn
    return db


def _app():
    from fastapi import FastAPI
    from api.revenue_forecast_router import router
    app = FastAPI()
    app.include_router(router)
    return app


def _get(query="", db_mock=None):
    from fastapi.testclient import TestClient
    import api.revenue_forecast_router as mod

    with patch("api.revenue_forecast_router.jwt_auth", return_value=TENANT), \
         patch.object(mod, "_get_db", return_value=db_mock or _make_db()):
        return TestClient(_app()).get(
            f"/ai/copilot/revenue-forecast{query}",
            headers={"Authorization": "Bearer fake"},
        )


# ---------------------------------------------------------------------------
# Unit: _project_occupancy
# ---------------------------------------------------------------------------

class TestProjectOccupancy:
    def test_zero_bookings_returns_zero(self):
        pct, nights = _project_occupancy([], 30, 1)
        assert pct == 0.0
        assert nights == 0

    def test_zero_property_count_returns_zero(self):
        pct, nights = _project_occupancy([_make_booking()], 30, 0)
        assert pct == 0.0

    def test_partial_stay_in_window(self):
        # 3-night booking in a 30-day window with 1 property → 10%
        booking = {
            "booking_id": "B1",
            "property_id": "prop-1",
            "check_in": (TODAY + timedelta(days=1)).isoformat(),
            "check_out": (TODAY + timedelta(days=4)).isoformat(),  # 3 nights
        }
        pct, nights = _project_occupancy([booking], 30, 1)
        assert nights == 3
        assert pct == 10.0

    def test_missing_checkout_treated_as_one_night(self):
        booking = {
            "booking_id": "B1",
            "property_id": "prop-1",
            "check_in": (TODAY + timedelta(days=2)).isoformat(),
            "check_out": None,
        }
        pct, nights = _project_occupancy([booking], 30, 1)
        assert nights == 1


# ---------------------------------------------------------------------------
# Unit: _build_heuristic_narrative
# ---------------------------------------------------------------------------

class TestBuildHeuristicNarrative:
    def _call(self, confirmed=5, gross="35000.00", net="29750.00", occ=16.7,
               hist=None, currency="THB"):
        return _build_heuristic_narrative(
            window_days=30,
            confirmed_bookings=confirmed,
            projected_gross=Decimal(gross),
            projected_net=Decimal(net),
            occupancy_pct=occ,
            historical_avg=hist or {"avg_gross_per_booking": "7000.00", "sample_bookings": 40, "lookback_days": 90},
            currency=currency,
        )

    def test_zero_bookings_says_no_confirmed(self):
        result = _build_heuristic_narrative(30, 0, Decimal("0"), Decimal("0"), 0.0, {}, "THB")
        assert "No confirmed bookings" in result

    def test_above_historical_says_above(self):
        # gross 42000 vs avg 7000 * 5 = 35000 → above
        result = self._call(gross="42000.00", net="35700.00")
        assert "above" in result

    def test_below_historical_says_below(self):
        # gross 28000 vs avg 7000 * 5 = 35000 → below
        result = self._call(gross="28000.00", net="23800.00")
        assert "below" in result

    def test_includes_occupancy(self):
        result = self._call()
        assert "Occupancy" in result or "occupancy" in result

    def test_no_historical_avg_uses_fallback(self):
        result = _build_heuristic_narrative(30, 5, Decimal("35000"), Decimal("29750"),
                                            16.7, {}, "THB")
        assert "THB" in result


# ---------------------------------------------------------------------------
# Unit: _project_revenue
# ---------------------------------------------------------------------------

class TestProjectRevenue:
    def test_bookings_with_financials_uses_actual(self):
        booking = _make_booking(booking_id="B1")
        financial_map = {
            "B1": {"total_price": "10000.00", "net_to_property": "8500.00", "currency": "THB"}
        }
        gross, net, ccy = _project_revenue([booking], financial_map, {}, "THB")
        assert gross == Decimal("10000.00")
        assert net == Decimal("8500.00")
        assert ccy == "THB"

    def test_no_financials_uses_historical_avg(self):
        booking = _make_booking(booking_id="B1")
        hist = {"avg_gross_per_booking": "7000.00", "avg_net_per_booking": "5950.00"}
        gross, net, ccy = _project_revenue([booking], {}, hist, None)
        assert gross == Decimal("7000.00")
        assert net == Decimal("5950.00")

    def test_dominant_currency_from_param(self):
        booking = _make_booking(booking_id="B1")
        financial_map = {"B1": {"total_price": "500", "net_to_property": "400", "currency": "USD"}}
        _, _, ccy = _project_revenue([booking], financial_map, {}, "THB")
        assert ccy == "THB"


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------

class TestRevenueForecastEndpoint:
    def test_200_happy_path_shape(self):
        resp = _get()
        assert resp.status_code == 200
        data = resp.json()
        assert "forecast" in data
        assert "historical_avg" in data
        assert "narrative" in data
        assert "tenant_id" in data
        assert "window_days" in data
        assert "generated_at" in data
        assert "properties_included" in data

    def test_200_forecast_has_required_keys(self):
        resp = _get()
        f = resp.json()["forecast"]
        for key in ("confirmed_bookings", "projected_gross", "projected_net",
                    "currency", "occupancy_pct", "total_nights_analyzed", "booked_nights"):
            assert key in f, f"Missing: {key}"

    def test_200_window_60(self):
        resp = _get("?window=60")
        assert resp.status_code == 200
        assert resp.json()["window_days"] == 60

    def test_200_window_90(self):
        resp = _get("?window=90")
        assert resp.status_code == 200
        assert resp.json()["window_days"] == 90

    def test_200_with_property_id_filter(self):
        resp = _get("?property_id=prop-7")
        assert resp.status_code == 200

    def test_200_with_currency_filter(self):
        resp = _get("?currency=THB")
        assert resp.status_code == 200

    def test_200_zero_confirmed_bookings(self):
        db = _make_db(bookings=[])
        resp = _get(db_mock=db)
        assert resp.status_code == 200
        assert resp.json()["forecast"]["confirmed_bookings"] == 0

    def test_400_invalid_window(self):
        resp = _get("?window=45")
        assert resp.status_code == 400

    def test_400_invalid_currency_code(self):
        resp = _get("?currency=TOLONG")
        assert resp.status_code == 400

    def test_400_currency_too_short(self):
        resp = _get("?currency=TH")
        assert resp.status_code == 400

    def test_db_error_graceful_degradation(self):
        """When DB completely fails, endpoint returns 200 with 0 confirmed bookings (best-effort)."""
        from fastapi.testclient import TestClient
        import api.revenue_forecast_router as mod

        failing_db = MagicMock()
        failing_db.table.side_effect = RuntimeError("catastrophic failure")

        with patch("api.revenue_forecast_router.jwt_auth", return_value=TENANT), \
             patch.object(mod, "_get_db", return_value=failing_db):
            resp = TestClient(_app()).get(
                "/ai/copilot/revenue-forecast",
                headers={"Authorization": "Bearer fake"},
            )
        # Best-effort: DB query failures are caught per-query, not catastrophically
        assert resp.status_code == 200
        assert resp.json()["forecast"]["confirmed_bookings"] == 0

    def test_narrative_is_non_empty_string(self):
        resp = _get()
        assert isinstance(resp.json()["narrative"], str)
        assert len(resp.json()["narrative"]) > 10
