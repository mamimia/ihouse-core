"""
Phase 191 — Contract tests: GET /financial/multi-currency-overview

Groups:
  A — Single currency: shape, totals, avg_commission_rate
  B — Multiple currencies: sorted by gross_total DESC, independence
  C — Empty period: currencies=[], total_bookings=0
  D — Zero-gross booking: avg_commission_rate is None
  E — Invalid / missing period: 400
  F — Currency filter: only requested currency returned
  G — Invalid currency filter: 400
"""
from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    db = MagicMock()
    # Chain .table().select().eq().gte().lt().order().execute()
    db.table.return_value = db
    db.select.return_value = db
    db.eq.return_value = db
    db.gte.return_value = db
    db.lt.return_value = db
    db.order.return_value = db
    db.in_.return_value = db
    db.limit.return_value = db
    db.execute.return_value = MagicMock(data=[])
    return db


def _row(booking_id, currency, gross, commission, net, provider="airbnb",
         property_id="prop-1", recorded_at="2026-03-10T00:00:00Z"):
    return {
        "booking_id": booking_id,
        "currency": currency,
        "total_price": str(gross),
        "ota_commission": str(commission),
        "net_to_property": str(net),
        "provider": provider,
        "property_id": property_id,
        "recorded_at": recorded_at,
        "event_kind": "BOOKING_CREATED",
    }


# ---------------------------------------------------------------------------
# Group A — Single currency
# ---------------------------------------------------------------------------

class TestGroupA_SingleCurrency:

    def test_a1_200_response_shape(self, mock_db):
        """Single currency returns correct shape."""
        mock_db.execute.return_value = MagicMock(data=[
            _row("bk-1", "THB", "10000", "1500", "8500"),
            _row("bk-2", "THB", "20000", "3000", "17000"),
        ])
        from api.financial_aggregation_router import get_multi_currency_overview
        result = asyncio.run(
            get_multi_currency_overview(period="2026-03", tenant_id="t1", client=mock_db)
        )
        data = json.loads(result.body)
        assert result.status_code == 200
        assert data["tenant_id"] == "t1"
        assert data["period"] == "2026-03"
        assert data["total_bookings"] == 2
        assert len(data["currencies"]) == 1

    def test_a2_gross_total_correct(self, mock_db):
        """gross_total is summed correctly."""
        mock_db.execute.return_value = MagicMock(data=[
            _row("bk-1", "THB", "10000", "1500", "8500"),
            _row("bk-2", "THB", "20000", "3000", "17000"),
        ])
        from api.financial_aggregation_router import get_multi_currency_overview
        result = asyncio.run(
            get_multi_currency_overview(period="2026-03", tenant_id="t1", client=mock_db)
        )
        data = json.loads(result.body)
        assert data["currencies"][0]["gross_total"] == "30000.00"

    def test_a3_net_total_correct(self, mock_db):
        """net_total is summed correctly."""
        mock_db.execute.return_value = MagicMock(data=[
            _row("bk-1", "THB", "10000", "1500", "8500"),
            _row("bk-2", "THB", "20000", "3000", "17000"),
        ])
        from api.financial_aggregation_router import get_multi_currency_overview
        result = asyncio.run(
            get_multi_currency_overview(period="2026-03", tenant_id="t1", client=mock_db)
        )
        data = json.loads(result.body)
        assert data["currencies"][0]["net_total"] == "25500.00"

    def test_a4_avg_commission_rate_correct(self, mock_db):
        """avg_commission_rate = (commission / gross) * 100."""
        # commission = 4500, gross = 30000 → rate = 15.00
        mock_db.execute.return_value = MagicMock(data=[
            _row("bk-1", "THB", "10000", "1500", "8500"),
            _row("bk-2", "THB", "20000", "3000", "17000"),
        ])
        from api.financial_aggregation_router import get_multi_currency_overview
        result = asyncio.run(
            get_multi_currency_overview(period="2026-03", tenant_id="t1", client=mock_db)
        )
        data = json.loads(result.body)
        assert data["currencies"][0]["avg_commission_rate"] == "15.00"

    def test_a5_booking_count_correct(self, mock_db):
        """booking_count reflects number of deduplicated bookings per currency."""
        mock_db.execute.return_value = MagicMock(data=[
            _row("bk-1", "THB", "10000", "1500", "8500"),
            _row("bk-2", "THB", "20000", "3000", "17000"),
        ])
        from api.financial_aggregation_router import get_multi_currency_overview
        result = asyncio.run(
            get_multi_currency_overview(period="2026-03", tenant_id="t1", client=mock_db)
        )
        data = json.loads(result.body)
        assert data["currencies"][0]["booking_count"] == 2


# ---------------------------------------------------------------------------
# Group B — Multiple currencies
# ---------------------------------------------------------------------------

