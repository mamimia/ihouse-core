"""
Phase 122 — OTA Financial Health Comparison — Contract Tests

Endpoint under test:
    GET /financial/ota-comparison?period=YYYY-MM

Groups:
    A — Validation (period param required, YYYY-MM format)
    B — Empty period (no rows → empty providers dict)
    C — Response shape (top-level keys, per-OTA keys)
    D — Per-OTA metric correctness (commission rate, net-to-gross, revenue share)
    E — Multi-currency (no cross-currency arithmetic)
    F — Deduplication (most-recent recorded_at per booking_id)
    G — OTA_COLLECTING lifecycle in lifecycle_distribution
    H — Epistemic tier (worst tier wins per OTA)
    I — Auth guard (403)
    J — Tenant isolation + INTERNAL_ERROR
    K — booking_state never read
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("fastapi")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row(
    booking_id: str = "bookingcom_R001",
    tenant_id: str = "tenant_test",
    provider: str = "bookingcom",
    total_price: str = "1000.00",
    currency: str = "USD",
    ota_commission: str = "150.00",
    net_to_property: str = "850.00",
    source_confidence: str = "FULL",
    event_kind: str = "BOOKING_CREATED",
    recorded_at: str = "2026-03-05T10:00:00+00:00",
    property_id: str = "prop-1",
) -> dict:
    return {
        "booking_id": booking_id,
        "tenant_id": tenant_id,
        "provider": provider,
        "total_price": total_price,
        "currency": currency,
        "ota_commission": ota_commission,
        "taxes": None,
        "fees": None,
        "net_to_property": net_to_property,
        "source_confidence": source_confidence,
        "event_kind": event_kind,
        "recorded_at": recorded_at,
        "property_id": property_id,
        "raw_financial_fields": {},
    }


def _mock_db(rows: list) -> MagicMock:
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=rows)
    chain.eq.return_value = chain
    chain.gte.return_value = chain
    chain.lt.return_value = chain
    chain.order.return_value = chain

    db = MagicMock()
    db.table.return_value.select.return_value = chain
    return db


def _make_app(tenant_id: str = "tenant_test") -> TestClient:
    from fastapi import FastAPI
    from api.ota_comparison_router import router
    from api.auth import jwt_auth

    app = FastAPI()

    async def _stub_auth():
        return tenant_id

    app.dependency_overrides[jwt_auth] = _stub_auth
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


# ===========================================================================
# Group A — Validation
# ===========================================================================

class TestGroupA_Validation:

    def test_a1_missing_period_returns_400(self) -> None:
        """A1: period param required → 400 INVALID_PERIOD."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison")
        assert resp.status_code == 400
        assert resp.json()["code"] == "INVALID_PERIOD"

    def test_a2_bad_period_format_returns_400(self) -> None:
        """A2: period=2026/03 → 400 INVALID_PERIOD."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2026/03")
        assert resp.status_code == 400
        assert resp.json()["code"] == "INVALID_PERIOD"

    def test_a3_invalid_month_number_returns_400(self) -> None:
        """A3: period=2026-13 → 400 INVALID_PERIOD."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2026-13")
        assert resp.status_code == 400
        assert resp.json()["code"] == "INVALID_PERIOD"

    def test_a4_valid_period_returns_200(self) -> None:
        """A4: period=2026-03 → 200."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2026-03")
        assert resp.status_code == 200

    def test_a5_period_echoed_in_response(self) -> None:
        """A5: period is echoed in response."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2026-06")
        assert resp.json()["period"] == "2026-06"


# ===========================================================================
# Group B — Empty period
# ===========================================================================

