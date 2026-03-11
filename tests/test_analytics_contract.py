"""
Phase 264 — Advanced Analytics Contract Tests
=============================================

Tests: 21 across 5 groups.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from main import app
from services import analytics as svc

client = TestClient(app, raise_server_exceptions=False)
_AUTH = {"Authorization": "Bearer test-token"}

# Shared stub dataset
_BOOKINGS = [
    {"property_id": "p1", "property_name": "Alpha Villa", "provider": "airbnb",     "gross_amount": 1000, "status": "confirmed", "check_in_date": "2026-01-15"},
    {"property_id": "p1", "property_name": "Alpha Villa", "provider": "airbnb",     "gross_amount": 800,  "status": "confirmed", "check_in_date": "2026-02-10"},
    {"property_id": "p2", "property_name": "Beta House",  "provider": "booking_com","gross_amount": 600,  "status": "confirmed", "check_in_date": "2026-02-20"},
    {"property_id": "p2", "property_name": "Beta House",  "provider": "agoda",      "gross_amount": 400,  "status": "confirmed", "check_in_date": "2026-03-01"},
    {"property_id": "p3", "property_name": "Gamma Hut",   "provider": "expedia",    "gross_amount": 200,  "status": "cancelled", "check_in_date": "2026-03-05"},
]


# ---------------------------------------------------------------------------
# Group A — Service: top_properties
# ---------------------------------------------------------------------------

class TestGroupATopProperties:

    def test_a1_returns_list(self):
        result = svc.top_properties(_BOOKINGS)
        assert isinstance(result, list)

    def test_a2_sorted_by_revenue_descending(self):
        result = svc.top_properties(_BOOKINGS, sort_by="revenue")
        revenues = [r["total_revenue"] for r in result]
        assert revenues == sorted(revenues, reverse=True)

    def test_a3_sorted_by_bookings_descending(self):
        result = svc.top_properties(_BOOKINGS, sort_by="bookings")
        counts = [r["confirmed_bookings"] for r in result]
        assert counts == sorted(counts, reverse=True)

    def test_a4_limit_respected(self):
        result = svc.top_properties(_BOOKINGS, limit=1)
        assert len(result) == 1

    def test_a5_cancelled_not_in_revenue(self):
        result = svc.top_properties(_BOOKINGS)
        p3 = next((r for r in result if r["property_id"] == "p3"), None)
        if p3:
            assert p3["total_revenue"] == 0.0


# ---------------------------------------------------------------------------
# Group B — Service: ota_mix
# ---------------------------------------------------------------------------

class TestGroupBOtaMix:

    def test_b1_returns_list(self):
        result = svc.ota_mix(_BOOKINGS)
        assert isinstance(result, list)

    def test_b2_all_providers_present(self):
        result = svc.ota_mix(_BOOKINGS)
        providers = {r["provider"] for r in result}
        assert "airbnb" in providers
        assert "booking_com" in providers

    def test_b3_booking_pct_sums_to_100(self):
        result = svc.ota_mix(_BOOKINGS)
        total_pct = sum(r["booking_pct"] for r in result)
        assert abs(total_pct - 100.0) < 1.0  # float rounding tolerance

    def test_b4_revenue_sorted_descending(self):
        result = svc.ota_mix(_BOOKINGS)
        revenues = [r["revenue"] for r in result]
        assert revenues == sorted(revenues, reverse=True)


# ---------------------------------------------------------------------------
# Group C — Service: revenue_summary
# ---------------------------------------------------------------------------

class TestGroupCRevenueSummary:

    def test_c1_returns_list(self):
        result = svc.revenue_summary(_BOOKINGS)
        assert isinstance(result, list)

    def test_c2_each_entry_has_month_field(self):
        result = svc.revenue_summary(_BOOKINGS)
        assert all("month" in r for r in result)

    def test_c3_months_are_in_order(self):
        result = svc.revenue_summary(_BOOKINGS)
        months = [r["month"] for r in result]
        assert months == sorted(months)

    def test_c4_empty_bookings_returns_empty(self):
        result = svc.revenue_summary([])
        assert result == []


# ---------------------------------------------------------------------------
# Group D — HTTP: /admin/analytics/top-properties
# ---------------------------------------------------------------------------

class TestGroupDHttpTopProperties:

    def test_d1_returns_200(self):
        resp = client.get("/admin/analytics/top-properties", headers=_AUTH)
        assert resp.status_code == 200

    def test_d2_has_properties_key(self):
        resp = client.get("/admin/analytics/top-properties", headers=_AUTH)
        assert "properties" in resp.json()

    def test_d3_limit_param_works(self):
        resp = client.get("/admin/analytics/top-properties?limit=2", headers=_AUTH)
        assert resp.json()["limit"] == 2


# ---------------------------------------------------------------------------
# Group E — HTTP: ota-mix + revenue-summary
# ---------------------------------------------------------------------------

class TestGroupEHttpMixAndRevenue:

    def test_e1_ota_mix_returns_200(self):
        resp = client.get("/admin/analytics/ota-mix", headers=_AUTH)
        assert resp.status_code == 200

    def test_e2_ota_mix_has_providers(self):
        resp = client.get("/admin/analytics/ota-mix", headers=_AUTH)
        assert "providers" in resp.json()

    def test_e3_revenue_summary_returns_200(self):
        resp = client.get("/admin/analytics/revenue-summary", headers=_AUTH)
        assert resp.status_code == 200

    def test_e4_revenue_summary_has_summary(self):
        resp = client.get("/admin/analytics/revenue-summary", headers=_AUTH)
        assert "summary" in resp.json()
        assert isinstance(resp.json()["summary"], list)
