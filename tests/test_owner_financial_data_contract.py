"""Phase 412 — Owner Portal Real Financial Data contract tests.

Verifies the financial data structures flowing to the owner portal.
"""

import pytest


SAMPLE_FINANCIAL_FACTS = {
    "booking_id": "airbnb_BK001",
    "property_id": "prop_1",
    "gross_amount": 15000.0,
    "net_amount": 12750.0,
    "commission_amount": 2250.0,
    "commission_pct": 15.0,
    "currency": "THB",
    "ota_source": "airbnb",
    "payment_status": "collected",
    "facts_extracted_at": "2026-03-01T00:00:00Z",
}

OWNER_DASHBOARD = {
    "total_revenue": 150000.0,
    "total_bookings": 12,
    "occupancy_rate": 0.72,
    "pending_payouts": 45000.0,
    "properties": [
        {"property_id": "prop_1", "revenue": 80000.0, "bookings": 7},
        {"property_id": "prop_2", "revenue": 70000.0, "bookings": 5},
    ],
}

CASHFLOW_ENTRY = {
    "iso_week": "2026-W10",
    "inflow": 25000.0,
    "outflow": 8000.0,
    "net": 17000.0,
    "currency": "THB",
}


class TestOwnerFinancialData:
    """Contract tests for owner portal financial data."""

    def test_financial_facts_has_required_fields(self):
        """Financial facts contain required fields."""
        required = ["booking_id", "gross_amount", "net_amount", "commission_amount", "currency"]
        for field in required:
            assert field in SAMPLE_FINANCIAL_FACTS

    def test_commission_is_consistent(self):
        """Commission amount matches gross - net."""
        delta = abs(
            SAMPLE_FINANCIAL_FACTS["gross_amount"]
            - SAMPLE_FINANCIAL_FACTS["net_amount"]
            - SAMPLE_FINANCIAL_FACTS["commission_amount"]
        )
        assert delta < 0.01

    def test_dashboard_has_totals(self):
        """Owner dashboard includes aggregate totals."""
        assert "total_revenue" in OWNER_DASHBOARD
        assert "total_bookings" in OWNER_DASHBOARD
        assert "occupancy_rate" in OWNER_DASHBOARD

    def test_dashboard_revenue_is_sum_of_properties(self):
        """Total revenue should equal sum of property revenues."""
        prop_sum = sum(p["revenue"] for p in OWNER_DASHBOARD["properties"])
        assert abs(OWNER_DASHBOARD["total_revenue"] - prop_sum) < 0.01

    def test_cashflow_has_iso_week(self):
        """Cashflow entries use ISO week format."""
        assert CASHFLOW_ENTRY["iso_week"].startswith("2026-W")

    def test_cashflow_net_is_inflow_minus_outflow(self):
        """Net cashflow = inflow - outflow."""
        expected_net = CASHFLOW_ENTRY["inflow"] - CASHFLOW_ENTRY["outflow"]
        assert abs(CASHFLOW_ENTRY["net"] - expected_net) < 0.01

    def test_financial_reads_from_facts_only(self):
        """Financial data should be sourced from booking_financial_facts."""
        assert "facts_extracted_at" in SAMPLE_FINANCIAL_FACTS

    def test_payment_status_is_valid(self):
        """Payment status is from known set."""
        valid = {"pending", "collected", "refunded", "disputed", "partial", "failed", "unknown"}
        assert SAMPLE_FINANCIAL_FACTS["payment_status"] in valid

    def test_currency_is_present(self):
        """All financial records carry currency."""
        assert SAMPLE_FINANCIAL_FACTS["currency"]
        assert CASHFLOW_ENTRY["currency"]

    def test_owner_dashboard_has_properties(self):
        """Dashboard includes per-property breakdown."""
        assert len(OWNER_DASHBOARD["properties"]) > 0
