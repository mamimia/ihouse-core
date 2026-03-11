"""
Phase 267 — E2E Financial Aggregation + Financial Router Tests

Tests for the financial aggregation API surface.

Strategy:
- Groups A-E: call financial_aggregation_router handler functions directly
  (HTTP surface shadowed by financial_router's GET /financial/{booking_id}).
  This tests the business logic comprehensively without depending on route order.
- Groups F-G: full HTTP-level (TestClient) tests of financial_router's Phase 67/108
  endpoints (GET /financial/{booking_id}, GET /financial).

CI-safe: no live DB, no staging flag, no SUPABASE_URL required.
"""
from __future__ import annotations

import asyncio
import os
import sys
from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock, patch

os.environ.setdefault("IHOUSE_ENV", "test")

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from main import app  # noqa: E402

http_client = TestClient(app, raise_server_exceptions=False)

TENANT = "dev-tenant"
PERIOD = "2026-09"
BOOKING_ID = "bookingcom_bk001"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fact_row(**overrides: Any) -> dict:
    base = {
        "booking_id":          BOOKING_ID,
        "tenant_id":           TENANT,
        "provider":            "bookingcom",
        "property_id":         "prop-001",
        "currency":            "THB",
        "total_price":         "10000.00",
        "ota_commission":      "1500.00",
        "net_to_property":     "8500.00",
        "taxes":               None,
        "fees":                None,
        "recorded_at":         f"{PERIOD}-01",
        "payment_collected_by": "OTA",
        "management_fee_pct":  "10.00",
        "source_confidence":   "HIGH",
        "event_kind":          "BOOKING_CREATED",
        "envelope_type":       "BOOKING_CREATED",   # required by project_payment_lifecycle
    }
    base.update(overrides)
    return base


def _query_chain(rows: list):
    q = MagicMock()
    q.select.return_value = q
    q.eq.return_value = q
    q.gte.return_value = q
    q.lt.return_value = q
    q.lte.return_value = q
    q.in_.return_value = q
    q.limit.return_value = q
    q.order.return_value = q
    q.execute.return_value = MagicMock(data=rows)
    return q


def _make_db(fact_rows: list | None = None):
    db = MagicMock()
    rows = fact_rows if fact_rows is not None else [_fact_row()]
    db.table.return_value = _query_chain(rows)
    return db


@contextmanager
def _patch_fin_router(fact_rows: list | None = None):
    """Patch financial_router's Supabase client for HTTP-level tests."""
    db = _make_db(fact_rows)
    with patch("api.financial_router._get_supabase_client", return_value=db):
        yield db


