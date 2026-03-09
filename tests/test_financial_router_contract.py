"""
Phase 67 — financial_router contract tests.
Phase 81 — Updated 404 and 500 assertions to use standardised 'code' field (Phase 75 standard).

Uses FastAPI TestClient + mocked Supabase — no live DB required.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Build a minimal test app with financial_router only
# ---------------------------------------------------------------------------

def _make_test_app(mock_db, mock_tenant_id="tenant_test"):
    """Create a TestClient with financial_router registered and auth stubbed."""
    from fastapi import FastAPI
    from api.financial_router import router

    app = FastAPI()

    # Override jwt_auth to return a fixed tenant_id
    from api.auth import jwt_auth

    async def _stub_auth():
        return mock_tenant_id

    app.dependency_overrides[jwt_auth] = _stub_auth
    app.include_router(router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Reusable row fixture
# ---------------------------------------------------------------------------

def _row(
    booking_id="bookingcom_R001",
    tenant_id="tenant_test",
    provider="bookingcom",
    total_price="300.0000",
    currency="EUR",
    ota_commission="45.0000",
    taxes=None,
    fees=None,
    net_to_property="255.0000",
    source_confidence="FULL",
    event_kind="BOOKING_CREATED",
    recorded_at="2026-03-09T00:00:00+00:00",
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
    }


# ---------------------------------------------------------------------------
# T1 — Valid booking_id → 200 + correct fields
# ---------------------------------------------------------------------------

class TestGetFinancialFacts:

    def test_valid_booking_returns_200(self):
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value \
            .eq.return_value.eq.return_value \
            .order.return_value.limit.return_value \
            .execute.return_value = MagicMock(data=[_row()])

        client = _make_test_app(mock_db)

        with patch("api.financial_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/financial/bookingcom_R001")

        assert resp.status_code == 200
        body = resp.json()
        assert body["booking_id"] == "bookingcom_R001"
        assert body["provider"] == "bookingcom"
        assert body["total_price"] == "300.0000"
        assert body["currency"] == "EUR"
        assert body["ota_commission"] == "45.0000"
        assert body["net_to_property"] == "255.0000"
        assert body["source_confidence"] == "FULL"
        assert body["event_kind"] == "BOOKING_CREATED"
        assert "recorded_at" in body

    # -----------------------------------------------------------------------
    # T2 — Unknown booking_id → 404
    # -----------------------------------------------------------------------

    def test_unknown_booking_returns_404(self):
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value \
            .eq.return_value.eq.return_value \
            .order.return_value.limit.return_value \
            .execute.return_value = MagicMock(data=[])

        client = _make_test_app(mock_db)

        with patch("api.financial_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/financial/bookingcom_UNKNOWN")

        assert resp.status_code == 404
        assert resp.json()["code"] == "BOOKING_NOT_FOUND"
        assert resp.json()["booking_id"] == "bookingcom_UNKNOWN"

    # -----------------------------------------------------------------------
    # T3 — No auth header → 403 (jwt_auth raises)
    # -----------------------------------------------------------------------

    def test_no_auth_returns_403(self):
        """jwt_auth raises an HTTP 403 if token is missing/invalid."""
        from fastapi import FastAPI, HTTPException
        from api.financial_router import router
        from api.auth import jwt_auth

        app = FastAPI()

        async def _reject_auth():
            raise HTTPException(status_code=403, detail="AUTH_FAILED")

        app.dependency_overrides[jwt_auth] = _reject_auth
        app.include_router(router)
        client = TestClient(app)

        resp = client.get("/financial/bookingcom_R001")
        assert resp.status_code == 403

    # -----------------------------------------------------------------------
    # T4 — Tenant isolation: another tenant's booking returns 404
    # -----------------------------------------------------------------------

    def test_tenant_isolation_returns_404(self):
        """
        The Supabase query includes .eq("tenant_id", tenant_id).
        If the booking belongs to another tenant, no rows are returned → 404.
        """
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value \
            .eq.return_value.eq.return_value \
            .order.return_value.limit.return_value \
            .execute.return_value = MagicMock(data=[])  # filtered out by tenant_id

        client = _make_test_app(mock_db, mock_tenant_id="attacker_tenant")

        with patch("api.financial_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/financial/bookingcom_VICTIM_BOOKING")

        assert resp.status_code == 404

    # -----------------------------------------------------------------------
    # T5 — Multiple rows → most recent returned (ORDER BY recorded_at DESC LIMIT 1)
    # -----------------------------------------------------------------------

    def test_most_recent_row_returned(self):
        recent = _row(recorded_at="2026-03-09T12:00:00+00:00", total_price="350.0000")
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value \
            .eq.return_value.eq.return_value \
            .order.return_value.limit.return_value \
            .execute.return_value = MagicMock(data=[recent])

        client = _make_test_app(mock_db)

        with patch("api.financial_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/financial/bookingcom_R001")

        assert resp.status_code == 200
        assert resp.json()["total_price"] == "350.0000"

    # -----------------------------------------------------------------------
    # T6 — Response schema has all required fields
    # -----------------------------------------------------------------------

    def test_response_schema_has_required_fields(self):
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value \
            .eq.return_value.eq.return_value \
            .order.return_value.limit.return_value \
            .execute.return_value = MagicMock(data=[_row()])

        client = _make_test_app(mock_db)

        with patch("api.financial_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/financial/bookingcom_R001")

        body = resp.json()
        required = {
            "booking_id", "tenant_id", "provider",
            "total_price", "currency", "ota_commission",
            "taxes", "fees", "net_to_property",
            "source_confidence", "event_kind", "recorded_at",
        }
        assert required.issubset(set(body.keys()))

    # -----------------------------------------------------------------------
    # T7 — Supabase raises → 500, no internal details leaked
    # -----------------------------------------------------------------------

    def test_supabase_error_returns_500(self):
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value \
            .eq.return_value.eq.return_value \
            .order.return_value.limit.return_value \
            .execute.side_effect = RuntimeError("DB down")

        client = _make_test_app(mock_db)

        with patch("api.financial_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/financial/bookingcom_R001")

        assert resp.status_code == 500
        body = resp.json()
        assert body["code"] == "INTERNAL_ERROR"
        assert "DB down" not in str(body)  # no internal details leaked

    # -----------------------------------------------------------------------
    # T8 — Tenant_id query parameter is correctly passed to Supabase
    # -----------------------------------------------------------------------

    def test_tenant_id_is_queried(self):
        """Verify .eq('tenant_id', ...) is called with the correct tenant_id."""
        mock_chain = MagicMock()
        mock_chain.execute.return_value = MagicMock(data=[_row()])
        mock_db = MagicMock()
        # Track the eq calls
        first_eq = MagicMock()
        second_eq = MagicMock()
        second_eq.order.return_value.limit.return_value.execute.return_value = \
            MagicMock(data=[_row()])
        first_eq.eq.return_value = second_eq
        mock_db.table.return_value.select.return_value.eq.return_value = first_eq

        client = _make_test_app(mock_db, mock_tenant_id="specific_tenant")

        with patch("api.financial_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/financial/bookingcom_R001")

        # The first .eq() call should be on booking_id
        first_call_args = mock_db.table.return_value.select.return_value.eq.call_args
        assert first_call_args[0][0] == "booking_id"
        assert first_call_args[0][1] == "bookingcom_R001"

        # The second .eq() call should be on tenant_id
        second_call_args = first_eq.eq.call_args
        assert second_call_args[0][0] == "tenant_id"
        assert second_call_args[0][1] == "specific_tenant"