class TestGroupB_Empty:

    def test_b1_no_rows_returns_200_not_404(self) -> None:
        """B1: No rows for the period → 200 with empty providers."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2025-01")
        assert resp.status_code == 200

    def test_b2_empty_providers_dict(self) -> None:
        """B2: No rows → providers={}."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2025-01")
        assert resp.json()["providers"] == {}

    def test_b3_total_bookings_is_zero(self) -> None:
        """B3: No rows → total_bookings=0."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2025-01")
        assert resp.json()["total_bookings"] == 0


# ===========================================================================
# Group C — Response shape
# ===========================================================================

class TestGroupC_ResponseShape:

    def test_c1_top_level_keys_present(self) -> None:
        """C1: Required top-level keys present."""
        c = _make_app()
        db = _mock_db([_row()])
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2026-03")
        body = resp.json()
        for key in ["tenant_id", "period", "total_bookings", "providers"]:
            assert key in body, f"Missing key: {key}"

    def test_c2_provider_currency_bucket_has_required_keys(self) -> None:
        """C2: Per-(OTA, currency) bucket has all required keys."""
        c = _make_app()
        db = _mock_db([_row()])
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2026-03")
        bucket = resp.json()["providers"]["bookingcom"]["USD"]
        for key in [
            "booking_count", "gross_total", "commission_total", "net_total",
            "avg_commission_rate", "net_to_gross_ratio", "revenue_share_pct",
            "epistemic_tier", "lifecycle_distribution",
        ]:
            assert key in bucket, f"Missing bucket key: {key}"

    def test_c3_tenant_id_correct(self) -> None:
        """C3: tenant_id is echoed correctly."""
        c = _make_app(tenant_id="t-gamma")
        db = _mock_db([_row(tenant_id="t-gamma")])
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2026-03")
        assert resp.json()["tenant_id"] == "t-gamma"

    def test_c4_total_bookings_counts_deduped_rows(self) -> None:
        """C4: total_bookings counts unique bookings after dedup."""
        rows = [_row(booking_id="bookingcom_R001"), _row(booking_id="airbnb_R002", provider="airbnb")]
        c = _make_app()
        db = _mock_db(rows)
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2026-03")
        assert resp.json()["total_bookings"] == 2

    def test_c5_providers_is_dict(self) -> None:
        """C5: providers is a dict."""
        c = _make_app()
        db = _mock_db([_row()])
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2026-03")
        assert isinstance(resp.json()["providers"], dict)

    def test_c6_lifecycle_distribution_is_dict(self) -> None:
        """C6: lifecycle_distribution is a dict."""
        c = _make_app()
        db = _mock_db([_row()])
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2026-03")
        ld = resp.json()["providers"]["bookingcom"]["USD"]["lifecycle_distribution"]
        assert isinstance(ld, dict)


# ===========================================================================
# Group D — Per-OTA metric correctness
# ===========================================================================

class TestGroupD_Metrics:

    def test_d1_booking_count_correct(self) -> None:
        """D1: booking_count = unique bookings for this OTA."""
        rows = [
            _row(booking_id="bookingcom_R001"),
            _row(booking_id="bookingcom_R002"),
        ]
        c = _make_app()
        db = _mock_db(rows)
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2026-03")
        assert resp.json()["providers"]["bookingcom"]["USD"]["booking_count"] == 2

    def test_d2_gross_total_is_sum(self) -> None:
        """D2: gross_total = sum of total_price for this OTA + currency."""
        rows = [
            _row(booking_id="bookingcom_R001", total_price="1000.00"),
            _row(booking_id="bookingcom_R002", total_price="2000.00"),
        ]
        c = _make_app()
        db = _mock_db(rows)
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2026-03")
        assert resp.json()["providers"]["bookingcom"]["USD"]["gross_total"] == "3000.00"

    def test_d3_commission_total_is_sum(self) -> None:
        """D3: commission_total = sum of ota_commission."""
        rows = [
            _row(booking_id="bookingcom_R001", ota_commission="100.00"),
            _row(booking_id="bookingcom_R002", ota_commission="200.00"),
        ]
        c = _make_app()
        db = _mock_db(rows)
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2026-03")
        assert resp.json()["providers"]["bookingcom"]["USD"]["commission_total"] == "300.00"

    def test_d4_net_total_is_sum(self) -> None:
        """D4: net_total = sum of net_to_property."""
        rows = [
            _row(booking_id="bookingcom_R001", net_to_property="850.00"),
            _row(booking_id="bookingcom_R002", net_to_property="1700.00"),
        ]
        c = _make_app()
        db = _mock_db(rows)
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2026-03")
        assert resp.json()["providers"]["bookingcom"]["USD"]["net_total"] == "2550.00"

    def test_d5_avg_commission_rate_single_booking(self) -> None:
        """D5: avg_commission_rate = commission/gross × 100.
        gross=1000, ota_commission=150 → rate = 15.00%."""
        c = _make_app()
        db = _mock_db([_row(total_price="1000.00", ota_commission="150.00")])
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2026-03")
        assert resp.json()["providers"]["bookingcom"]["USD"]["avg_commission_rate"] == "15.00"

    def test_d6_net_to_gross_ratio_single_booking(self) -> None:
        """D6: net_to_gross_ratio = net/gross × 100.
        gross=1000, net=850 → ratio = 85.00%."""
        c = _make_app()
        db = _mock_db([_row(total_price="1000.00", net_to_property="850.00")])
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2026-03")
        assert resp.json()["providers"]["bookingcom"]["USD"]["net_to_gross_ratio"] == "85.00"

    def test_d7_revenue_share_100pct_single_ota(self) -> None:
        """D7: Only one OTA → revenue_share_pct = 100.00."""
        c = _make_app()
        db = _mock_db([_row()])
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2026-03")
        assert resp.json()["providers"]["bookingcom"]["USD"]["revenue_share_pct"] == "100.00"

    def test_d8_revenue_share_two_equal_otas(self) -> None:
        """D8: Two OTAs, equal gross → each 50.00%."""
        rows = [
            _row(booking_id="bookingcom_R001", provider="bookingcom", total_price="1000.00"),
            _row(booking_id="airbnb_R001", provider="airbnb", total_price="1000.00"),
        ]
        c = _make_app()
        db = _mock_db(rows)
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2026-03")
        providers = resp.json()["providers"]
        assert providers["bookingcom"]["USD"]["revenue_share_pct"] == "50.00"
        assert providers["airbnb"]["USD"]["revenue_share_pct"] == "50.00"

    def test_d9_zero_gross_commission_rate_is_null(self) -> None:
        """D9: total_price=0 → avg_commission_rate=null (no division by zero)."""
        c = _make_app()
        db = _mock_db([_row(total_price="0", ota_commission="0")])
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2026-03")
        assert resp.json()["providers"]["bookingcom"]["USD"]["avg_commission_rate"] is None

    def test_d10_gross_total_is_2dp_string(self) -> None:
        """D10: gross_total is a 2dp formatted string."""
        c = _make_app()
        db = _mock_db([_row(total_price="1000")])
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2026-03")
        assert resp.json()["providers"]["bookingcom"]["USD"]["gross_total"] == "1000.00"

    def test_d11_two_different_otas_in_providers(self) -> None:
        """D11: Two different providers both appear in providers dict."""
        rows = [
            _row(booking_id="bookingcom_R001", provider="bookingcom"),
            _row(booking_id="airbnb_R002", provider="airbnb"),
        ]
        c = _make_app()
        db = _mock_db(rows)
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2026-03")
        providers = resp.json()["providers"]
        assert "bookingcom" in providers
        assert "airbnb" in providers


# ===========================================================================
# Group E — Multi-currency
# ===========================================================================

class TestGroupE_MultiCurrency:

    def test_e1_different_currencies_separate_buckets(self) -> None:
        """E1: USD and THB bookings → separate currency buckets per OTA."""
        rows = [
            _row(booking_id="bookingcom_R001", currency="USD"),
            _row(booking_id="bookingcom_R002", currency="THB"),
        ]
        c = _make_app()
        db = _mock_db(rows)
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2026-03")
        ota = resp.json()["providers"]["bookingcom"]
        assert "USD" in ota
        assert "THB" in ota

    def test_e2_no_cross_currency_gross_total(self) -> None:
        """E2: USD gross is not contaminated by THB gross."""
        rows = [
            _row(booking_id="bookingcom_R001", currency="USD", total_price="1000.00"),
            _row(booking_id="bookingcom_R002", currency="THB", total_price="35000.00"),
        ]
        c = _make_app()
        db = _mock_db(rows)
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2026-03")
        ota = resp.json()["providers"]["bookingcom"]
        assert ota["USD"]["gross_total"] == "1000.00"
        assert ota["THB"]["gross_total"] == "35000.00"

    def test_e3_revenue_share_per_currency_not_cross_currency(self) -> None:
        """E3: Revenue share is computed per currency, not mixed."""
        rows = [
            _row(booking_id="bookingcom_R001", provider="bookingcom",
                 currency="USD", total_price="1000.00"),
            _row(booking_id="airbnb_R001", provider="airbnb",
                 currency="THB", total_price="35000.00"),
        ]
        c = _make_app()
        db = _mock_db(rows)
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2026-03")
        providers = resp.json()["providers"]
        # Each OTA has 100% share of its own currency (no other OTA in that currency)
        assert providers["bookingcom"]["USD"]["revenue_share_pct"] == "100.00"
        assert providers["airbnb"]["THB"]["revenue_share_pct"] == "100.00"


# ===========================================================================
# Group F — Deduplication
# ===========================================================================

class TestGroupF_Deduplication:

    def test_f1_duplicate_booking_ids_deduped(self) -> None:
        """F1: Two rows same booking_id → only most-recent kept → booking_count=1."""
        rows = [
            _row(booking_id="bookingcom_R001",
                 total_price="1000.00",
                 recorded_at="2026-03-01T10:00:00+00:00"),
            _row(booking_id="bookingcom_R001",
                 total_price="1200.00",
                 recorded_at="2026-03-10T10:00:00+00:00"),
        ]
        c = _make_app()
        db = _mock_db(rows)
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2026-03")
        ota = resp.json()["providers"]["bookingcom"]["USD"]
        assert ota["booking_count"] == 1
        # Most-recent row wins → gross_total=1200
        assert ota["gross_total"] == "1200.00"

    def test_f2_two_distinct_bookings_both_counted(self) -> None:
        """F2: Two distinct booking_ids → booking_count=2."""
        rows = [
            _row(booking_id="bookingcom_R001"),
            _row(booking_id="bookingcom_R002"),
        ]
        c = _make_app()
        db = _mock_db(rows)
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2026-03")
        assert resp.json()["providers"]["bookingcom"]["USD"]["booking_count"] == 2


# ===========================================================================
# Group G — OTA_COLLECTING in lifecycle_distribution
# ===========================================================================

class TestGroupG_LifecycleDistribution:

    def test_g1_lifecycle_distribution_present_and_non_empty(self) -> None:
        """G1: lifecycle_distribution has at least one entry."""
        c = _make_app()
        db = _mock_db([_row()])
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2026-03")
        ld = resp.json()["providers"]["bookingcom"]["USD"]["lifecycle_distribution"]
        assert len(ld) >= 1

    def test_g2_all_lifecycle_values_are_ints(self) -> None:
        """G2: All lifecycle distribution values are integers."""
        c = _make_app()
        db = _mock_db([_row()])
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2026-03")
        ld = resp.json()["providers"]["bookingcom"]["USD"]["lifecycle_distribution"]
        for k, v in ld.items():
            assert isinstance(v, int), f"Expected int for {k}, got {type(v)}"

    def test_g3_ota_collecting_lifecycle_counted(self) -> None:
        """G3: OTA_COLLECTING lifecycle appears in lifecycle_distribution."""
        c = _make_app()
        db = _mock_db([_row()])
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db), \
             patch("api.ota_comparison_router._project_lifecycle_status",
                   return_value="OTA_COLLECTING"):
            resp = c.get("/financial/ota-comparison?period=2026-03")
        ld = resp.json()["providers"]["bookingcom"]["USD"]["lifecycle_distribution"]
        assert ld.get("OTA_COLLECTING", 0) == 1

    def test_g4_counts_sum_to_booking_count(self) -> None:
        """G4: Sum of lifecycle_distribution values == booking_count."""
        rows = [
            _row(booking_id="r1"),
            _row(booking_id="r2"),
        ]
        c = _make_app()
        db = _mock_db(rows)
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2026-03")
        bucket = resp.json()["providers"]["bookingcom"]["USD"]
        ld_sum = sum(bucket["lifecycle_distribution"].values())
        assert ld_sum == bucket["booking_count"]


# ===========================================================================
# Group H — Epistemic tier
# ===========================================================================

class TestGroupH_EpistemicTier:

    def test_h1_full_confidence_yields_A(self) -> None:
        """H1: FULL→tier A."""
        c = _make_app()
        db = _mock_db([_row(source_confidence="FULL")])
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2026-03")
        assert resp.json()["providers"]["bookingcom"]["USD"]["epistemic_tier"] == "A"

    def test_h2_estimated_confidence_yields_B(self) -> None:
        """H2: ESTIMATED→tier B."""
        c = _make_app()
        db = _mock_db([_row(source_confidence="ESTIMATED")])
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2026-03")
        assert resp.json()["providers"]["bookingcom"]["USD"]["epistemic_tier"] == "B"

    def test_h3_partial_confidence_yields_C(self) -> None:
        """H3: PARTIAL→tier C."""
        c = _make_app()
        db = _mock_db([_row(source_confidence="PARTIAL")])
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2026-03")
        assert resp.json()["providers"]["bookingcom"]["USD"]["epistemic_tier"] == "C"

    def test_h4_worst_tier_wins(self) -> None:
        """H4: FULL + PARTIAL → worst tier = C."""
        rows = [
            _row(booking_id="r1", source_confidence="FULL"),
            _row(booking_id="r2", source_confidence="PARTIAL"),
        ]
        c = _make_app()
        db = _mock_db(rows)
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2026-03")
        assert resp.json()["providers"]["bookingcom"]["USD"]["epistemic_tier"] == "C"

    def test_h5_different_otas_have_independent_tiers(self) -> None:
        """H5: Each OTA's tier is computed independently."""
        rows = [
            _row(booking_id="bookingcom_R001", provider="bookingcom",
                 source_confidence="FULL"),
            _row(booking_id="airbnb_R001", provider="airbnb",
                 source_confidence="PARTIAL"),
        ]
        c = _make_app()
        db = _mock_db(rows)
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2026-03")
        providers = resp.json()["providers"]
        assert providers["bookingcom"]["USD"]["epistemic_tier"] == "A"
        assert providers["airbnb"]["USD"]["epistemic_tier"] == "C"


