"""
Phase 101 — Owner Statement Router Contract Tests

Uses FastAPI TestClient + mocked Supabase — no live DB required.
Follows the exact same pattern as test_financial_router_contract.py (Phase 67).

Structure:
  Group A — Happy path: 200 response, correct JSON shape
  Group B — Empty result: 404 when no financial records found
  Group C — Auth: 403 response when JWT invalid
  Group D — Validation: 400 when month param missing or malformed
  Group E — Tenant isolation + error codes
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.auth import jwt_auth
from api.owner_statement_router import router


# ---------------------------------------------------------------------------
# Test app factory
# ---------------------------------------------------------------------------

def _make_test_app(mock_tenant_id: str = "tenant_test") -> TestClient:
    """Create a TestClient with owner_statement_router registered and auth stubbed."""
    app = FastAPI()

    async def _stub_auth():
        return mock_tenant_id

    app.dependency_overrides[jwt_auth] = _stub_auth
    app.include_router(router)
    return TestClient(app)


def _reject_auth_app() -> TestClient:
    """Create a TestClient where jwt_auth always raises 403."""
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
    taxes: None = None,
    fees: None = None,
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
        "taxes": taxes,
        "fees": fees,
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
        .ilike.return_value
        .execute.return_value
    ) = MagicMock(data=rows)
    return mock_db


# ---------------------------------------------------------------------------
# Group A — Happy path
# ---------------------------------------------------------------------------

class TestGroupAHappyPath:

    def test_a1_returns_200_with_one_row(self) -> None:
        mock_db = _mock_db_returning([_row()])
        client = _make_test_app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/owner-statement/PROP-001?month=2026-06")
        assert resp.status_code == 200

    def test_a2_response_has_property_id(self) -> None:
        mock_db = _mock_db_returning([_row()])
        client = _make_test_app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=mock_db):
            body = client.get("/owner-statement/PROP-001?month=2026-06").json()
        assert body["property_id"] == "PROP-001"

    def test_a3_response_has_month(self) -> None:
        mock_db = _mock_db_returning([_row()])
        client = _make_test_app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=mock_db):
            body = client.get("/owner-statement/PROP-001?month=2026-06").json()
        assert body["month"] == "2026-06"

    def test_a4_response_has_currency(self) -> None:
        mock_db = _mock_db_returning([_row(currency="EUR")])
        client = _make_test_app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=mock_db):
            body = client.get("/owner-statement/PROP-001?month=2026-06").json()
        assert body["currency"] == "EUR"

    def test_a5_response_has_gross_total(self) -> None:
        mock_db = _mock_db_returning([_row(total_price="1000.00")])
        client = _make_test_app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=mock_db):
            body = client.get("/owner-statement/PROP-001?month=2026-06").json()
        assert body["gross_total"] == "1000.00"

    def test_a6_response_has_net_total(self) -> None:
        mock_db = _mock_db_returning([_row(net_to_property="850.00")])
        client = _make_test_app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=mock_db):
            body = client.get("/owner-statement/PROP-001?month=2026-06").json()
        assert body["net_total"] == "850.00"

    def test_a7_response_has_booking_count(self) -> None:
        mock_db = _mock_db_returning([_row(), _row(booking_id="bookingcom_BK-002")])
        client = _make_test_app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=mock_db):
            body = client.get("/owner-statement/PROP-001?month=2026-06").json()
        assert body["booking_count"] == 2

    def test_a8_response_has_entries_list(self) -> None:
        mock_db = _mock_db_returning([_row()])
        client = _make_test_app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=mock_db):
            body = client.get("/owner-statement/PROP-001?month=2026-06").json()
        assert isinstance(body["entries"], list)
        assert len(body["entries"]) == 1

    def test_a9_entry_has_required_fields(self) -> None:
        mock_db = _mock_db_returning([_row()])
        client = _make_test_app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=mock_db):
            body = client.get("/owner-statement/PROP-001?month=2026-06").json()
        entry = body["entries"][0]
        required = {
            "booking_id", "provider", "currency", "total_price",
            "ota_commission", "net_to_property", "source_confidence",
            "lifecycle_status", "envelope_type", "is_canceled",
        }
        assert required.issubset(set(entry.keys()))

    def test_a10_response_has_statement_confidence(self) -> None:
        mock_db = _mock_db_returning([_row(source_confidence="FULL")])
        client = _make_test_app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=mock_db):
            body = client.get("/owner-statement/PROP-001?month=2026-06").json()
        assert body["statement_confidence"] == "VERIFIED"

    def test_a11_response_has_confidence_breakdown(self) -> None:
        mock_db = _mock_db_returning([_row(source_confidence="FULL")])
        client = _make_test_app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=mock_db):
            body = client.get("/owner-statement/PROP-001?month=2026-06").json()
        assert "FULL" in body["confidence_breakdown"]
        assert body["confidence_breakdown"]["FULL"] == 1

    def test_a12_canceled_row_gives_zero_net(self) -> None:
        mock_db = _mock_db_returning([_row(event_kind="BOOKING_CANCELED")])
        client = _make_test_app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=mock_db):
            body = client.get("/owner-statement/PROP-001?month=2026-06").json()
        assert body["canceled_booking_count"] == 1
        assert body["net_total"] is None  # canceled excluded from totals

    def test_a13_active_and_canceled_counts(self) -> None:
        mock_db = _mock_db_returning([
            _row(booking_id="bk_001", event_kind="BOOKING_CREATED"),
            _row(booking_id="bk_002", event_kind="BOOKING_CANCELED"),
        ])
        client = _make_test_app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=mock_db):
            body = client.get("/owner-statement/PROP-001?month=2026-06").json()
        assert body["active_booking_count"] == 1
        assert body["canceled_booking_count"] == 1


# ---------------------------------------------------------------------------
# Group B — Empty result: 404
# ---------------------------------------------------------------------------

class TestGroupBEmptyResult:

    def test_b1_no_rows_returns_404(self) -> None:
        mock_db = _mock_db_returning([])
        client = _make_test_app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/owner-statement/PROP-001?month=2026-06")
        assert resp.status_code == 404

    def test_b2_404_has_correct_code(self) -> None:
        mock_db = _mock_db_returning([])
        client = _make_test_app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=mock_db):
            body = client.get("/owner-statement/PROP-001?month=2026-06").json()
        assert body["code"] == "PROPERTY_NOT_FOUND"

    def test_b3_404_includes_property_id(self) -> None:
        mock_db = _mock_db_returning([])
        client = _make_test_app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=mock_db):
            body = client.get("/owner-statement/PROP-XYZ?month=2026-06").json()
        assert body["property_id"] == "PROP-XYZ"

    def test_b4_404_includes_month(self) -> None:
        mock_db = _mock_db_returning([])
        client = _make_test_app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=mock_db):
            body = client.get("/owner-statement/PROP-001?month=2026-09").json()
        assert body["month"] == "2026-09"


# ---------------------------------------------------------------------------
# Group C — Auth
# ---------------------------------------------------------------------------

class TestGroupCAuth:

    def test_c1_no_auth_returns_403(self) -> None:
        client = _reject_auth_app()
        resp = client.get("/owner-statement/PROP-001?month=2026-06")
        assert resp.status_code == 403

    def test_c2_valid_auth_passes(self) -> None:
        mock_db = _mock_db_returning([_row()])
        client = _make_test_app(mock_tenant_id="valid_tenant")
        with patch("api.owner_statement_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/owner-statement/PROP-001?month=2026-06")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Group D — Validation: month param
# ---------------------------------------------------------------------------

class TestGroupDValidation:

    def test_d1_missing_month_returns_400(self) -> None:
        client = _make_test_app()
        resp = client.get("/owner-statement/PROP-001")
        assert resp.status_code == 400

    def test_d2_missing_month_code_is_invalid_month(self) -> None:
        client = _make_test_app()
        body = client.get("/owner-statement/PROP-001").json()
        assert body["code"] == "INVALID_MONTH"

    def test_d3_malformed_month_returns_400(self) -> None:
        client = _make_test_app()
        resp = client.get("/owner-statement/PROP-001?month=June-2026")
        assert resp.status_code == 400

    def test_d4_partial_month_returns_400(self) -> None:
        client = _make_test_app()
        resp = client.get("/owner-statement/PROP-001?month=2026")
        assert resp.status_code == 400

    def test_d5_valid_month_format_passes_validation(self) -> None:
        mock_db = _mock_db_returning([_row()])
        client = _make_test_app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/owner-statement/PROP-001?month=2026-12")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Group E — Tenant isolation + error codes
# ---------------------------------------------------------------------------

class TestGroupEIsolationAndErrors:

    def test_e1_tenant_isolation_filters_rows(self) -> None:
        """Supabase query is always filtered by tenant_id. Empty result → 404."""
        mock_db = _mock_db_returning([])  # filtered out
        client = _make_test_app(mock_tenant_id="attacker_tenant")
        with patch("api.owner_statement_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/owner-statement/VICTIM-PROP?month=2026-06")
        assert resp.status_code == 404

    def test_e2_supabase_exception_returns_500(self) -> None:
        mock_db = MagicMock()
        (
            mock_db.table.return_value
            .select.return_value
            .eq.return_value
            .ilike.return_value
            .execute.side_effect
        ) = RuntimeError("DB down")
        client = _make_test_app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/owner-statement/PROP-001?month=2026-06")
        assert resp.status_code == 500

    def test_e3_500_code_is_internal_error(self) -> None:
        mock_db = MagicMock()
        (
            mock_db.table.return_value
            .select.return_value
            .eq.return_value
            .ilike.return_value
            .execute.side_effect
        ) = RuntimeError("connection timeout")
        client = _make_test_app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=mock_db):
            body = client.get("/owner-statement/PROP-001?month=2026-06").json()
        assert body["code"] == "INTERNAL_ERROR"

    def test_e4_500_does_not_leak_internal_details(self) -> None:
        mock_db = MagicMock()
        (
            mock_db.table.return_value
            .select.return_value
            .eq.return_value
            .ilike.return_value
            .execute.side_effect
        ) = RuntimeError("super secret internal error XYZ")
        client = _make_test_app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=mock_db):
            body = client.get("/owner-statement/PROP-001?month=2026-06").json()
        assert "super secret" not in str(body)
        assert "XYZ" not in str(body)
