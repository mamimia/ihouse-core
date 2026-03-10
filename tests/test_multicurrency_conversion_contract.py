"""
Phase 161 — Contract Tests: Multi-Currency Conversion Layer

Tests:
  A — _validate_base_currency: None passes
  B — _validate_base_currency: valid 3-letter code passes
  C — _validate_base_currency: invalid code → error response
  D — _fetch_rate: same currency returns 1
  E — _fetch_rate: valid pair returns Decimal rate
  F — _fetch_rate: missing pair returns None
  G — _fetch_rate: DB exception returns None (no raise)
  H — _apply_conversion: single bucket same currency
  I — _apply_conversion: converts with known rate
  J — _apply_conversion: missing rate → warning, excluded from total
  K — _apply_conversion: multiple buckets merged
  L — GET /financial/summary: no base_currency → multi-currency response
  M — GET /financial/summary: base_currency=USD → single USD key
  N — GET /financial/summary: base_currency=INVALID → 400
  O — GET /financial/summary: base_currency present → base_currency field in response
  P — GET /financial/summary: missing rate → conversion_warnings present
  Q — GET /financial/by-provider: base_currency converts per provider
  R — GET /financial/by-property: base_currency converts per property
  S — GET /financial/by-provider: invalid base_currency → 400
  T — GET /financial/by-property: invalid base_currency → 400
"""
from __future__ import annotations

import os
import sys
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.financial_aggregation_router import (
    router as fin_router,
    _validate_base_currency,
    _fetch_rate,
    _apply_conversion,
)
from api.auth import jwt_auth

