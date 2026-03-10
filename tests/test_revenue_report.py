"""
Phase 215 — Automated Revenue Reports: Contract Tests

Tests for:
    revenue_report_router.py
        GET /revenue-report/{property_id}  — single-property monthly breakdown
        GET /revenue-report/portfolio       — cross-property portfolio summary
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import main

_TENANT = "tenant-revenue-test"


def _make_client() -> TestClient:
    return TestClient(main.app)


# ---------------------------------------------------------------------------
# Minimal DB mock for revenue tests
# ---------------------------------------------------------------------------

class _MockResult:
    def __init__(self, data=None):
        self.data = data or []


class _RevenueDB:
    """Mock DB. .table('booking_financial_facts') returns configurable rows."""
    def __init__(self, rows=None):
        self._rows = rows or []

    def table(self, name):
        return self

    def select(self, *a, **kw):
        return self

    def eq(self, *a, **kw):
        return self

    def gte(self, *a, **kw):
        return self

    def lt(self, *a, **kw):
        return self

    def order(self, *a, **kw):
        return self

    def execute(self):
        return _MockResult(self._rows)


def _row(booking_id: str, month: str, property_id: str = "prop-001",
         gross: str = "1000.00", net: str = "800.00",
         commission: str = "200.00", currency: str = "USD") -> dict:
    return {
        "booking_id":         booking_id,
        "property_id":        property_id,
        "tenant_id":          _TENANT,
        "provider":           "airbnb",
        "total_price":        gross,
        "ota_commission":     commission,
        "net_to_property":    net,
        "currency":           currency,
        "recorded_at":        f"{month}-15T10:00:00",
        "source_confidence":  "FULL",
        "event_kind":         "BOOKING_CREATED",
        "canonical_status":   "ACTIVE",
        "payout_status":      None,
    }


# ===========================================================================
# Month utility tests (pure)
# ===========================================================================

from api.revenue_report_router import (
    _months_between,
    _month_diff,
    _build_month_summary,
    _aggregate_months,
)


class TestMonthUtilities:

    def test_months_between_single(self):
        result = _months_between("2026-01", "2026-01")
        assert result == ["2026-01"]

    def test_months_between_range(self):
        result = _months_between("2026-01", "2026-03")
        assert result == ["2026-01", "2026-02", "2026-03"]

    def test_months_between_crosses_year(self):
        result = _months_between("2025-11", "2026-02")
        assert result == ["2025-11", "2025-12", "2026-01", "2026-02"]

    def test_month_diff_same(self):
        assert _month_diff("2026-01", "2026-01") == 1

    def test_month_diff_range(self):
        assert _month_diff("2026-01", "2026-12") == 12

    def test_month_diff_cross_year(self):
        assert _month_diff("2025-01", "2026-01") == 13


class TestBuildMonthSummary:

    def test_empty_rows(self):
        s = _build_month_summary([], "2026-01", Decimal("0"))
        assert s["booking_count"] == 0
        assert s["gross_total"] is None

    def test_single_row(self):
        rows = [_row("bk-1", "2026-01")]
        s = _build_month_summary(rows, "2026-01", Decimal("0"))
        assert s["booking_count"] == 1
        assert s["gross_total"] == "1000.00"
        assert s["net_to_property_total"] == "800.00"

    def test_management_fee_deducted(self):
        rows = [_row("bk-1", "2026-01")]
        s = _build_month_summary(rows, "2026-01", Decimal("10"))
        # net = 800, fee = 80, owner_net = 720
        assert s["management_fee_amount"] == "80.00"
        assert s["owner_net_total"] == "720.00"

    def test_mixed_currency_nullifies_totals(self):
        rows = [
            _row("bk-1", "2026-01", currency="USD"),
            _row("bk-2", "2026-01", currency="THB"),
        ]
        s = _build_month_summary(rows, "2026-01", Decimal("0"))
        assert s["currency"] == "MIXED"
        assert s["gross_total"] is None


class TestAggregateMonths:

    def test_aggregates_correctly(self):
        monthly = [
            {"month": "2026-01", "booking_count": 2, "currency": "USD",
             "gross_total": "1000.00", "ota_commission_total": "200.00",
             "net_to_property_total": "800.00", "management_fee_amount": None,
             "owner_net_total": "800.00", "ota_collecting_excluded": 0,
             "epistemic_tier": "A"},
            {"month": "2026-02", "booking_count": 1, "currency": "USD",
             "gross_total": "500.00", "ota_commission_total": "100.00",
             "net_to_property_total": "400.00", "management_fee_amount": None,
             "owner_net_total": "400.00", "ota_collecting_excluded": 0,
             "epistemic_tier": "B"},
        ]
        totals = _aggregate_months(monthly)
        assert totals["total_booking_count"] == 3
        assert totals["gross_total"] == "1500.00"
        assert totals["owner_net_total"] == "1200.00"
        assert totals["overall_epistemic_tier"] == "B"


# ===========================================================================
# GET /revenue-report/{property_id}
# ===========================================================================

class TestRevenueReportSingle:

    def test_happy_path(self):
        rows = [_row("bk-1", "2026-01"), _row("bk-2", "2026-02")]
        db = _RevenueDB(rows)
        with patch("api.revenue_report_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/revenue-report/prop-001",
                params={"from_month": "2026-01", "to_month": "2026-02"},
                headers={"Authorization": "Bearer mock"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["property_id"] == "prop-001"
        assert "monthly" in body
        assert "totals" in body
        assert len(body["monthly"]) == 2

    def test_missing_from_month_returns_400(self):
        with patch("api.revenue_report_router._get_supabase_client", return_value=_RevenueDB()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/revenue-report/prop-001",
                params={"to_month": "2026-02"},
                headers={"Authorization": "Bearer mock"},
            )
        assert resp.status_code == 400

    def test_to_month_before_from_month_returns_400(self):
        with patch("api.revenue_report_router._get_supabase_client", return_value=_RevenueDB()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/revenue-report/prop-001",
                params={"from_month": "2026-06", "to_month": "2026-01"},
                headers={"Authorization": "Bearer mock"},
            )
        assert resp.status_code == 400

    def test_range_exceeds_24_months_returns_400(self):
        with patch("api.revenue_report_router._get_supabase_client", return_value=_RevenueDB()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/revenue-report/prop-001",
                params={"from_month": "2023-01", "to_month": "2026-06"},
                headers={"Authorization": "Bearer mock"},
            )
        assert resp.status_code == 400

    def test_no_data_returns_404(self):
        db = _RevenueDB([])
        with patch("api.revenue_report_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/revenue-report/prop-empty",
                params={"from_month": "2026-01", "to_month": "2026-02"},
                headers={"Authorization": "Bearer mock"},
            )
        assert resp.status_code == 404

    def test_management_fee_applied(self):
        rows = [_row("bk-1", "2026-01")]
        db = _RevenueDB(rows)
        with patch("api.revenue_report_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/revenue-report/prop-001",
                params={"from_month": "2026-01", "to_month": "2026-01", "management_fee_pct": "10"},
                headers={"Authorization": "Bearer mock"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["management_fee_pct"] == "10.00"

    def test_invalid_mgmt_fee_returns_400(self):
        with patch("api.revenue_report_router._get_supabase_client", return_value=_RevenueDB()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/revenue-report/prop-001",
                params={"from_month": "2026-01", "to_month": "2026-01", "management_fee_pct": "200"},
                headers={"Authorization": "Bearer mock"},
            )
        assert resp.status_code == 400

    def test_response_has_generated_at(self):
        rows = [_row("bk-1", "2026-01")]
        db = _RevenueDB(rows)
        with patch("api.revenue_report_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/revenue-report/prop-001",
                params={"from_month": "2026-01", "to_month": "2026-01"},
                headers={"Authorization": "Bearer mock"},
            )
        assert "generated_at" in resp.json()


# ===========================================================================
# GET /revenue-report/portfolio
# ===========================================================================

class TestRevenueReportPortfolio:

    def test_happy_path_multiple_properties(self):
        rows = [
            _row("bk-1", "2026-01", property_id="prop-001"),
            _row("bk-2", "2026-01", property_id="prop-002"),
        ]
        db = _RevenueDB(rows)
        with patch("api.revenue_report_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/revenue-report/portfolio",
                params={"from_month": "2026-01", "to_month": "2026-01"},
                headers={"Authorization": "Bearer mock"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["property_count"] == 2
        assert "properties" in body

    def test_empty_returns_zero_properties(self):
        db = _RevenueDB([])
        with patch("api.revenue_report_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/revenue-report/portfolio",
                params={"from_month": "2026-01", "to_month": "2026-01"},
                headers={"Authorization": "Bearer mock"},
            )
        assert resp.status_code == 200
        assert resp.json()["property_count"] == 0

    def test_missing_from_month_returns_400(self):
        with patch("api.revenue_report_router._get_supabase_client", return_value=_RevenueDB()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/revenue-report/portfolio",
                params={"to_month": "2026-01"},
                headers={"Authorization": "Bearer mock"},
            )
        assert resp.status_code == 400

    def test_response_sorted_by_gross(self):
        rows = [
            _row("bk-1", "2026-01", property_id="prop-low",  gross="100.00", net="80.00", commission="20.00"),
            _row("bk-2", "2026-01", property_id="prop-high", gross="5000.00", net="4000.00", commission="1000.00"),
        ]
        db = _RevenueDB(rows)
        with patch("api.revenue_report_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/revenue-report/portfolio",
                params={"from_month": "2026-01", "to_month": "2026-01"},
                headers={"Authorization": "Bearer mock"},
            )
        props = resp.json()["properties"]
        # sorted descending by gross — prop-high should be first
        assert props[0]["property_id"] == "prop-high"

    def test_response_has_management_fee_pct(self):
        db = _RevenueDB([])
        with patch("api.revenue_report_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/revenue-report/portfolio",
                params={"from_month": "2026-01", "to_month": "2026-01"},
                headers={"Authorization": "Bearer mock"},
            )
        assert "management_fee_pct" in resp.json()