class TestGroupB_MultiCurrency:

    def _rows(self):
        return [
            _row("bk-1", "THB", "450000", "67500", "382500"),  # big
            _row("bk-2", "USD", "18200",  "2730",  "15470"),   # medium
            _row("bk-3", "JPY", "5000",   "750",   "4250"),    # small
        ]

    def test_b1_sorted_by_gross_desc(self, mock_db):
        """Currencies are sorted by gross_total descending."""
        mock_db.execute.return_value = MagicMock(data=self._rows())
        from api.financial_aggregation_router import get_multi_currency_overview
        result = asyncio.run(
            get_multi_currency_overview(period="2026-03", tenant_id="t1", client=mock_db)
        )
        data = json.loads(result.body)
        currencies = [r["currency"] for r in data["currencies"]]
        assert currencies[0] == "THB"   # largest
        assert currencies[-1] == "JPY"  # smallest

    def test_b2_currencies_are_independent(self, mock_db):
        """No cross-currency arithmetic: each currency has correct totals."""
        mock_db.execute.return_value = MagicMock(data=self._rows())
        from api.financial_aggregation_router import get_multi_currency_overview
        result = asyncio.run(
            get_multi_currency_overview(period="2026-03", tenant_id="t1", client=mock_db)
        )
        data = json.loads(result.body)
        by_ccy = {r["currency"]: r for r in data["currencies"]}
        assert by_ccy["THB"]["gross_total"] == "450000.00"
        assert by_ccy["USD"]["gross_total"] == "18200.00"
        assert by_ccy["JPY"]["gross_total"] == "5000.00"

    def test_b3_total_bookings_is_all_bookings(self, mock_db):
        """total_bookings covers all bookings across all currencies."""
        mock_db.execute.return_value = MagicMock(data=self._rows())
        from api.financial_aggregation_router import get_multi_currency_overview
        result = asyncio.run(
            get_multi_currency_overview(period="2026-03", tenant_id="t1", client=mock_db)
        )
        data = json.loads(result.body)
        assert data["total_bookings"] == 3


# ---------------------------------------------------------------------------
# Group C — Empty period
# ---------------------------------------------------------------------------

class TestGroupC_EmptyPeriod:

    def test_c1_empty_period_returns_empty_currencies(self, mock_db):
        """No rows → currencies=[], total_bookings=0."""
        mock_db.execute.return_value = MagicMock(data=[])
        from api.financial_aggregation_router import get_multi_currency_overview
        result = asyncio.run(
            get_multi_currency_overview(period="2026-03", tenant_id="t1", client=mock_db)
        )
        data = json.loads(result.body)
        assert data["currencies"] == []
        assert data["total_bookings"] == 0


# ---------------------------------------------------------------------------
# Group D — Zero-gross booking
# ---------------------------------------------------------------------------

class TestGroupD_ZeroGross:

    def test_d1_zero_gross_gives_null_commission_rate(self, mock_db):
        """avg_commission_rate is null when gross = 0 (no division by zero)."""
        mock_db.execute.return_value = MagicMock(data=[
            _row("bk-1", "THB", "0", "0", "0"),
        ])
        from api.financial_aggregation_router import get_multi_currency_overview
        result = asyncio.run(
            get_multi_currency_overview(period="2026-03", tenant_id="t1", client=mock_db)
        )
        data = json.loads(result.body)
        assert data["currencies"][0]["avg_commission_rate"] is None


# ---------------------------------------------------------------------------
# Group E — Period validation
# ---------------------------------------------------------------------------

class TestGroupE_PeriodValidation:

    def test_e1_missing_period_returns_400(self, mock_db):
        """Missing period → 400 INVALID_PERIOD."""
        from api.financial_aggregation_router import get_multi_currency_overview
        result = asyncio.run(
            get_multi_currency_overview(period=None, tenant_id="t1", client=mock_db)
        )
        assert result.status_code == 400

    def test_e2_bad_period_format_returns_400(self, mock_db):
        """period='not-a-month' → 400."""
        from api.financial_aggregation_router import get_multi_currency_overview
        result = asyncio.run(
            get_multi_currency_overview(period="not-a-month", tenant_id="t1", client=mock_db)
        )
        assert result.status_code == 400


# ---------------------------------------------------------------------------
# Group F — Currency filter
# ---------------------------------------------------------------------------

class TestGroupF_CurrencyFilter:

    def test_f1_currency_filter_thb_only(self, mock_db):
        """?currency=THB returns only THB rows."""
        mock_db.execute.return_value = MagicMock(data=[
            _row("bk-1", "THB", "450000", "67500", "382500"),
            _row("bk-2", "USD", "18200",  "2730",  "15470"),
        ])
        from api.financial_aggregation_router import get_multi_currency_overview
        result = asyncio.run(
            get_multi_currency_overview(
                period="2026-03", currency="THB", tenant_id="t1", client=mock_db
            )
        )
        data = json.loads(result.body)
        assert len(data["currencies"]) == 1
        assert data["currencies"][0]["currency"] == "THB"

    def test_f2_currency_filter_no_match_returns_empty(self, mock_db):
        """?currency=EUR with only THB data returns currencies=[]."""
        mock_db.execute.return_value = MagicMock(data=[
            _row("bk-1", "THB", "450000", "67500", "382500"),
        ])
        from api.financial_aggregation_router import get_multi_currency_overview
        result = asyncio.run(
            get_multi_currency_overview(
                period="2026-03", currency="EUR", tenant_id="t1", client=mock_db
            )
        )
        data = json.loads(result.body)
        assert data["currencies"] == []


# ---------------------------------------------------------------------------
# Group G — Invalid currency filter
# ---------------------------------------------------------------------------

class TestGroupG_InvalidCurrencyFilter:

    def test_g1_bad_currency_code_returns_400(self, mock_db):
        """?currency=INVALID → 400 VALIDATION_ERROR."""
        from api.financial_aggregation_router import get_multi_currency_overview
        result = asyncio.run(
            get_multi_currency_overview(
                period="2026-03", currency="INVALID", tenant_id="t1", client=mock_db
            )
        )
        assert result.status_code == 400
        data = json.loads(result.body)
        assert data["code"] == "VALIDATION_ERROR"