# ===========================================================================
# Group I — Auth guard
# ===========================================================================

class TestGroupI_AuthGuard:

    def test_i1_missing_auth_returns_403(self) -> None:
        """I1: No auth → 403."""
        from fastapi import FastAPI, HTTPException
        from api.ota_comparison_router import router
        from api.auth import jwt_auth

        app = FastAPI()

        async def _reject():
            raise HTTPException(status_code=403, detail="AUTH_FAILED")

        app.dependency_overrides[jwt_auth] = _reject
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/financial/ota-comparison?period=2026-03")
        assert resp.status_code == 403


# ===========================================================================
# Group J — Tenant isolation + INTERNAL_ERROR
# ===========================================================================

class TestGroupJ_TenantIsolation:

    def test_j1_tenant_id_echoed_in_response(self) -> None:
        """J1: tenant_id is echoed correctly."""
        c = _make_app(tenant_id="tenant-alpha")
        db = _mock_db([])
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2026-03")
        assert resp.json()["tenant_id"] == "tenant-alpha"

    def test_j2_supabase_exception_returns_500(self) -> None:
        """J2: DB error → 500 INTERNAL_ERROR."""
        chain = MagicMock()
        chain.execute.side_effect = RuntimeError("DB down")
        chain.eq.return_value = chain
        chain.gte.return_value = chain
        chain.lt.return_value = chain
        chain.order.return_value = chain

        db = MagicMock()
        db.table.return_value.select.return_value = chain

        c = _make_app()
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            resp = c.get("/financial/ota-comparison?period=2026-03")
        assert resp.status_code == 500
        assert resp.json()["code"] == "INTERNAL_ERROR"

    def test_j3_500_does_not_leak_internal_details(self) -> None:
        """J3: 500 body does not contain raw exception text."""
        chain = MagicMock()
        chain.execute.side_effect = RuntimeError("super secret XYZ")
        chain.eq.return_value = chain
        chain.gte.return_value = chain
        chain.lt.return_value = chain
        chain.order.return_value = chain

        db = MagicMock()
        db.table.return_value.select.return_value = chain

        c = _make_app()
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            body = c.get("/financial/ota-comparison?period=2026-03").json()
        assert "super secret" not in str(body)
        assert "XYZ" not in str(body)


# ===========================================================================
# Group K — booking_state never read
# ===========================================================================

class TestGroupK_NeverQueriesBookingState:

    def test_k1_does_not_query_booking_state(self) -> None:
        """K1: Endpoint must not call db.table('booking_state')."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.ota_comparison_router._get_supabase_client", return_value=db):
            c.get("/financial/ota-comparison?period=2026-03")
        calls = [str(c) for c in db.table.call_args_list]
        assert not any("booking_state" in c for c in calls)
