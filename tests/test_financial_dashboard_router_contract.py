"""
Phase 118 — Financial Dashboard API (Ring 2–3) contract tests.

Endpoints under test:
    GET /financial/status/{booking_id}
    GET /financial/revpar?property_id=&period=YYYY-MM
    GET /financial/lifecycle-by-property?period=YYYY-MM

Groups:
    A — /financial/status/{booking_id}
    B — /financial/revpar
    C — /financial/lifecycle-by-property
    D — Epistemic tier logic
    E — Validation (period, property_id)
    F — Auth guard (403 on missing JWT)
    G — Tenant isolation
    H — booking_financial_facts only (booking_state never touched)
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
        "taxes": None,
        "fees": None,
        "net_to_property": net_to_property,
        "source_confidence": source_confidence,
        "event_kind": event_kind,
        "recorded_at": recorded_at,
        "property_id": property_id,
    }


def _mock_db(rows):
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
    from api.financial_dashboard_router import router
    from api.auth import jwt_auth

    app = FastAPI()

    async def _stub_auth():
        return tenant_id

    app.dependency_overrides[jwt_auth] = _stub_auth
    app.include_router(router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Group A — /financial/status/{booking_id}
# ---------------------------------------------------------------------------

class TestFinancialStatus:

    def test_status_returns_200_with_row(self):
        row = _row(source_confidence="FULL")
        db = _mock_db([row])
        client = _make_app(db)

        with patch("api.financial_dashboard_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/status/bookingcom_R001")

        assert resp.status_code == 200
        body = resp.json()
        assert body["booking_id"] == "bookingcom_R001"
        assert body["tenant_id"] == "tenant_test"
        assert body["total_price"] == "300.00"
        assert body["ota_commission"] == "45.00"
        assert body["net_to_property"] == "255.00"
        assert body["currency"] == "USD"
        assert body["source_confidence"] == "FULL"
        assert body["provider"] == "bookingcom"

    def test_status_returns_404_when_no_row(self):
        db = _mock_db([])
        client = _make_app(db)

        with patch("api.financial_dashboard_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/status/unknown_booking")

        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    def test_status_epistemic_tier_full_is_A(self):
        row = _row(source_confidence="FULL")
        db = _mock_db([row])
        client = _make_app(db)

        with patch("api.financial_dashboard_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/status/bookingcom_R001")

        assert resp.json()["epistemic_tier"] == "A"

    def test_status_epistemic_tier_estimated_is_B(self):
        row = _row(source_confidence="ESTIMATED")
        db = _mock_db([row])
        client = _make_app(db)

        with patch("api.financial_dashboard_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/status/bookingcom_R001")

        assert resp.json()["epistemic_tier"] == "B"

    def test_status_epistemic_tier_partial_is_C(self):
        row = _row(source_confidence="PARTIAL")
        db = _mock_db([row])
        client = _make_app(db)

        with patch("api.financial_dashboard_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/status/bookingcom_R001")

        assert resp.json()["epistemic_tier"] == "C"

    def test_status_reason_field_is_present(self):
        row = _row()
        db = _mock_db([row])
        client = _make_app(db)

        with patch("api.financial_dashboard_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/status/bookingcom_R001")

        body = resp.json()
        assert "reason" in body
        assert isinstance(body["reason"], str)
        assert len(body["reason"]) > 0

    def test_status_lifecycle_status_is_string(self):
        row = _row(source_confidence="FULL")
        db = _mock_db([row])
        client = _make_app(db)

        with patch("api.financial_dashboard_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/status/bookingcom_R001")

        body = resp.json()
        assert "lifecycle_status" in body
        assert isinstance(body["lifecycle_status"], str)

    def test_status_canceled_booking_lifecycle_status_is_string(self):
        """BOOKING_CANCELED → lifecycle_status is a valid string.
        RECONCILIATION_PENDING if payment_lifecycle import available,
        else UNKNOWN (graceful fallback)."""
        row = _row(event_kind="BOOKING_CANCELED", source_confidence="FULL")
        db = _mock_db([row])
        client = _make_app(db)

        with patch("api.financial_dashboard_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/status/bookingcom_R001")

        body = resp.json()
        assert body["lifecycle_status"] in (
            "RECONCILIATION_PENDING", "UNKNOWN"
        ), f"Unexpected lifecycle_status: {body['lifecycle_status']}"

    def test_status_null_monetary_fields_are_null_in_response(self):
        row = _row(total_price=None, ota_commission=None, net_to_property=None)
        db = _mock_db([row])
        client = _make_app(db)

        with patch("api.financial_dashboard_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/status/bookingcom_R001")

        body = resp.json()
        assert body["total_price"] is None
        assert body["ota_commission"] is None
        assert body["net_to_property"] is None

    def test_status_db_error_returns_500(self):
        chain = MagicMock()
        chain.execute.side_effect = RuntimeError("DB down")
        chain.eq.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = chain
        db = MagicMock()
        db.table.return_value.select.return_value = chain
        client = _make_app(db)

        with patch("api.financial_dashboard_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/status/bookingcom_R001")

        assert resp.status_code == 500
        assert resp.json()["code"] == "INTERNAL_ERROR"


# ---------------------------------------------------------------------------
# Group B — /financial/revpar
# ---------------------------------------------------------------------------

class TestRevpar:

    def test_revpar_returns_200_with_rows(self):
        rows = [
            _row(property_id="villa_001", net_to_property="5000.00", currency="THB"),
            _row(booking_id="agoda_B002", property_id="villa_001",
                 net_to_property="3000.00", currency="THB"),
        ]
        db = _mock_db(rows)
        client = _make_app(db)

        with patch("api.financial_dashboard_router._get_supabase_client", return_value=db):
            resp = client.get(
                "/financial/revpar?property_id=villa_001&period=2026-03&available_room_nights=30"
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["property_id"] == "villa_001"
        assert body["period"] == "2026-03"
        assert body["total_bookings"] == 2
        assert "THB" in body["currencies"]
        thb = body["currencies"]["THB"]
        assert thb["total_net"] == "8000.00"
        # revpar = 8000 / 30
        assert thb["revpar"] is not None
        assert thb["available_room_nights"] == 30

    def test_revpar_without_available_room_nights_returns_none_revpar(self):
        rows = [_row(property_id="villa_001", net_to_property="5000.00", currency="USD")]
        db = _mock_db(rows)
        client = _make_app(db)

        with patch("api.financial_dashboard_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/revpar?property_id=villa_001&period=2026-03")

        assert resp.status_code == 200
        body = resp.json()
        assert body["currencies"]["USD"]["revpar"] is None
        assert body["currencies"]["USD"]["total_net"] == "5000.00"

    def test_revpar_empty_period_returns_empty_currencies(self):
        db = _mock_db([])
        client = _make_app(db)

        with patch("api.financial_dashboard_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/revpar?property_id=villa_001&period=2026-01")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total_bookings"] == 0
        assert body["currencies"] == {}

    def test_revpar_missing_property_id_returns_400(self):
        db = _mock_db([])
        client = _make_app(db)

        with patch("api.financial_dashboard_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/revpar?period=2026-03")

        assert resp.status_code == 400

    def test_revpar_missing_period_returns_400(self):
        db = _mock_db([])
        client = _make_app(db)

        with patch("api.financial_dashboard_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/revpar?property_id=villa_001")

        assert resp.status_code == 400

    def test_revpar_epistemic_tier_full_is_A(self):
        rows = [_row(property_id="p1", source_confidence="FULL",
                     net_to_property="1000.00", currency="USD")]
        db = _mock_db(rows)
        client = _make_app(db)

        with patch("api.financial_dashboard_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/revpar?property_id=p1&period=2026-03")

        body = resp.json()
        assert body["currencies"]["USD"]["epistemic_tier"] == "A"
        assert body["overall_epistemic_tier"] == "A"

    def test_revpar_mixed_confidence_worst_tier_wins(self):
        """FULL + PARTIAL → overall = C."""
        rows = [
            _row(booking_id="b1", property_id="p1", source_confidence="FULL",
                 net_to_property="1000.00", currency="USD"),
            _row(booking_id="b2", property_id="p1", source_confidence="PARTIAL",
                 net_to_property="500.00", currency="USD"),
        ]
        db = _mock_db(rows)
        client = _make_app(db)

        with patch("api.financial_dashboard_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/revpar?property_id=p1&period=2026-03")

        body = resp.json()
        assert body["currencies"]["USD"]["epistemic_tier"] == "C"
        assert body["overall_epistemic_tier"] == "C"

    def test_revpar_does_not_query_booking_state(self):
        db = _mock_db([])
        client = _make_app(db)

        with patch("api.financial_dashboard_router._get_supabase_client", return_value=db):
            client.get("/financial/revpar?property_id=p1&period=2026-03")

        calls = [str(c) for c in db.table.call_args_list]
        assert not any("booking_state" in c for c in calls)


# ---------------------------------------------------------------------------
# Group C — /financial/lifecycle-by-property
# ---------------------------------------------------------------------------

class TestLifecycleByProperty:

    def test_lifecycle_by_property_returns_200(self):
        rows = [
            _row(booking_id="b1", property_id="prop_A", event_kind="BOOKING_CREATED",
                 source_confidence="FULL"),
            _row(booking_id="b2", property_id="prop_A", event_kind="BOOKING_CANCELED",
                 source_confidence="FULL"),
            _row(booking_id="b3", property_id="prop_B", event_kind="BOOKING_CREATED",
                 source_confidence="PARTIAL", net_to_property=None, total_price=None),
        ]
        db = _mock_db(rows)
        client = _make_app(db)

        with patch("api.financial_dashboard_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/lifecycle-by-property?period=2026-03")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total_bookings"] == 3
        assert "prop_A" in body["properties"]
        assert "prop_B" in body["properties"]

    def test_lifecycle_by_property_missing_property_grouped_as_unknown(self):
        row = _row(booking_id="b1")
        row["property_id"] = None
        db = _mock_db([row])
        client = _make_app(db)

        with patch("api.financial_dashboard_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/lifecycle-by-property?period=2026-03")

        body = resp.json()
        assert "unknown" in body["properties"]

    def test_lifecycle_by_property_empty_returns_empty_properties(self):
        db = _mock_db([])
        client = _make_app(db)

        with patch("api.financial_dashboard_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/lifecycle-by-property?period=2026-03")

        assert resp.status_code == 200
        body = resp.json()
        assert body["properties"] == {}
        assert body["total_bookings"] == 0

    def test_lifecycle_by_property_missing_period_returns_400(self):
        db = _mock_db([])
        client = _make_app(db)

        with patch("api.financial_dashboard_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/lifecycle-by-property")

        assert resp.status_code == 400
        assert resp.json()["code"] == "INVALID_PERIOD"

    def test_lifecycle_by_property_distribution_values_are_ints(self):
        rows = [
            _row(booking_id="b1", property_id="p1", event_kind="BOOKING_CREATED"),
            _row(booking_id="b2", property_id="p1", event_kind="BOOKING_CANCELED"),
        ]
        db = _mock_db(rows)
        client = _make_app(db)

        with patch("api.financial_dashboard_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/lifecycle-by-property?period=2026-03")

        body = resp.json()
        for status, count in body["properties"]["p1"].items():
            assert isinstance(count, int), f"count for {status} should be int"


# ---------------------------------------------------------------------------
# Group D — Epistemic tier logic
# ---------------------------------------------------------------------------

class TestEpistemicTier:

    def test_tier_helper_full(self):
        from api.financial_dashboard_router import _tier
        assert _tier("FULL") == "A"

    def test_tier_helper_estimated(self):
        from api.financial_dashboard_router import _tier
        assert _tier("ESTIMATED") == "B"

    def test_tier_helper_partial(self):
        from api.financial_dashboard_router import _tier
        assert _tier("PARTIAL") == "C"

    def test_tier_helper_unknown_falls_back_to_c(self):
        from api.financial_dashboard_router import _tier
        assert _tier(None) == "C"
        assert _tier("") == "C"
        assert _tier("MYSTERY") == "C"

    def test_worst_tier_all_a(self):
        from api.financial_dashboard_router import _worst_tier
        assert _worst_tier(["A", "A", "A"]) == "A"

    def test_worst_tier_mixed_a_b(self):
        from api.financial_dashboard_router import _worst_tier
        assert _worst_tier(["A", "B", "A"]) == "B"

    def test_worst_tier_mixed_with_c(self):
        from api.financial_dashboard_router import _worst_tier
        assert _worst_tier(["A", "B", "C"]) == "C"

    def test_worst_tier_empty_list_returns_c(self):
        from api.financial_dashboard_router import _worst_tier
        assert _worst_tier([]) == "C"


# ---------------------------------------------------------------------------
# Group E — Validation
# ---------------------------------------------------------------------------

class TestValidation:

    @pytest.mark.parametrize("bad_period", [
        "2026-13", "26-03", "2026/03", "March", "2026-3",
    ])
    def test_bad_period_returns_400(self, bad_period):
        db = _mock_db([])
        client = _make_app(db)

        with patch("api.financial_dashboard_router._get_supabase_client", return_value=db):
            resp = client.get(f"/financial/lifecycle-by-property?period={bad_period}")

        assert resp.status_code == 400
        assert resp.json()["code"] == "INVALID_PERIOD"

    def test_revpar_bad_period_returns_400(self):
        db = _mock_db([])
        client = _make_app(db)

        with patch("api.financial_dashboard_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/revpar?property_id=p1&period=INVALID")

        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Group F — Auth guard
# ---------------------------------------------------------------------------

class TestAuthGuard:

    @pytest.mark.parametrize("endpoint", [
        "/financial/status/some_booking",
        "/financial/revpar?property_id=p1&period=2026-03",
        "/financial/lifecycle-by-property?period=2026-03",
    ])
    def test_missing_auth_returns_403(self, endpoint):
        from fastapi import FastAPI, HTTPException
        from api.financial_dashboard_router import router
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

    def test_status_response_includes_tenant_id(self):
        row = _row(tenant_id="tenant_alpha")
        db = _mock_db([row])
        client = _make_app(db, tenant_id="tenant_alpha")

        with patch("api.financial_dashboard_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/status/bookingcom_R001")

        assert resp.json()["tenant_id"] == "tenant_alpha"

    def test_revpar_response_includes_tenant_id(self):
        db = _mock_db([])
        client = _make_app(db, tenant_id="tenant_beta")

        with patch("api.financial_dashboard_router._get_supabase_client", return_value=db):
            resp = client.get("/financial/revpar?property_id=p1&period=2026-03")

        assert resp.json()["tenant_id"] == "tenant_beta"


# ---------------------------------------------------------------------------
# Group H — booking_state never touched
# ---------------------------------------------------------------------------

class TestNeverQueriesBookingState:

    def test_lifecycle_by_property_never_queries_booking_state(self):
        db = _mock_db([])
        client = _make_app(db)

        with patch("api.financial_dashboard_router._get_supabase_client", return_value=db):
            client.get("/financial/lifecycle-by-property?period=2026-03")

        calls = [str(c) for c in db.table.call_args_list]
        assert not any("booking_state" in c for c in calls)

    def test_revpar_never_queries_booking_state(self):
        db = _mock_db([])
        client = _make_app(db)

        with patch("api.financial_dashboard_router._get_supabase_client", return_value=db):
            client.get("/financial/revpar?property_id=p1&period=2026-03")

        calls = [str(c) for c in db.table.call_args_list]
        assert not any("booking_state" in c for c in calls)
