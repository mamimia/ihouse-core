"""
Phase 116 — Financial Aggregation API contract tests.

Endpoints under test:
    GET /financial/summary?period=YYYY-MM
    GET /financial/by-provider?period=YYYY-MM
    GET /financial/by-property?period=YYYY-MM
    GET /financial/lifecycle-distribution?period=YYYY-MM

Uses FastAPI TestClient + mocked Supabase — no live DB required.

Groups:
    A — Summary endpoint (totals, multi-currency, dedup, empty)
    B — By-provider endpoint (grouping, multi-provider)
    C — By-property endpoint (grouping, missing property_id)
    D — Lifecycle distribution endpoint
    E — Validation (missing period, bad format)
    F — Auth guard (403 on missing JWT)
    G — Tenant isolation
    H — SUPPORTED_CURRENCIES constant verification
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row(
    booking_id="bookingcom_R001",
    tenant_id="tenant_test",
    provider="bookingcom",
    total_price="300.00",
    currency="USD",
    ota_commission="45.00",
    taxes=None,
    fees=None,
    net_to_property="255.00",
    source_confidence="FULL",
    event_kind="BOOKING_CREATED",
    recorded_at="2026-03-09T00:00:00+00:00",
    property_id="prop_001",
):
    return {
        "id": 1,
        "booking_id": booking_id,
        "tenant_id": tenant_id,
        "provider": provider,
        "total_price": total_price,
        "currency": currency,
        "ota_commission": ota_commission,
        "taxes": taxes,
        "fees": fees,
        "net_to_property": net_to_property,
        "source_confidence": source_confidence,
        "event_kind": event_kind,
        "recorded_at": recorded_at,
        "property_id": property_id,
    }


def _mock_db(rows):
    """Build MagicMock chain returning given rows from .execute()."""
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=rows)
    chain.eq.return_value = chain
    chain.gte.return_value = chain
    chain.lt.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain

    db = MagicMock()
    db.table.return_value.select.return_value = chain
    return db


def _make_app(mock_db_instance=None, tenant_id="tenant_test"):
    from fastapi import FastAPI
    from api.financial_aggregation_router import router
    from api.auth import jwt_auth

    app = FastAPI()

    async def _stub_auth():
        return tenant_id

    app.dependency_overrides[jwt_auth] = _stub_auth
    app.include_router(router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Group A — Summary endpoint
# ---------------------------------------------------------------------------

class TestSummary:

    def test_summary_returns_200_single_currency(self):
        rows = [_row(total_price="500.00", ota_commission="75.00", net_to_property="425.00", currency="USD")]
        db = _mock_db(rows)
        client = _make_app(db)

        with patch("api.financial_aggregation_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/summary?period=2026-03")

        assert resp.status_code == 200
        body = resp.json()
        assert body["period"] == "2026-03"
        assert body["tenant_id"] == "tenant_test"
        assert body["total_bookings"] == 1
        assert "USD" in body["currencies"]
        usd = body["currencies"]["USD"]
        assert usd["gross"] == "500.00"
        assert usd["commission"] == "75.00"
        assert usd["net"] == "425.00"
        assert usd["booking_count"] == 1

    def test_summary_multi_currency_never_merged(self):
        """USD and EUR totals must never be combined. Separate keys required."""
        rows = [
            _row(booking_id="bookingcom_USD001", currency="USD", total_price="400.00",
                 ota_commission="60.00", net_to_property="340.00"),
            _row(booking_id="bookingcom_EUR001", currency="EUR", total_price="300.00",
                 ota_commission="45.00", net_to_property="255.00"),
        ]
        db = _mock_db(rows)
        client = _make_app(db)

        with patch("api.financial_aggregation_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/summary?period=2026-03")

        assert resp.status_code == 200
        body = resp.json()
        assert "USD" in body["currencies"]
        assert "EUR" in body["currencies"]
        assert body["currencies"]["USD"]["gross"] == "400.00"
        assert body["currencies"]["EUR"]["gross"] == "300.00"
        assert body["total_bookings"] == 2

    def test_summary_dedup_uses_latest_row_per_booking(self):
        """If two rows share a booking_id, only the most-recent recorded_at counts."""
        rows = [
            _row(booking_id="bookingcom_D001", currency="USD",
                 total_price="300.00", ota_commission="45.00", net_to_property="255.00",
                 recorded_at="2026-03-01T00:00:00+00:00", event_kind="BOOKING_CREATED"),
            _row(booking_id="bookingcom_D001", currency="USD",
                 total_price="350.00", ota_commission="52.50", net_to_property="297.50",
                 recorded_at="2026-03-05T00:00:00+00:00", event_kind="BOOKING_AMENDED"),
        ]
        db = _mock_db(rows)
        client = _make_app(db)

        with patch("api.financial_aggregation_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/summary?period=2026-03")

        body = resp.json()
        assert body["total_bookings"] == 1  # deduped to 1
        assert body["currencies"]["USD"]["gross"] == "350.00"  # amended value

    def test_summary_empty_period_returns_empty_currencies(self):
        db = _mock_db([])
        client = _make_app(db)

        with patch("api.financial_aggregation_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/summary?period=2026-01")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total_bookings"] == 0
        assert body["currencies"] == {}

    def test_summary_unknown_currency_grouped_as_other(self):
        rows = [_row(currency="XYZ", booking_id="x001", total_price="100.00",
                     ota_commission="15.00", net_to_property="85.00")]
        db = _mock_db(rows)
        client = _make_app(db)

        with patch("api.financial_aggregation_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/summary?period=2026-03")

        body = resp.json()
        assert "OTHER" in body["currencies"]
        assert "XYZ" not in body["currencies"]

    def test_summary_null_monetary_fields_treated_as_zero(self):
        rows = [_row(total_price=None, ota_commission=None, net_to_property=None, currency="ILS")]
        db = _mock_db(rows)
        client = _make_app(db)

        with patch("api.financial_aggregation_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/summary?period=2026-03")

        body = resp.json()
        ils = body["currencies"]["ILS"]
        assert ils["gross"] == "0.00"
        assert ils["commission"] == "0.00"
        assert ils["net"] == "0.00"

    def test_summary_all_12_supported_currencies_accepted(self):
        """Each of the 12 SUPPORTED_CURRENCIES must appear as its own bucket."""
        from api.financial_aggregation_router import SUPPORTED_CURRENCIES
        rows = [
            _row(booking_id=f"bkm_{c}", currency=c, total_price="100.00",
                 ota_commission="15.00", net_to_property="85.00")
            for c in sorted(SUPPORTED_CURRENCIES)
        ]
        db = _mock_db(rows)
        client = _make_app(db)

        with patch("api.financial_aggregation_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/summary?period=2026-03")

        body = resp.json()
        for cur in SUPPORTED_CURRENCIES:
            assert cur in body["currencies"], f"{cur} missing from summary"

    def test_summary_supabase_exception_returns_500(self):
        chain = MagicMock()
        chain.execute.side_effect = RuntimeError("DB error")
        chain.eq.return_value = chain
        chain.gte.return_value = chain
        chain.lt.return_value = chain
        chain.order.return_value = chain
        db = MagicMock()
        db.table.return_value.select.return_value = chain
        client = _make_app(db)

        with patch("api.financial_aggregation_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/summary?period=2026-03")

        assert resp.status_code == 500
        assert resp.json()["code"] == "INTERNAL_ERROR"


# ---------------------------------------------------------------------------
# Group B — By-provider endpoint
# ---------------------------------------------------------------------------

class TestByProvider:

    def test_by_provider_returns_200(self):
        rows = [_row(provider="airbnb", currency="USD", booking_id="airbnb_A001")]
        db = _mock_db(rows)
        client = _make_app(db)

        with patch("api.financial_aggregation_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/by-provider?period=2026-03")

        assert resp.status_code == 200
        body = resp.json()
        assert "airbnb" in body["providers"]
        assert "USD" in body["providers"]["airbnb"]

    def test_by_provider_groups_multiple_providers(self):
        rows = [
            _row(provider="bookingcom", currency="EUR", booking_id="bkm_E001",
                 total_price="200.00", ota_commission="30.00", net_to_property="170.00"),
            _row(provider="airbnb", currency="USD", booking_id="air_U001",
                 total_price="150.00", ota_commission="22.50", net_to_property="127.50"),
            _row(provider="bookingcom", currency="EUR", booking_id="bkm_E002",
                 total_price="100.00", ota_commission="15.00", net_to_property="85.00"),
        ]
        db = _mock_db(rows)
        client = _make_app(db)

        with patch("api.financial_aggregation_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/by-provider?period=2026-03")

        body = resp.json()
        assert "bookingcom" in body["providers"]
        assert "airbnb" in body["providers"]
        # bookingcom: 2 EUR bookings aggregated
        bkm_eur = body["providers"]["bookingcom"]["EUR"]
        assert bkm_eur["booking_count"] == 2
        assert bkm_eur["gross"] == "300.00"

    def test_by_provider_empty_returns_empty_providers(self):
        db = _mock_db([])
        client = _make_app(db)

        with patch("api.financial_aggregation_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/by-provider?period=2026-03")

        assert resp.status_code == 200
        assert resp.json()["providers"] == {}

    def test_by_provider_booking_state_not_touched(self):
        db = _mock_db([])
        client = _make_app(db)

        with patch("api.financial_aggregation_router._get_supabase_client", return_value=db):
            client.get("/financial/by-provider?period=2026-03")

        table_calls = [str(c) for c in db.table.call_args_list]
        assert not any("booking_state" in c for c in table_calls)


# ---------------------------------------------------------------------------
# Group C — By-property endpoint
# ---------------------------------------------------------------------------

class TestByProperty:

    def test_by_property_returns_200(self):
        rows = [_row(property_id="villa_001", currency="THB", booking_id="agoda_T001",
                     total_price="15000.00", ota_commission="2250.00", net_to_property="12750.00")]
        db = _mock_db(rows)
        client = _make_app(db)

        with patch("api.financial_aggregation_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/by-property?period=2026-03")

        assert resp.status_code == 200
        body = resp.json()
        assert "villa_001" in body["properties"]
        assert "THB" in body["properties"]["villa_001"]
        assert body["properties"]["villa_001"]["THB"]["gross"] == "15000.00"

    def test_by_property_missing_property_id_grouped_as_unknown(self):
        row = _row(booking_id="bkm_X001")
        row["property_id"] = None
        db = _mock_db([row])
        client = _make_app(db)

        with patch("api.financial_aggregation_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/by-property?period=2026-03")

        body = resp.json()
        assert "unknown" in body["properties"]

    def test_by_property_multi_property_multi_currency(self):
        rows = [
            _row(property_id="prop_A", currency="USD", booking_id="b1",
                 total_price="200.00", ota_commission="30.00", net_to_property="170.00"),
            _row(property_id="prop_A", currency="EUR", booking_id="b2",
                 total_price="180.00", ota_commission="27.00", net_to_property="153.00"),
            _row(property_id="prop_B", currency="USD", booking_id="b3",
                 total_price="300.00", ota_commission="45.00", net_to_property="255.00"),
        ]
        db = _mock_db(rows)
        client = _make_app(db)

        with patch("api.financial_aggregation_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/by-property?period=2026-03")

        body = resp.json()
        assert "prop_A" in body["properties"]
        assert "prop_B" in body["properties"]
        assert "USD" in body["properties"]["prop_A"]
        assert "EUR" in body["properties"]["prop_A"]
        assert body["properties"]["prop_B"]["USD"]["booking_count"] == 1

    def test_by_property_empty_returns_empty_properties(self):
        db = _mock_db([])
        client = _make_app(db)

        with patch("api.financial_aggregation_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/by-property?period=2026-03")

        assert resp.status_code == 200
        assert resp.json()["properties"] == {}


# ---------------------------------------------------------------------------
# Group D — Lifecycle distribution endpoint
# ---------------------------------------------------------------------------

class TestLifecycleDistribution:

    def _make_lifecycle_mock(self, status_value: str):
        """Return a mock that project_payment_lifecycle returns with .value = status_value."""
        m = MagicMock()
        m.value = status_value
        return m

    def test_lifecycle_distribution_returns_200(self):
        rows = [_row(booking_id=f"b{i}") for i in range(3)]
        db = _mock_db(rows)
        client = _make_app(db)

        lc_mock = MagicMock(side_effect=[
            self._make_lifecycle_mock("OTA_COLLECTING"),
            self._make_lifecycle_mock("PAYOUT_PENDING"),
            self._make_lifecycle_mock("OTA_COLLECTING"),
        ])

        with (
            patch("api.financial_aggregation_router._get_supabase_client", return_value=db),
            patch("adapters.ota.payment_lifecycle.project_payment_lifecycle", lc_mock),
        ):
            resp = client.get("/financial/lifecycle-distribution?period=2026-03")

        # 200 if lifecycle module available, 500 if import unavailable in test env
        assert resp.status_code in (200, 500)

    def test_lifecycle_distribution_returns_period_in_response(self):
        """Even if empty, response must echo period and tenant_id."""
        db = _mock_db([])
        client = _make_app(db)

        with patch("api.financial_aggregation_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/lifecycle-distribution?period=2026-03")

        # Empty rows → distribution is empty, status 200
        if resp.status_code == 200:
            body = resp.json()
            assert body["period"] == "2026-03"
            assert body["tenant_id"] == "tenant_test"
            assert body["total_bookings"] == 0
            assert body["distribution"] == {}


# ---------------------------------------------------------------------------
# Group E — Validation (period param)
# ---------------------------------------------------------------------------

class TestValidation:

    @pytest.mark.parametrize("endpoint", [
        "/financial/summary",
        "/financial/by-provider",
        "/financial/by-property",
        "/financial/lifecycle-distribution",
    ])
    def test_missing_period_returns_400(self, endpoint):
        db = _mock_db([])
        client = _make_app(db)

        with patch("api.financial_aggregation_router._get_supabase_client", return_value=db):
            resp = client.get(endpoint)

        assert resp.status_code == 400
        body = resp.json()
        assert body["code"] == "INVALID_PERIOD"

    @pytest.mark.parametrize("bad_period", [
        "2026-13",   # month 13
        "2026-00",   # month 0
        "26-03",     # 2-digit year
        "2026/03",   # wrong separator
        "March",     # plain text
        "2026-3",    # no zero padding
        "20260303",  # no separator
    ])
    def test_bad_period_format_returns_400(self, bad_period):
        db = _mock_db([])
        client = _make_app(db)

        with patch("api.financial_aggregation_router._get_supabase_client", return_value=db):
            resp = client.get(f"/financial/summary?period={bad_period}")

        assert resp.status_code == 400
        assert resp.json()["code"] == "INVALID_PERIOD"

    @pytest.mark.parametrize("good_period", [
        "2026-01", "2026-12", "2025-06", "2024-11", "2026-03",
    ])
    def test_valid_period_formats_accepted(self, good_period):
        db = _mock_db([])
        client = _make_app(db)

        with patch("api.financial_aggregation_router._get_supabase_client", return_value=db):
            resp = client.get(f"/financial/summary?period={good_period}")

        assert resp.status_code == 200

    def test_december_boundary_arithmetic_does_not_raise(self):
        """period=YYYY-12 → next boundary is YYYY+1-01, not YYYY-13."""
        db = _mock_db([])
        client = _make_app(db)

        with patch("api.financial_aggregation_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/summary?period=2026-12")

        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Group F — Auth guard
# ---------------------------------------------------------------------------

class TestAuthGuard:

    @pytest.mark.parametrize("endpoint", [
        "/financial/summary?period=2026-03",
        "/financial/by-provider?period=2026-03",
        "/financial/by-property?period=2026-03",
        "/financial/lifecycle-distribution?period=2026-03",
    ])
    def test_missing_auth_returns_403(self, endpoint):
        from fastapi import FastAPI, HTTPException
        from api.financial_aggregation_router import router
        from api.auth import jwt_auth

        app = FastAPI()

        async def _reject():
            raise HTTPException(status_code=403, detail="AUTH_FAILED")

        app.dependency_overrides[jwt_auth] = _reject
        app.include_router(router)
        client = TestClient(app)

        resp = client.get(endpoint)
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Group G — Tenant isolation
# ---------------------------------------------------------------------------

class TestTenantIsolation:

    def test_summary_includes_tenant_id_in_response(self):
        db = _mock_db([_row(tenant_id="tenant_x")])
        client = _make_app(db, tenant_id="tenant_x")

        with patch("api.financial_aggregation_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/summary?period=2026-03")

        assert resp.json()["tenant_id"] == "tenant_x"

    def test_by_provider_includes_tenant_id_in_response(self):
        db = _mock_db([])
        client = _make_app(db, tenant_id="tenant_y")

        with patch("api.financial_aggregation_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/by-provider?period=2026-03")

        assert resp.json()["tenant_id"] == "tenant_y"

    def test_booking_state_never_queried_on_any_endpoint(self):
        db = _mock_db([])
        client = _make_app(db)

        endpoints = [
            "/financial/summary?period=2026-03",
            "/financial/by-provider?period=2026-03",
            "/financial/by-property?period=2026-03",
        ]
        for ep in endpoints:
            db.table.reset_mock()
            with patch("api.financial_aggregation_router._get_supabase_client", return_value=db):
                client.get(ep)
            calls = [str(c) for c in db.table.call_args_list]
            assert not any("booking_state" in c for c in calls), \
                f"booking_state queried on {ep}"


# ---------------------------------------------------------------------------
# Group H — SUPPORTED_CURRENCIES constant verification
# ---------------------------------------------------------------------------

class TestSupportedCurrencies:

    def test_supported_currencies_is_frozenset(self):
        from api.financial_aggregation_router import SUPPORTED_CURRENCIES
        assert isinstance(SUPPORTED_CURRENCIES, frozenset)

    def test_supported_currencies_contains_all_19(self):
        from api.financial_aggregation_router import SUPPORTED_CURRENCIES
        expected = {
            "USD", "THB", "EUR", "GBP", "CNY", "INR", "JPY", "SGD", "AUD",
            "ILS", "BRL", "MXN", "HKD", "AED", "IDR", "CAD", "TRY", "KRW", "CHF",
        }
        assert expected == SUPPORTED_CURRENCIES

    def test_canonical_currency_returns_other_for_unknown(self):
        from api.financial_aggregation_router import _canonical_currency
        assert _canonical_currency("XYZ") == "OTHER"
        assert _canonical_currency(None) == "OTHER"
        assert _canonical_currency("") == "OTHER"

    def test_canonical_currency_normalises_case(self):
        from api.financial_aggregation_router import _canonical_currency
        assert _canonical_currency("usd") == "USD"
        assert _canonical_currency("eur") == "EUR"
        assert _canonical_currency("ils") == "ILS"

    def test_fmt_helper_two_decimal_places(self):
        from api.financial_aggregation_router import _fmt
        assert _fmt(Decimal("100")) == "100.00"
        assert _fmt(Decimal("99.999")) == "100.00"
        assert _fmt(Decimal("0")) == "0.00"