_app = FastAPI()
_app.include_router(fin_router)
_app.dependency_overrides[jwt_auth] = lambda: "tenant-161"
_client = TestClient(_app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Mock DB factories
# ---------------------------------------------------------------------------

def _make_chain(data: list | None = None, side_effect=None) -> MagicMock:
    chain = MagicMock()
    if side_effect:
        chain.execute.side_effect = side_effect
    else:
        chain.execute.return_value = MagicMock(data=data if data is not None else [])
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.gte.return_value = chain
    chain.lt.return_value = chain
    chain.limit.return_value = chain
    chain.order.return_value = chain
    return chain


def _mock_db_with_rate(facts: list, rate_value: float | None = None) -> MagicMock:
    """DB mock: first execute = facts, second = exchange rate lookup."""
    rate_rows = [{"rate": str(rate_value)}] if rate_value is not None else []
    calls = [
        MagicMock(data=facts),
        MagicMock(data=rate_rows),
    ]

    def side_effect():
        return calls.pop(0) if calls else MagicMock(data=[])

    chain = MagicMock()
    chain.execute.side_effect = side_effect
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.gte.return_value = chain
    chain.lt.return_value = chain
    chain.limit.return_value = chain
    chain.order.return_value = chain
    db = MagicMock()
    db.table.return_value = chain
    return db


def _make_fact(
    booking_id: str = "bk-1",
    currency: str = "USD",
    total_price: str = "200.00",
    ota_commission: str = "20.00",
    net_to_property: str = "180.00",
    provider: str = "airbnb",
    property_id: str = "prop-1",
    recorded_at: str = "2026-01-15",
) -> dict:
    return {
        "booking_id": booking_id,
        "tenant_id": "tenant-161",
        "currency": currency,
        "total_price": total_price,
        "ota_commission": ota_commission,
        "net_to_property": net_to_property,
        "provider": provider,
        "property_id": property_id,
        "recorded_at": recorded_at,
    }


# ===========================================================================
# Group A — _validate_base_currency: None passes
# ===========================================================================

class TestGroupA_ValidateNone:

    def test_a1_none_returns_none(self):
        assert _validate_base_currency(None) is None

    def test_a2_empty_string_returns_400(self):
        result = _validate_base_currency("")
        assert result is not None


# ===========================================================================
# Group B — _validate_base_currency: valid 3-letter code passes
# ===========================================================================

class TestGroupB_ValidCode:

    def test_b1_usd_passes(self):
        assert _validate_base_currency("USD") is None

    def test_b2_thb_passes(self):
        assert _validate_base_currency("THB") is None

    def test_b3_eur_passes(self):
        assert _validate_base_currency("EUR") is None

    def test_b4_lowercase_passes(self):
        assert _validate_base_currency("usd") is None


# ===========================================================================
# Group C — _validate_base_currency: invalid code → error
# ===========================================================================

class TestGroupC_InvalidCode:

    def test_c1_two_letters_returns_error(self):
        result = _validate_base_currency("US")
        assert result is not None

    def test_c2_four_letters_returns_error(self):
        result = _validate_base_currency("USDD")
        assert result is not None

    def test_c3_digit_in_code_returns_error(self):
        result = _validate_base_currency("U5D")
        assert result is not None


# ===========================================================================
# Group D — _fetch_rate: same currency = 1
# ===========================================================================

class TestGroupD_SameCurrency:

    def test_d1_usd_to_usd(self):
        db = MagicMock()
        rate = _fetch_rate(db, "USD", "USD")
        assert rate == Decimal("1")

    def test_d2_thb_to_thb(self):
        db = MagicMock()
        rate = _fetch_rate(db, "THB", "THB")
        assert rate == Decimal("1")

    def test_d3_case_insensitive(self):
        db = MagicMock()
        rate = _fetch_rate(db, "usd", "USD")
        assert rate == Decimal("1")


# ===========================================================================
# Group E — _fetch_rate: valid pair returns Decimal
# ===========================================================================

class TestGroupE_ValidPair:

    def test_e1_returns_decimal(self):
        chain = _make_chain(data=[{"rate": "36.5"}])
        db = MagicMock()
        db.table.return_value = chain
        rate = _fetch_rate(db, "USD", "THB")
        assert rate == Decimal("36.5")

    def test_e2_rate_type_decimal(self):
        chain = _make_chain(data=[{"rate": "0.027"}])
        db = MagicMock()
        db.table.return_value = chain
        rate = _fetch_rate(db, "THB", "USD")
        assert isinstance(rate, Decimal)


# ===========================================================================
# Group F — _fetch_rate: missing pair → None
# ===========================================================================

class TestGroupF_MissingPair:

    def test_f1_no_rows_returns_none(self):
        chain = _make_chain(data=[])
        db = MagicMock()
        db.table.return_value = chain
        assert _fetch_rate(db, "USD", "XYZ") is None


# ===========================================================================
# Group G — _fetch_rate: DB exception → None
# ===========================================================================

class TestGroupG_DbException:

    def test_g1_exception_returns_none(self):
        chain = _make_chain(side_effect=Exception("DB error"))
        db = MagicMock()
        db.table.return_value = chain
        assert _fetch_rate(db, "USD", "THB") is None


# ===========================================================================
# Group H — _apply_conversion: same currency (identity)
# ===========================================================================

class TestGroupH_SameCurrency:

    def test_h1_usd_to_usd_no_change(self):
        db = MagicMock()  # won't be called for same-currency (fetch_rate returns 1)
        amounts = {"USD": {"gross": "200.00", "commission": "20.00", "net": "180.00", "booking_count": 1}}
        # Patch _fetch_rate to return 1 for same
        out, warns = _apply_conversion(amounts, "USD", db)
        assert "USD" in out
        assert warns == []

    def test_h2_no_warnings_for_same_currency(self):
        db = MagicMock()
        amounts = {"USD": {"gross": "100.00", "commission": "10.00", "net": "90.00", "booking_count": 1}}
        _, warns = _apply_conversion(amounts, "USD", db)
        assert warns == []


# ===========================================================================
# Group I — _apply_conversion: converts with known rate
# ===========================================================================

class TestGroupI_Conversion:

    def test_i1_gross_multiplied_by_rate(self):
        chain = _make_chain(data=[{"rate": "2.0"}])
        db = MagicMock()
        db.table.return_value = chain
        amounts = {"USD": {"gross": "100.00", "commission": "10.00", "net": "90.00", "booking_count": 1}}
        out, warns = _apply_conversion(amounts, "EUR", db)
        assert "EUR" in out
        assert out["EUR"]["gross"] == "200.00"
        assert warns == []


# ===========================================================================
# Group J — _apply_conversion: missing rate → warning, excluded
# ===========================================================================

class TestGroupJ_MissingRate:

    def test_j1_missing_rate_adds_warning(self):
        chain = _make_chain(data=[])  # no rate row
        db = MagicMock()
        db.table.return_value = chain
        amounts = {"XYZ": {"gross": "100.00", "commission": "10.00", "net": "90.00", "booking_count": 1}}
        out, warns = _apply_conversion(amounts, "USD", db)
        assert "XYZ" in warns

    def test_j2_missing_rate_booking_not_included(self):
        chain = _make_chain(data=[])
        db = MagicMock()
        db.table.return_value = chain
        amounts = {"XYZ": {"gross": "100.00", "commission": "10.00", "net": "90.00", "booking_count": 1}}
        out, _ = _apply_conversion(amounts, "USD", db)
        assert out["USD"]["booking_count"] == 0


# ===========================================================================
# Group K — _apply_conversion: multiple buckets merged
# ===========================================================================

class TestGroupK_MultipleBuckets:

    def test_k1_two_buckets_merged(self):
        # Mock db: first call returns EUR rate, second returns GBP rate
        eur_rate = MagicMock(data=[{"rate": "1.0"}])
        gbp_rate = MagicMock(data=[{"rate": "1.0"}])
        calls = [eur_rate, gbp_rate]
        chain = MagicMock()
        chain.execute.side_effect = lambda: calls.pop(0)
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.limit.return_value = chain
        db = MagicMock()
        db.table.return_value = chain
        amounts = {
            "EUR": {"gross": "100.00", "commission": "10.00", "net": "90.00", "booking_count": 1},
            "GBP": {"gross": "50.00",  "commission": "5.00",  "net": "45.00", "booking_count": 1},
        }
        out, warns = _apply_conversion(amounts, "USD", db)
        assert out["USD"]["booking_count"] == 2
        assert warns == []


# ===========================================================================
# Group L — GET /financial/summary: no base_currency → multi-currency response
# ===========================================================================

class TestGroupL_SummaryNoCurrency:

    def test_l1_no_base_currency_returns_currencies_dict(self, monkeypatch):
        db = _mock_db_with_rate([_make_fact(currency="USD")])
        monkeypatch.setattr("api.financial_aggregation_router._get_supabase_client", lambda: db)
        resp = _client.get("/financial/summary?period=2026-01")
        assert resp.status_code == 200
        assert "currencies" in resp.json()

    def test_l2_no_base_currency_field_in_response(self, monkeypatch):
        db = _mock_db_with_rate([_make_fact(currency="USD")])
        monkeypatch.setattr("api.financial_aggregation_router._get_supabase_client", lambda: db)
        data = _client.get("/financial/summary?period=2026-01").json()
        assert "base_currency" not in data


# ===========================================================================
# Group M — GET /financial/summary: base_currency=USD → single key
# ===========================================================================

class TestGroupM_SummaryWithCurrency:

    def test_m1_base_currency_returns_single_key(self, monkeypatch):
        db = _mock_db_with_rate([_make_fact(currency="USD")], rate_value=1.0)
        monkeypatch.setattr("api.financial_aggregation_router._get_supabase_client", lambda: db)
        data = _client.get("/financial/summary?period=2026-01&base_currency=USD").json()
        assert "USD" in data["currencies"]
        assert len(data["currencies"]) == 1

    def test_m2_single_currency_booking_count(self, monkeypatch):
        db = _mock_db_with_rate([_make_fact(currency="USD", booking_id="b1"),
                                  _make_fact(currency="USD", booking_id="b2")], rate_value=1.0)
        monkeypatch.setattr("api.financial_aggregation_router._get_supabase_client", lambda: db)
        data = _client.get("/financial/summary?period=2026-01&base_currency=USD").json()
        assert data["currencies"]["USD"]["booking_count"] == 2


# ===========================================================================
# Group N — GET /financial/summary: invalid base_currency → 400
# ===========================================================================

class TestGroupN_InvalidCurrency:

    def test_n1_two_letter_returns_400(self, monkeypatch):
        db = _mock_db_with_rate([])
        monkeypatch.setattr("api.financial_aggregation_router._get_supabase_client", lambda: db)
        resp = _client.get("/financial/summary?period=2026-01&base_currency=US")
        assert resp.status_code == 400

    def test_n2_numeric_code_returns_400(self, monkeypatch):
        db = _mock_db_with_rate([])
        monkeypatch.setattr("api.financial_aggregation_router._get_supabase_client", lambda: db)
        resp = _client.get("/financial/summary?period=2026-01&base_currency=123")
        assert resp.status_code == 400


# ===========================================================================
# Group O — base_currency field present in response
# ===========================================================================

class TestGroupO_BaseCurrencyField:

    def test_o1_base_currency_in_response(self, monkeypatch):
        db = _mock_db_with_rate([_make_fact(currency="USD")], rate_value=1.0)
        monkeypatch.setattr("api.financial_aggregation_router._get_supabase_client", lambda: db)
        data = _client.get("/financial/summary?period=2026-01&base_currency=USD").json()
        assert data.get("base_currency") == "USD"

    def test_o2_base_currency_uppercased(self, monkeypatch):
        db = _mock_db_with_rate([_make_fact(currency="USD")], rate_value=1.0)
        monkeypatch.setattr("api.financial_aggregation_router._get_supabase_client", lambda: db)
        data = _client.get("/financial/summary?period=2026-01&base_currency=usd").json()
        assert data.get("base_currency") == "USD"


# ===========================================================================
# Group P — missing rate → conversion_warnings in response
# ===========================================================================

class TestGroupP_ConversionWarnings:

    def test_p1_missing_rate_adds_warnings_field(self, monkeypatch):
        db = _mock_db_with_rate([_make_fact(currency="ZZZ")], rate_value=None)
        monkeypatch.setattr("api.financial_aggregation_router._get_supabase_client", lambda: db)
        data = _client.get("/financial/summary?period=2026-01&base_currency=USD").json()
        assert "conversion_warnings" in data

    def test_p2_no_warnings_field_when_all_rates_found(self, monkeypatch):
        db = _mock_db_with_rate([_make_fact(currency="USD")], rate_value=1.0)
        monkeypatch.setattr("api.financial_aggregation_router._get_supabase_client", lambda: db)
        data = _client.get("/financial/summary?period=2026-01&base_currency=USD").json()
        assert "conversion_warnings" not in data


# ===========================================================================
# Group Q — GET /financial/by-provider: base_currency converts per provider
# ===========================================================================

class TestGroupQ_ByProvider:

    def test_q1_by_provider_with_base_currency_200(self, monkeypatch):
        db = _mock_db_with_rate([_make_fact(currency="USD", provider="airbnb")], rate_value=1.0)
        monkeypatch.setattr("api.financial_aggregation_router._get_supabase_client", lambda: db)
        resp = _client.get("/financial/by-provider?period=2026-01&base_currency=USD")
        assert resp.status_code == 200

    def test_q2_by_provider_base_currency_field(self, monkeypatch):
        db = _mock_db_with_rate([_make_fact(currency="USD", provider="airbnb")], rate_value=1.0)
        monkeypatch.setattr("api.financial_aggregation_router._get_supabase_client", lambda: db)
        data = _client.get("/financial/by-provider?period=2026-01&base_currency=USD").json()
        assert data.get("base_currency") == "USD"


# ===========================================================================
# Group R — GET /financial/by-property: base_currency converts per property
# ===========================================================================

class TestGroupR_ByProperty:

    def test_r1_by_property_with_base_currency_200(self, monkeypatch):
        db = _mock_db_with_rate([_make_fact(currency="USD", property_id="p1")], rate_value=1.0)
        monkeypatch.setattr("api.financial_aggregation_router._get_supabase_client", lambda: db)
        resp = _client.get("/financial/by-property?period=2026-01&base_currency=USD")
        assert resp.status_code == 200

    def test_r2_by_property_base_currency_field(self, monkeypatch):
        db = _mock_db_with_rate([_make_fact(currency="USD", property_id="p1")], rate_value=1.0)
        monkeypatch.setattr("api.financial_aggregation_router._get_supabase_client", lambda: db)
        data = _client.get("/financial/by-property?period=2026-01&base_currency=USD").json()
        assert data.get("base_currency") == "USD"


# ===========================================================================
# Group S — GET /financial/by-provider: invalid base_currency → 400
# ===========================================================================

class TestGroupS_ByProviderInvalid:

    def test_s1_invalid_base_currency_400(self, monkeypatch):
        db = _mock_db_with_rate([])
        monkeypatch.setattr("api.financial_aggregation_router._get_supabase_client", lambda: db)
        resp = _client.get("/financial/by-provider?period=2026-01&base_currency=TOOLONG")
        assert resp.status_code == 400


# ===========================================================================
# Group T — GET /financial/by-property: invalid base_currency → 400
# ===========================================================================

class TestGroupT_ByPropertyInvalid:

    def test_t1_invalid_base_currency_400(self, monkeypatch):
        db = _mock_db_with_rate([])
        monkeypatch.setattr("api.financial_aggregation_router._get_supabase_client", lambda: db)
        resp = _client.get("/financial/by-property?period=2026-01&base_currency=12")
        assert resp.status_code == 400
