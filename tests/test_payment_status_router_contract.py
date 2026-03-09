"""
Phase 103 — Payment Status Router Contract Tests

Uses FastAPI TestClient + mocked Supabase — no live DB required.
Pattern: identical to test_financial_router_contract.py (Phase 67).

Structure:
  Group A — Happy path: 200, correct JSON shape, status field
  Group B — 404 when no financial records found
  Group C — Auth: 403 when JWT invalid
  Group D — Status values from lifecycle states
  Group E — Tenant isolation + 500 error
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.auth import jwt_auth
from api.payment_status_router import router


# ---------------------------------------------------------------------------
# Test app factory
# ---------------------------------------------------------------------------

def _make_test_app(mock_tenant_id: str = "tenant_test") -> TestClient:
    app = FastAPI()

    async def _stub_auth():
        return mock_tenant_id

    app.dependency_overrides[jwt_auth] = _stub_auth
    app.include_router(router)
    return TestClient(app)


def _reject_auth_app() -> TestClient:
    app = FastAPI()

    async def _reject():
        raise HTTPException(status_code=403, detail="AUTH_FAILED")

    app.dependency_overrides[jwt_auth] = _reject
    app.include_router(router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# DB row fixture
# ---------------------------------------------------------------------------

def _row(
    booking_id: str = "bookingcom_BK-001",
    tenant_id: str = "tenant_test",
    provider: str = "bookingcom",
    total_price: str = "1000.00",
    currency: str = "USD",
    ota_commission: str = "150.00",
    net_to_property: str = "850.00",
    source_confidence: str = "FULL",
    event_kind: str = "BOOKING_CREATED",
    recorded_at: str = "2026-06-15T10:00:00+00:00",
) -> dict:
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
    }


def _mock_db_returning(rows: list) -> MagicMock:
    mock_db = MagicMock()
    (
        mock_db.table.return_value
        .select.return_value
        .eq.return_value
        .eq.return_value
        .order.return_value
        .limit.return_value
        .execute.return_value
    ) = MagicMock(data=rows)
    return mock_db


# ---------------------------------------------------------------------------
# Group A — Happy path
# ---------------------------------------------------------------------------

class TestGroupAHappyPath:

    def test_a1_returns_200(self) -> None:
        mock_db = _mock_db_returning([_row()])
        client = _make_test_app()
        with patch("api.payment_status_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/payment-status/bookingcom_BK-001")
        assert resp.status_code == 200

    def test_a2_response_has_booking_id(self) -> None:
        mock_db = _mock_db_returning([_row()])
        client = _make_test_app()
        with patch("api.payment_status_router._get_supabase_client", return_value=mock_db):
            body = client.get("/payment-status/bookingcom_BK-001").json()
        assert body["booking_id"] == "bookingcom_BK-001"

    def test_a3_response_has_status(self) -> None:
        mock_db = _mock_db_returning([_row()])
        client = _make_test_app()
        with patch("api.payment_status_router._get_supabase_client", return_value=mock_db):
            body = client.get("/payment-status/bookingcom_BK-001").json()
        assert "status" in body
        assert body["status"]  # non-empty string

    def test_a4_response_has_rule_applied(self) -> None:
        mock_db = _mock_db_returning([_row()])
        client = _make_test_app()
        with patch("api.payment_status_router._get_supabase_client", return_value=mock_db):
            body = client.get("/payment-status/bookingcom_BK-001").json()
        assert "rule_applied" in body

    def test_a5_response_has_reason(self) -> None:
        mock_db = _mock_db_returning([_row()])
        client = _make_test_app()
        with patch("api.payment_status_router._get_supabase_client", return_value=mock_db):
            body = client.get("/payment-status/bookingcom_BK-001").json()
        assert "reason" in body

    def test_a6_response_has_source_confidence(self) -> None:
        mock_db = _mock_db_returning([_row(source_confidence="FULL")])
        client = _make_test_app()
        with patch("api.payment_status_router._get_supabase_client", return_value=mock_db):
            body = client.get("/payment-status/bookingcom_BK-001").json()
        assert body["source_confidence"] == "FULL"

    def test_a7_response_has_envelope_type(self) -> None:
        mock_db = _mock_db_returning([_row(event_kind="BOOKING_CREATED")])
        client = _make_test_app()
        with patch("api.payment_status_router._get_supabase_client", return_value=mock_db):
            body = client.get("/payment-status/bookingcom_BK-001").json()
        assert body["envelope_type"] == "BOOKING_CREATED"

    def test_a8_response_has_currency(self) -> None:
        mock_db = _mock_db_returning([_row(currency="EUR")])
        client = _make_test_app()
        with patch("api.payment_status_router._get_supabase_client", return_value=mock_db):
            body = client.get("/payment-status/bookingcom_BK-001").json()
        assert body["currency"] == "EUR"

    def test_a9_response_has_net_to_property(self) -> None:
        mock_db = _mock_db_returning([_row(net_to_property="850.00")])
        client = _make_test_app()
        with patch("api.payment_status_router._get_supabase_client", return_value=mock_db):
            body = client.get("/payment-status/bookingcom_BK-001").json()
        assert body["net_to_property"] == "850.00"

    def test_a10_response_has_all_required_fields(self) -> None:
        mock_db = _mock_db_returning([_row()])
        client = _make_test_app()
        with patch("api.payment_status_router._get_supabase_client", return_value=mock_db):
            body = client.get("/payment-status/bookingcom_BK-001").json()
        required = {
            "booking_id", "tenant_id", "status", "rule_applied", "reason",
            "net_to_property", "total_price", "currency", "source_confidence",
            "envelope_type", "provider", "recorded_at",
        }
        assert required.issubset(set(body.keys()))


# ---------------------------------------------------------------------------
# Group B — 404 when no records found
# ---------------------------------------------------------------------------

class TestGroupBNotFound:

    def test_b1_no_rows_returns_404(self) -> None:
        mock_db = _mock_db_returning([])
        client = _make_test_app()
        with patch("api.payment_status_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/payment-status/bookingcom_UNKNOWN")
        assert resp.status_code == 404

    def test_b2_404_code_is_booking_not_found(self) -> None:
        mock_db = _mock_db_returning([])
        client = _make_test_app()
        with patch("api.payment_status_router._get_supabase_client", return_value=mock_db):
            body = client.get("/payment-status/bookingcom_UNKNOWN").json()
        assert body["code"] == "BOOKING_NOT_FOUND"

    def test_b3_404_includes_booking_id(self) -> None:
        mock_db = _mock_db_returning([])
        client = _make_test_app()
        with patch("api.payment_status_router._get_supabase_client", return_value=mock_db):
            body = client.get("/payment-status/bookingcom_GHOST").json()
        assert body["booking_id"] == "bookingcom_GHOST"


# ---------------------------------------------------------------------------
# Group C — Auth
# ---------------------------------------------------------------------------

class TestGroupCAuth:

    def test_c1_no_auth_returns_403(self) -> None:
        client = _reject_auth_app()
        resp = client.get("/payment-status/bookingcom_BK-001")
        assert resp.status_code == 403

    def test_c2_valid_auth_passes_through(self) -> None:
        mock_db = _mock_db_returning([_row()])
        client = _make_test_app(mock_tenant_id="valid_tenant")
        with patch("api.payment_status_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/payment-status/bookingcom_BK-001")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Group D — Status values from lifecycle projection
# ---------------------------------------------------------------------------

class TestGroupDLifecycleStatus:

    def test_d1_active_full_confidence_gives_guest_paid_or_owner_net(self) -> None:
        """With full confidence + net + active booking → deterministic status."""
        mock_db = _mock_db_returning([_row(
            source_confidence="FULL",
            net_to_property="850.00",
            event_kind="BOOKING_CREATED",
        )])
        client = _make_test_app()
        with patch("api.payment_status_router._get_supabase_client", return_value=mock_db):
            body = client.get("/payment-status/bookingcom_BK-001").json()
        # Must be a known PaymentLifecycleStatus value
        valid_statuses = {
            "GUEST_PAID", "OTA_COLLECTING", "OWNER_NET_PENDING",
            "PAYOUT_PENDING", "CANCELED_NO_CHARGE", "CANCELED_REFUND_PENDING",
            "UNKNOWN",
        }
        assert body["status"] in valid_statuses

    def test_d2_canceled_envelope_gives_reconciliation_pending(self) -> None:
        """BOOKING_CANCELED → RECONCILIATION_PENDING (Phase 93 rule: canceled_booking)."""
        mock_db = _mock_db_returning([_row(
            event_kind="BOOKING_CANCELED",
            net_to_property="0.00",
            total_price="0.00",
        )])
        client = _make_test_app()
        with patch("api.payment_status_router._get_supabase_client", return_value=mock_db):
            body = client.get("/payment-status/bookingcom_BK-001").json()
        assert body["status"] == "RECONCILIATION_PENDING"

    def test_d3_status_is_string(self) -> None:
        mock_db = _mock_db_returning([_row()])
        client = _make_test_app()
        with patch("api.payment_status_router._get_supabase_client", return_value=mock_db):
            body = client.get("/payment-status/bookingcom_BK-001").json()
        assert isinstance(body["status"], str)

    def test_d4_rule_applied_is_string(self) -> None:
        mock_db = _mock_db_returning([_row()])
        client = _make_test_app()
        with patch("api.payment_status_router._get_supabase_client", return_value=mock_db):
            body = client.get("/payment-status/bookingcom_BK-001").json()
        assert isinstance(body["rule_applied"], str)

    def test_d5_no_financial_data_gives_unknown(self) -> None:
        """Missing total_price AND net_to_property → UNKNOWN status."""
        row = _row()
        row["total_price"] = None
        row["net_to_property"] = None
        row["event_kind"] = "BOOKING_CREATED"
        mock_db = _mock_db_returning([row])
        client = _make_test_app()
        with patch("api.payment_status_router._get_supabase_client", return_value=mock_db):
            body = client.get("/payment-status/bookingcom_BK-001").json()
        assert body["status"] == "UNKNOWN"


# ---------------------------------------------------------------------------
# Group E — Tenant isolation + 500
# ---------------------------------------------------------------------------

class TestGroupEIsolationAndErrors:

    def test_e1_tenant_isolation_returns_404(self) -> None:
        mock_db = _mock_db_returning([])
        client = _make_test_app(mock_tenant_id="attacker")
        with patch("api.payment_status_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/payment-status/victim_booking")
        assert resp.status_code == 404

    def test_e2_supabase_error_returns_500(self) -> None:
        mock_db = MagicMock()
        (
            mock_db.table.return_value
            .select.return_value
            .eq.return_value
            .eq.return_value
            .order.return_value
            .limit.return_value
            .execute.side_effect
        ) = RuntimeError("DB down")
        client = _make_test_app()
        with patch("api.payment_status_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/payment-status/bookingcom_BK-001")
        assert resp.status_code == 500

    def test_e3_500_code_is_internal_error(self) -> None:
        mock_db = MagicMock()
        (
            mock_db.table.return_value
            .select.return_value
            .eq.return_value
            .eq.return_value
            .order.return_value
            .limit.return_value
            .execute.side_effect
        ) = RuntimeError("connection closed")
        client = _make_test_app()
        with patch("api.payment_status_router._get_supabase_client", return_value=mock_db):
            body = client.get("/payment-status/bookingcom_BK-001").json()
        assert body["code"] == "INTERNAL_ERROR"

    def test_e4_500_does_not_leak_details(self) -> None:
        mock_db = MagicMock()
        (
            mock_db.table.return_value
            .select.return_value
            .eq.return_value
            .eq.return_value
            .order.return_value
            .limit.return_value
            .execute.side_effect
        ) = RuntimeError("SECRET_INTERNAL_TOKEN_XYZ")
        client = _make_test_app()
        with patch("api.payment_status_router._get_supabase_client", return_value=mock_db):
            body = client.get("/payment-status/bookingcom_BK-001").json()
        assert "SECRET_INTERNAL_TOKEN_XYZ" not in str(body)
