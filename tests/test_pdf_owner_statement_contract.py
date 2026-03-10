"""
Phase 188 — PDF Owner Statement Contract Tests

Verifies that GET /owner-statement/{property_id}?format=pdf returns a real
application/pdf response with the correct headers and non-empty PDF bytes.

Test structure:
  Group F — PDF format contract (9 tests)

All tests use FastAPI TestClient + mocked Supabase — no live DB required.
Test f6 is the only one that calls real reportlab (no mock) to verify %PDF magic bytes.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.auth import jwt_auth
from api.owner_statement_router import router


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def _app() -> TestClient:
    app = FastAPI()

    async def _stub_auth():
        return "tenant_test"

    app.dependency_overrides[jwt_auth] = _stub_auth
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _row(
    booking_id: str = "airbnb_abc001",
    provider: str = "airbnb",
    total_price: str = "15000.00",
    currency: str = "THB",
    ota_commission: str = "1800.00",
    net_to_property: str = "13200.00",
    source_confidence: str = "FULL",
    event_kind: str = "BOOKING_CREATED",
    recorded_at: str = "2026-03-15T10:00:00+00:00",
    property_id: str = "VILLA-001",
) -> dict:
    return {
        "id": 1,
        "booking_id": booking_id,
        "tenant_id": "tenant_test",
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
        "raw_financial_fields": {
            "canonical_check_in": "2026-03-01",
            "canonical_check_out": "2026-03-05",
        },
    }


def _mock_db(rows: list) -> MagicMock:
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=rows)
    chain.eq.return_value = chain
    chain.gte.return_value = chain
    chain.lt.return_value = chain
    chain.order.return_value = chain
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value = chain
    return mock_db


_PDF_URL = "/owner-statement/VILLA-001?month=2026-03&format=pdf"
_PDF_FAKE = b"%PDF-fake-bytes-for-header-tests"


# ---------------------------------------------------------------------------
# Group F — PDF format contract
# ---------------------------------------------------------------------------

class TestGroupFPdfFormat:
    """Phase 188: ?format=pdf must return a real application/pdf response."""

    def test_f1_pdf_format_returns_200(self) -> None:
        """?format=pdf + data present → 200."""
        client = _app()
        with (
            patch("api.owner_statement_router._get_supabase_client", return_value=_mock_db([_row()])),
            patch("api.owner_statement_router.generate_owner_statement_pdf", return_value=_PDF_FAKE),
        ):
            resp = client.get(_PDF_URL)
        assert resp.status_code == 200

    def test_f2_content_type_is_application_pdf(self) -> None:
        """Content-Type header must be application/pdf."""
        client = _app()
        with (
            patch("api.owner_statement_router._get_supabase_client", return_value=_mock_db([_row()])),
            patch("api.owner_statement_router.generate_owner_statement_pdf", return_value=_PDF_FAKE),
        ):
            resp = client.get(_PDF_URL)
        assert "application/pdf" in resp.headers.get("content-type", "")

    def test_f3_content_disposition_is_attachment(self) -> None:
        """Content-Disposition must indicate an attachment download."""
        client = _app()
        with (
            patch("api.owner_statement_router._get_supabase_client", return_value=_mock_db([_row()])),
            patch("api.owner_statement_router.generate_owner_statement_pdf", return_value=_PDF_FAKE),
        ):
            resp = client.get(_PDF_URL)
        disposition = resp.headers.get("content-disposition", "")
        assert "attachment" in disposition

    def test_f4_filename_ends_with_pdf(self) -> None:
        """Content-Disposition filename must end with .pdf."""
        client = _app()
        with (
            patch("api.owner_statement_router._get_supabase_client", return_value=_mock_db([_row()])),
            patch("api.owner_statement_router.generate_owner_statement_pdf", return_value=_PDF_FAKE),
        ):
            resp = client.get(_PDF_URL)
        disposition = resp.headers.get("content-disposition", "")
        assert ".pdf" in disposition

    def test_f5_body_is_non_empty_bytes(self) -> None:
        """Response body must be non-empty bytes."""
        client = _app()
        with (
            patch("api.owner_statement_router._get_supabase_client", return_value=_mock_db([_row()])),
            patch("api.owner_statement_router.generate_owner_statement_pdf", return_value=_PDF_FAKE),
        ):
            resp = client.get(_PDF_URL)
        assert len(resp.content) > 0

    def test_f6_pdf_magic_bytes_real_render(self) -> None:
        """
        Real reportlab render (no mock).
        First 4 bytes must be b'%PDF' — this is the canonical PDF magic number.
        """
        from services.statement_generator import generate_owner_statement_pdf

        summary = {
            "currency": "THB",
            "gross_total": "15000.00",
            "ota_commission_total": "1800.00",
            "net_to_property_total": "13200.00",
            "management_fee_pct": "10.00",
            "management_fee_amount": "1320.00",
            "owner_net_total": "11880.00",
            "booking_count": 1,
            "ota_collecting_excluded_from_net": 0,
            "overall_epistemic_tier": "A",
        }
        line_items = [{
            "booking_id": "airbnb_abc001",
            "provider": "airbnb",
            "currency": "THB",
            "check_in": "2026-03-01",
            "check_out": "2026-03-05",
            "gross": "15000.00",
            "ota_commission": "1800.00",
            "net_to_property": "13200.00",
            "epistemic_tier": "A",
            "lifecycle_status": "PAYOUT_RELEASED",
            "event_kind": "BOOKING_CREATED",
        }]
        pdf_bytes = generate_owner_statement_pdf(
            property_id="VILLA-001",
            month="2026-03",
            tenant_id="tenant_test",
            summary=summary,
            line_items=line_items,
            generated_at="2026-03-10T13:49:00Z",
        )
        assert pdf_bytes[:4] == b"%PDF", f"Expected %PDF magic bytes, got {pdf_bytes[:4]!r}"

    def test_f7_no_format_still_returns_json(self) -> None:
        """Without ?format=pdf, response must be JSON."""
        client = _app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=_mock_db([_row()])):
            resp = client.get("/owner-statement/VILLA-001?month=2026-03")
        assert resp.status_code == 200
        assert "application/json" in resp.headers.get("content-type", "")

    def test_f8_format_json_explicit_returns_json(self) -> None:
        """?format=json must still return JSON (case-insensitive non-pdf value)."""
        client = _app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=_mock_db([_row()])):
            resp = client.get("/owner-statement/VILLA-001?month=2026-03&format=json")
        assert resp.status_code == 200
        assert "application/json" in resp.headers.get("content-type", "")

    def test_f9_pdf_404_when_no_data(self) -> None:
        """?format=pdf with empty DB → 404 JSON error (not a PDF)."""
        client = _app()
        with patch("api.owner_statement_router._get_supabase_client", return_value=_mock_db([])):
            resp = client.get(_PDF_URL)
        assert resp.status_code == 404
        # Must be a JSON error, not a PDF
        body = resp.json()
        assert body.get("code") == "PROPERTY_NOT_FOUND"
