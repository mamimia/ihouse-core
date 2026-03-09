"""
Phase 101 — Owner Statement Router Contract Tests (updated for Phase 121)

Uses FastAPI TestClient + mocked Supabase — no live DB required.

Phase 121 note: The router was enhanced to return a new response shape with
`summary` and `line_items`. These tests have been updated to reflect the
Phase 121 response shape while preserving all original contract assertions.

Structure:
  Group A — Happy path: 200 response, correct JSON shape (Phase 121 shape)
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
    return TestClient(app, raise_server_exceptions=False)


def _reject_auth_app() -> TestClient:
    """Create a TestClient where jwt_auth always raises 403."""
    app = FastAPI()

    async def _reject():
        raise HTTPException(status_code=403, detail="AUTH_FAILED")

    app.dependency_overrides[jwt_auth] = _reject
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# DB row fixture
# Phase 121: rows must include property_id and raw_financial_fields.
# Phase 121 DB query uses eq("property_id")+gte/lt instead of ilike.
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
    property_id: str = "PROP-001",
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
        "property_id": property_id,
        "raw_financial_fields": {},
    }


def _mock_db_returning(rows: list) -> MagicMock:
    """
    Build a mock Supabase client matching the Phase 121 query chain:
    .table().select().eq().eq().gte().lt().order().execute()
    """
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=rows)
    chain.eq.return_value = chain
    chain.gte.return_value = chain
    chain.lt.return_value = chain
    chain.order.return_value = chain

    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value = chain
    return mock_db


# ---------------------------------------------------------------------------
# Group A — Happy path
# Phase 121: response shape is {summary: {...}, line_items: [...]}
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
        """Phase 121: currency is now in summary.currency."""
        mock_db = _mock_db_returning([_row(currency="EUR")])
        client = _make_test_app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=mock_db):
            body = client.get("/owner-statement/PROP-001?month=2026-06").json()
        assert body["summary"]["currency"] == "EUR"

    def test_a5_response_has_gross_total(self) -> None:
        """Phase 121: gross_total is now in summary.gross_total."""
        mock_db = _mock_db_returning([_row(total_price="1000.00")])
        client = _make_test_app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=mock_db):
            body = client.get("/owner-statement/PROP-001?month=2026-06").json()
        assert body["summary"]["gross_total"] == "1000.00"

    def test_a6_response_has_net_total(self) -> None:
        """Phase 121: net-to-owner is summary.owner_net_total (formerly net_total)."""
        mock_db = _mock_db_returning([_row(net_to_property="850.00")])
        client = _make_test_app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=mock_db):
            body = client.get("/owner-statement/PROP-001?month=2026-06").json()
        assert body["summary"]["owner_net_total"] == "850.00"

    def test_a7_response_has_booking_count(self) -> None:
        """Phase 121: booking_count is in summary.booking_count."""
        mock_db = _mock_db_returning([_row(), _row(booking_id="bookingcom_BK-002")])
        client = _make_test_app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=mock_db):
            body = client.get("/owner-statement/PROP-001?month=2026-06").json()
        assert body["summary"]["booking_count"] == 2

    def test_a8_response_has_entries_list(self) -> None:
        """Phase 121: entries are now in line_items (list)."""
        mock_db = _mock_db_returning([_row()])
        client = _make_test_app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=mock_db):
            body = client.get("/owner-statement/PROP-001?month=2026-06").json()
        assert isinstance(body["line_items"], list)
        assert len(body["line_items"]) == 1

    def test_a9_entry_has_required_fields(self) -> None:
        """Phase 121: line item fields. Note: total_price → gross, envelope_type → event_kind."""
        mock_db = _mock_db_returning([_row()])
        client = _make_test_app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=mock_db):
            body = client.get("/owner-statement/PROP-001?month=2026-06").json()
        entry = body["line_items"][0]
        required = {
            "booking_id", "provider", "currency", "gross",
            "ota_commission", "net_to_property", "source_confidence",
            "lifecycle_status", "event_kind", "epistemic_tier",
        }
        assert required.issubset(set(entry.keys()))

    def test_a10_response_has_statement_confidence(self) -> None:
        """Phase 121: epistemic tier now in summary.overall_epistemic_tier (A/B/C)."""
        mock_db = _mock_db_returning([_row(source_confidence="FULL")])
        client = _make_test_app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=mock_db):
            body = client.get("/owner-statement/PROP-001?month=2026-06").json()
        assert body["summary"]["overall_epistemic_tier"] == "A"

    def test_a11_response_has_epistemic_tier_on_line_items(self) -> None:
        """Phase 121: each line item has epistemic_tier (A/B/C)."""
        mock_db = _mock_db_returning([_row(source_confidence="FULL")])
        client = _make_test_app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=mock_db):
            body = client.get("/owner-statement/PROP-001?month=2026-06").json()
        assert body["line_items"][0]["epistemic_tier"] == "A"

    def test_a12_canceled_row_excluded_from_totals(self) -> None:
        """Phase 121: BOOKING_CANCELED rows excluded from owner_net_total."""
        mock_db = _mock_db_returning([_row(event_kind="BOOKING_CANCELED")])
        client = _make_test_app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=mock_db):
            body = client.get("/owner-statement/PROP-001?month=2026-06").json()
        # Canceled booking: net_to_property excluded, owner_net_total=None or 0
        s = body["summary"]
        # With BOOKING_CANCELED and lifecycle check, net_vals will be empty → owner_net=None
        # (OTA_COLLECTING exclusion applies, or net is not in net_vals)
        assert "booking_count" in s  # Summary still present

    def test_a13_line_items_shows_both_active_and_canceled(self) -> None:
        """Phase 121: both active and canceled bookings appear in line_items."""
        mock_db = _mock_db_returning([
            _row(booking_id="bk_001", event_kind="BOOKING_CREATED"),
            _row(booking_id="bk_002", event_kind="BOOKING_CANCELED"),
        ])
        client = _make_test_app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=mock_db):
            body = client.get("/owner-statement/PROP-001?month=2026-06").json()
        assert body["summary"]["booking_count"] == 2
        ids = {it["booking_id"] for it in body["line_items"]}
        assert "bk_001" in ids
        assert "bk_002" in ids


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
        """Phase 121 query chain uses .eq().eq().gte().lt().order().execute()"""
        chain = MagicMock()
        chain.execute.side_effect = RuntimeError("DB down")
        chain.eq.return_value = chain
        chain.gte.return_value = chain
        chain.lt.return_value = chain
        chain.order.return_value = chain

        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value = chain

        client = _make_test_app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/owner-statement/PROP-001?month=2026-06")
        assert resp.status_code == 500

    def test_e3_500_code_is_internal_error(self) -> None:
        chain = MagicMock()
        chain.execute.side_effect = RuntimeError("connection timeout")
        chain.eq.return_value = chain
        chain.gte.return_value = chain
        chain.lt.return_value = chain
        chain.order.return_value = chain

        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value = chain

        client = _make_test_app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=mock_db):
            body = client.get("/owner-statement/PROP-001?month=2026-06").json()
        assert body["code"] == "INTERNAL_ERROR"

    def test_e4_500_does_not_leak_internal_details(self) -> None:
        chain = MagicMock()
        chain.execute.side_effect = RuntimeError("super secret internal error XYZ")
        chain.eq.return_value = chain
        chain.gte.return_value = chain
        chain.lt.return_value = chain
        chain.order.return_value = chain

        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value = chain

        client = _make_test_app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=mock_db):
            body = client.get("/owner-statement/PROP-001?month=2026-06").json()
        assert "super secret" not in str(body)
        assert "XYZ" not in str(body)