def _run(coro):
    """Run an async handler function synchronously in tests."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# The financial aggregation router functions under test
# (Direct function calls — bypasses routing shadowing issue)
# ---------------------------------------------------------------------------

from api.financial_aggregation_router import (  # noqa: E402
    get_financial_summary,
    get_financial_by_provider,
    get_financial_by_property,
    get_lifecycle_distribution,
    get_multi_currency_overview,
)


# ---------------------------------------------------------------------------
# Group A — get_financial_summary (direct function call)
# ---------------------------------------------------------------------------

class TestGroupAFinancialSummary:

    def test_a1_missing_period_returns_400(self):
        r = _run(get_financial_summary(period=None, tenant_id=TENANT))
        assert r.status_code == 400

    def test_a2_bad_period_format_returns_400(self):
        r = _run(get_financial_summary(period="2026-13", tenant_id=TENANT))
        assert r.status_code == 400

    def test_a3_bad_base_currency_returns_400(self):
        r = _run(get_financial_summary(period=PERIOD, base_currency="XYZW", tenant_id=TENANT))
        assert r.status_code == 400

    def test_a4_valid_period_returns_200_with_currencies(self):
        db = _make_db()
        r = _run(get_financial_summary(period=PERIOD, tenant_id=TENANT, client=db))
        assert r.status_code == 200
        import json
        body = json.loads(r.body)
        assert "currencies" in body
        assert body["period"] == PERIOD

    def test_a5_empty_data_returns_zero_bookings(self):
        db = _make_db([])
        r = _run(get_financial_summary(period=PERIOD, tenant_id=TENANT, client=db))
        import json
        assert json.loads(r.body)["total_bookings"] == 0

    def test_a6_currency_bucket_has_financial_keys(self):
        db = _make_db()
        r = _run(get_financial_summary(period=PERIOD, tenant_id=TENANT, client=db))
        import json
        body = json.loads(r.body)
        currencies = body["currencies"]
        assert len(currencies) > 0
        bucket = next(iter(currencies.values()))
        for key in ("gross", "commission", "net", "booking_count"):
            assert key in bucket, f"Missing key: {key}"

    def test_a7_thb_currency_correctly_aggregated(self):
        db = _make_db([_fact_row(currency="THB", total_price="5000.00",
                                 ota_commission="750.00", net_to_property="4250.00")])
        r = _run(get_financial_summary(period=PERIOD, tenant_id=TENANT, client=db))
        import json
        body = json.loads(r.body)
        assert "THB" in body["currencies"]
        assert body["currencies"]["THB"]["gross"] == "5000.00"


# ---------------------------------------------------------------------------
# Group B — get_financial_by_provider (direct)
# ---------------------------------------------------------------------------

class TestGroupBByProvider:

    def test_b1_missing_period_returns_400(self):
        r = _run(get_financial_by_provider(period=None, tenant_id=TENANT))
        assert r.status_code == 400

    def test_b2_valid_period_returns_200_with_providers(self):
        db = _make_db()
        r = _run(get_financial_by_provider(period=PERIOD, tenant_id=TENANT, client=db))
        import json
        assert r.status_code == 200
        assert "providers" in json.loads(r.body)

    def test_b3_provider_key_present(self):
        db = _make_db([_fact_row(provider="airbnb")])
        r = _run(get_financial_by_provider(period=PERIOD, tenant_id=TENANT, client=db))
        import json
        assert "airbnb" in json.loads(r.body)["providers"]

    def test_b4_empty_data_returns_empty_providers(self):
        db = _make_db([])
        r = _run(get_financial_by_provider(period=PERIOD, tenant_id=TENANT, client=db))
        import json
        assert json.loads(r.body)["providers"] == {}


# ---------------------------------------------------------------------------
# Group C — get_financial_by_property (direct)
# ---------------------------------------------------------------------------

class TestGroupCByProperty:

    def test_c1_missing_period_returns_400(self):
        r = _run(get_financial_by_property(period=None, tenant_id=TENANT))
        assert r.status_code == 400

    def test_c2_valid_period_returns_200_with_properties(self):
        db = _make_db()
        r = _run(get_financial_by_property(period=PERIOD, tenant_id=TENANT, client=db))
        import json
        assert r.status_code == 200
        assert "properties" in json.loads(r.body)

    def test_c3_property_id_in_properties(self):
        db = _make_db([_fact_row(property_id="villa-007")])
        r = _run(get_financial_by_property(period=PERIOD, tenant_id=TENANT, client=db))
        import json
        assert "villa-007" in json.loads(r.body)["properties"]

    def test_c4_empty_data_returns_empty_properties(self):
        db = _make_db([])
        r = _run(get_financial_by_property(period=PERIOD, tenant_id=TENANT, client=db))
        import json
        assert json.loads(r.body)["properties"] == {}


# ---------------------------------------------------------------------------
# Group D — get_lifecycle_distribution (direct)
# ---------------------------------------------------------------------------

class TestGroupDLifecycleDistribution:

    def test_d1_missing_period_returns_400(self):
        r = _run(get_lifecycle_distribution(period=None, tenant_id=TENANT))
        assert r.status_code == 400

    def test_d2_valid_period_returns_200_with_distribution(self):
        db = _make_db()
        with patch("adapters.ota.payment_lifecycle.project_payment_lifecycle") as mock_plc:
            mock_plc.return_value = MagicMock(value="OTA_COLLECTING")
            r = _run(get_lifecycle_distribution(period=PERIOD, tenant_id=TENANT, client=db))
        import json
        assert r.status_code == 200
        body = json.loads(r.body)
        assert "distribution" in body

    def test_d3_required_keys_present(self):
        db = _make_db()
        with patch("adapters.ota.payment_lifecycle.project_payment_lifecycle") as mock_plc:
            mock_plc.return_value = MagicMock(value="OTA_COLLECTING")
            r = _run(get_lifecycle_distribution(period=PERIOD, tenant_id=TENANT, client=db))
        import json
        body = json.loads(r.body)
        for key in ("tenant_id", "period", "total_bookings", "distribution"):
            assert key in body, f"Missing key: {key}"

    def test_d4_empty_data_returns_zero_total(self):
        db = _make_db([])
        r = _run(get_lifecycle_distribution(period=PERIOD, tenant_id=TENANT, client=db))
        import json
        assert json.loads(r.body)["total_bookings"] == 0


# ---------------------------------------------------------------------------
# Group E — get_multi_currency_overview (direct)
# ---------------------------------------------------------------------------

class TestGroupEMultiCurrencyOverview:

    def test_e1_missing_period_returns_400(self):
        r = _run(get_multi_currency_overview(period=None, tenant_id=TENANT))
        assert r.status_code == 400

    def test_e2_invalid_currency_filter_returns_400(self):
        r = _run(get_multi_currency_overview(period=PERIOD, currency="TOOLONG", tenant_id=TENANT))
        assert r.status_code == 400

    def test_e3_valid_returns_200_with_period(self):
        db = _make_db()
        r = _run(get_multi_currency_overview(period=PERIOD, tenant_id=TENANT, client=db))
        import json
        assert r.status_code == 200
        assert json.loads(r.body)["period"] == PERIOD

    def test_e4_empty_data_returns_200(self):
        db = _make_db([])
        r = _run(get_multi_currency_overview(period=PERIOD, tenant_id=TENANT, client=db))
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Group F — GET /financial/{booking_id} (HTTP — financial_router Phase 67)
# ---------------------------------------------------------------------------

class TestGroupFSingleFinancialFacts:

    def test_f1_returns_200_with_correct_shape(self):
        with _patch_fin_router():
            r = http_client.get(f"/financial/{BOOKING_ID}")
        assert r.status_code == 200, f"Got {r.status_code}: {r.text}"
        body = r.json()
        assert body["booking_id"] == BOOKING_ID
        assert body["tenant_id"] == TENANT

    def test_f2_required_keys_in_response(self):
        with _patch_fin_router():
            r = http_client.get(f"/financial/{BOOKING_ID}")
        body = r.json()
        for key in ("booking_id", "tenant_id", "provider", "total_price",
                    "currency", "ota_commission", "net_to_property",
                    "source_confidence", "event_kind", "recorded_at"):
            assert key in body, f"Missing key: {key}"

    def test_f3_returns_404_when_no_facts(self):
        with _patch_fin_router([]):
            r = http_client.get("/financial/unknown_booking_xyz")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Group G — GET /financial (list — financial_router Phase 108)
# ---------------------------------------------------------------------------

class TestGroupGListFinancial:

    def test_g1_returns_200_with_records_key(self):
        with _patch_fin_router():
            r = http_client.get("/financial")
        assert r.status_code == 200, f"Got {r.status_code}: {r.text}"
        assert "records" in r.json()

    def test_g2_count_and_limit_present(self):
        with _patch_fin_router():
            r = http_client.get("/financial")
        body = r.json()
        assert "count" in body
        assert "limit" in body

    def test_g3_invalid_month_returns_400(self):
        with _patch_fin_router():
            r = http_client.get("/financial?month=2026-99")
        assert r.status_code == 400

    def test_g4_empty_result_has_zero_count(self):
        with _patch_fin_router([]):
            r = http_client.get("/financial")
        assert r.json()["count"] == 0
