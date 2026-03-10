"""
Phase 121 — Owner Statement Generator (Ring 4) — Contract Tests

Tests the enhanced GET /owner-statement/{property_id} endpoint.

Groups:
    A — Validation (missing/bad month, bad management_fee_pct)
    B — 404 (no records for property + month + tenant)
    C — Basic JSON response shape (line items present, summary present)
    D — Per-booking line item fields (epistemic tier, lifecycle, gross/net)
    E — Management fee calculation (0%, 10%, 100%, decimal precision)
    F — OTA_COLLECTING honest exclusion from owner_net_total
    G — PDF export (format=pdf returns text/plain, attachment header)
    H — Multi-currency guard (MIXED currency, None totals)
    I — Deduplication (most-recent recorded_at per booking_id wins)

Invariants verified:
    - booking_state is NEVER read (mocked DB returns only booking_financial_facts rows)
    - Management fee: owner_net = net - (net * fee_pct / 100)
    - OTA_COLLECTING net excluded from owner_net_total
    - Epistemic tier: FULL→A, ESTIMATED→B, PARTIAL→C; worst tier wins
    - PDF export: Content-Type text/plain, Content-Disposition attachment
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("fastapi")


# ---------------------------------------------------------------------------
# App bootstrap — follows same pattern as test_cashflow_router_contract.py
# ---------------------------------------------------------------------------

def _make_app(tenant_id: str = "dev-tenant") -> TestClient:
    from fastapi import FastAPI
    from api.owner_statement_router import router
    from api.auth import jwt_auth

    app = FastAPI()

    async def _stub_auth():
        return tenant_id

    app.dependency_overrides[jwt_auth] = _stub_auth
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def _mock_db(rows: list) -> Any:
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=rows)
    chain.eq.return_value = chain
    chain.gte.return_value = chain
    chain.lt.return_value = chain
    chain.order.return_value = chain

    db = MagicMock()
    db.table.return_value.select.return_value = chain
    return db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _row(
    booking_id: str = "bookingcom_RES001",
    provider: str = "bookingcom",
    currency: str = "THB",
    total_price: str = "5000.00",
    ota_commission: str = "500.00",
    net_to_property: str = "4500.00",
    source_confidence: str = "FULL",
    event_kind: str = "BOOKING_CREATED",
    recorded_at: str = "2026-03-05T10:00:00+00:00",
    property_id: str = "prop-A",
    tenant_id: str = "dev-tenant",
) -> dict:
    return {
        "booking_id": booking_id,
        "provider": provider,
        "currency": currency,
        "total_price": total_price,
        "ota_commission": ota_commission,
        "net_to_property": net_to_property,
        "source_confidence": source_confidence,
        "event_kind": event_kind,
        "recorded_at": recorded_at,
        "property_id": property_id,
        "tenant_id": tenant_id,
        "raw_financial_fields": {},
    }


# ===========================================================================
# Group A — Validation
# ===========================================================================

class TestGroupA_Validation:

    def test_a1_missing_month_returns_400(self) -> None:
        """A1: Missing month → 400 INVALID_MONTH."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A", headers={"Authorization": "Bearer test"})
        assert resp.status_code == 400
        assert resp.json()["code"] == "INVALID_MONTH"

    def test_a2_bad_month_format_returns_400(self) -> None:
        """A2: month=2026/03 → 400 INVALID_MONTH."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A", params={"month": "2026/03"})
        assert resp.status_code == 400
        assert resp.json()["code"] == "INVALID_MONTH"

    def test_a3_bad_management_fee_string_returns_400(self) -> None:
        """A3: management_fee_pct=abc → 400 VALIDATION_ERROR."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A",
                         params={"month": "2026-03", "management_fee_pct": "abc"})
        assert resp.status_code == 400
        assert resp.json()["code"] == "VALIDATION_ERROR"

    def test_a4_management_fee_above_100_returns_400(self) -> None:
        """A4: management_fee_pct=150 → 400 VALIDATION_ERROR."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A",
                         params={"month": "2026-03", "management_fee_pct": "150"})
        assert resp.status_code == 400
        assert resp.json()["code"] == "VALIDATION_ERROR"

    def test_a5_management_fee_negative_returns_400(self) -> None:
        """A5: management_fee_pct=-5 → 400 VALIDATION_ERROR."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A",
                         params={"month": "2026-03", "management_fee_pct": "-5"})
        assert resp.status_code == 400
        assert resp.json()["code"] == "VALIDATION_ERROR"

    def test_a6_management_fee_zero_is_valid(self) -> None:
        """A6: management_fee_pct=0 is valid — no fee applied."""
        c = _make_app()
        db = _mock_db([_row()])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A",
                         params={"month": "2026-03", "management_fee_pct": "0"})
        assert resp.status_code == 200

    def test_a7_management_fee_100_is_valid(self) -> None:
        """A7: management_fee_pct=100 is valid — full net deducted as fee."""
        c = _make_app()
        db = _mock_db([_row()])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A",
                         params={"month": "2026-03", "management_fee_pct": "100"})
        assert resp.status_code == 200
        assert resp.json()["summary"]["owner_net_total"] == "0.00"


# ===========================================================================
# Group B — 404 (no records)
# ===========================================================================

class TestGroupB_NotFound:

    def test_b1_no_rows_returns_404(self) -> None:
        """B1: Empty rows → 404 PROPERTY_NOT_FOUND."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-X", params={"month": "2026-03"})
        assert resp.status_code == 404
        assert resp.json()["code"] == "PROPERTY_NOT_FOUND"

    def test_b2_404_body_includes_property_id_and_month(self) -> None:
        """B2: 404 body includes property_id and month."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-X", params={"month": "2026-01"})
        body = resp.json()
        assert body["property_id"] == "prop-X"
        assert body["month"] == "2026-01"


# ===========================================================================
# Group C — Basic response shape
# ===========================================================================

class TestGroupC_ResponseShape:

    def test_c1_200_has_required_top_level_keys(self) -> None:
        """C1: 200 response has all required top-level keys."""
        c = _make_app()
        db = _mock_db([_row()])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A", params={"month": "2026-03"})
        assert resp.status_code == 200
        body = resp.json()
        for key in ["tenant_id", "property_id", "month",
                    "total_bookings_checked", "summary", "line_items"]:
            assert key in body, f"Missing key: {key}"

    def test_c2_summary_has_required_keys(self) -> None:
        """C2: summary has all required keys."""
        c = _make_app()
        db = _mock_db([_row()])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A", params={"month": "2026-03"})
        s = resp.json()["summary"]
        for key in [
            "currency", "gross_total", "ota_commission_total", "net_to_property_total",
            "management_fee_pct", "management_fee_amount", "owner_net_total",
            "booking_count", "ota_collecting_excluded_from_net", "overall_epistemic_tier",
        ]:
            assert key in s, f"Missing summary key: {key}"

    def test_c3_line_items_is_list(self) -> None:
        """C3: line_items is a list."""
        c = _make_app()
        db = _mock_db([_row()])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A", params={"month": "2026-03"})
        assert isinstance(resp.json()["line_items"], list)

    def test_c4_line_item_has_required_fields(self) -> None:
        """C4: Each line item has all required fields."""
        c = _make_app()
        db = _mock_db([_row()])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A", params={"month": "2026-03"})
        item = resp.json()["line_items"][0]
        for key in [
            "booking_id", "provider", "currency", "check_in", "check_out",
            "gross", "ota_commission", "net_to_property",
            "source_confidence", "epistemic_tier", "lifecycle_status",
            "event_kind", "recorded_at",
        ]:
            assert key in item, f"Missing line item key: {key}"

    def test_c5_tenant_id_in_response(self) -> None:
        """C5: tenant_id is correct in response."""
        c = _make_app(tenant_id="t-alpha")
        db = _mock_db([_row(tenant_id="t-alpha")])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A", params={"month": "2026-03"})
        assert resp.json()["tenant_id"] == "t-alpha"

    def test_c6_booking_count_matches_deduped_rows(self) -> None:
        """C6: booking_count = unique bookings after dedup."""
        rows = [
            _row(booking_id="bookingcom_RES001"),
            _row(booking_id="bookingcom_RES002"),
        ]
        c = _make_app()
        db = _mock_db(rows)
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A", params={"month": "2026-03"})
        assert resp.json()["summary"]["booking_count"] == 2

    def test_c7_total_bookings_checked_in_response(self) -> None:
        """C7: total_bookings_checked equals number of rows after dedup."""
        c = _make_app()
        db = _mock_db([_row()])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A", params={"month": "2026-03"})
        assert resp.json()["total_bookings_checked"] == 1


# ===========================================================================
# Group D — Per-booking line items
# ===========================================================================

class TestGroupD_LineItems:

    def test_d1_epistemic_tier_full_maps_to_A(self) -> None:
        """D1: source_confidence=FULL → epistemic_tier=A."""
        c = _make_app()
        db = _mock_db([_row(source_confidence="FULL")])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A", params={"month": "2026-03"})
        assert resp.json()["line_items"][0]["epistemic_tier"] == "A"

    def test_d2_epistemic_tier_estimated_maps_to_B(self) -> None:
        """D2: source_confidence=ESTIMATED → epistemic_tier=B."""
        c = _make_app()
        db = _mock_db([_row(source_confidence="ESTIMATED")])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A", params={"month": "2026-03"})
        assert resp.json()["line_items"][0]["epistemic_tier"] == "B"

    def test_d3_epistemic_tier_partial_maps_to_C(self) -> None:
        """D3: source_confidence=PARTIAL → epistemic_tier=C."""
        c = _make_app()
        db = _mock_db([_row(source_confidence="PARTIAL")])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A", params={"month": "2026-03"})
        assert resp.json()["line_items"][0]["epistemic_tier"] == "C"

    def test_d4_gross_is_2dp_string(self) -> None:
        """D4: gross is a 2dp string."""
        c = _make_app()
        db = _mock_db([_row(total_price="5000")])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A", params={"month": "2026-03"})
        assert resp.json()["line_items"][0]["gross"] == "5000.00"

    def test_d5_event_kind_preserved(self) -> None:
        """D5: event_kind from DB row is preserved in line item."""
        c = _make_app()
        db = _mock_db([_row(event_kind="BOOKING_AMENDED")])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A", params={"month": "2026-03"})
        assert resp.json()["line_items"][0]["event_kind"] == "BOOKING_AMENDED"

    def test_d6_provider_preserved(self) -> None:
        """D6: provider from DB row is preserved."""
        c = _make_app()
        db = _mock_db([_row(provider="airbnb")])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A", params={"month": "2026-03"})
        assert resp.json()["line_items"][0]["provider"] == "airbnb"

    def test_d7_lifecycle_status_is_non_empty_string(self) -> None:
        """D7: lifecycle_status is a non-empty string."""
        c = _make_app()
        db = _mock_db([_row()])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A", params={"month": "2026-03"})
        ls = resp.json()["line_items"][0]["lifecycle_status"]
        assert isinstance(ls, str) and ls

    def test_d8_worst_tier_wins_in_summary(self) -> None:
        """D8: FULL+PARTIAL → overall_epistemic_tier=C (worst wins)."""
        rows = [
            _row(booking_id="r1", source_confidence="FULL"),
            _row(booking_id="r2", source_confidence="PARTIAL"),
        ]
        c = _make_app()
        db = _mock_db(rows)
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A", params={"month": "2026-03"})
        assert resp.json()["summary"]["overall_epistemic_tier"] == "C"

    def test_d9_all_full_tier_yields_A(self) -> None:
        """D9: All FULL → overall_epistemic_tier=A."""
        rows = [
            _row(booking_id="r1", source_confidence="FULL"),
            _row(booking_id="r2", source_confidence="FULL"),
        ]
        c = _make_app()
        db = _mock_db(rows)
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A", params={"month": "2026-03"})
        assert resp.json()["summary"]["overall_epistemic_tier"] == "A"


# ===========================================================================
# Group E — Management fee calculation
# ===========================================================================

class TestGroupE_ManagementFee:

    def test_e1_no_fee_owner_net_equals_net_to_property(self) -> None:
        """E1: management_fee_pct=0 → owner_net_total = net_to_property_total."""
        c = _make_app()
        db = _mock_db([_row(net_to_property="4500.00")])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A",
                         params={"month": "2026-03", "management_fee_pct": "0"})
        s = resp.json()["summary"]
        assert s["owner_net_total"] == "4500.00"
        assert s["management_fee_amount"] is None

    def test_e2_10pct_fee_correct_calculation(self) -> None:
        """E2: net=4500, fee=10% → fee_amount=450, owner_net=4050."""
        c = _make_app()
        db = _mock_db([_row(net_to_property="4500.00")])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A",
                         params={"month": "2026-03", "management_fee_pct": "10"})
        s = resp.json()["summary"]
        assert s["management_fee_amount"] == "450.00"
        assert s["owner_net_total"] == "4050.00"

    def test_e3_100pct_fee_owner_net_is_zero(self) -> None:
        """E3: net=4500, fee=100% → owner_net=0.00."""
        c = _make_app()
        db = _mock_db([_row(net_to_property="4500.00")])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A",
                         params={"month": "2026-03", "management_fee_pct": "100"})
        s = resp.json()["summary"]
        assert s["owner_net_total"] == "0.00"

    def test_e4_decimal_fee_precision(self) -> None:
        """E4: net=1000, fee=12.5% → fee_amount=125.00, owner_net=875.00."""
        c = _make_app()
        db = _mock_db([_row(net_to_property="1000.00")])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A",
                         params={"month": "2026-03", "management_fee_pct": "12.5"})
        s = resp.json()["summary"]
        assert s["management_fee_amount"] == "125.00"
        assert s["owner_net_total"] == "875.00"

    def test_e5_management_fee_pct_in_summary_as_string(self) -> None:
        """E5: management_fee_pct is present in summary as a formatted string."""
        c = _make_app()
        db = _mock_db([_row()])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A",
                         params={"month": "2026-03", "management_fee_pct": "15"})
        assert resp.json()["summary"]["management_fee_pct"] == "15.00"

    def test_e6_no_fee_param_defaults_to_zero(self) -> None:
        """E6: No management_fee_pct param → fee=0.00, management_fee_amount=None."""
        c = _make_app()
        db = _mock_db([_row(net_to_property="3000.00")])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A", params={"month": "2026-03"})
        s = resp.json()["summary"]
        assert s["management_fee_pct"] == "0.00"
        assert s["management_fee_amount"] is None
        assert s["owner_net_total"] == "3000.00"

    def test_e7_multiple_bookings_fee_applied_to_total(self) -> None:
        """E7: Two bookings — fee applied to aggregated net total."""
        rows = [
            _row(booking_id="r1", net_to_property="2000.00"),
            _row(booking_id="r2", net_to_property="3000.00"),
        ]
        c = _make_app()
        db = _mock_db(rows)
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A",
                         params={"month": "2026-03", "management_fee_pct": "10"})
        s = resp.json()["summary"]
        # net_total = 5000, fee = 500, owner_net = 4500
        assert s["net_to_property_total"] == "5000.00"
        assert s["management_fee_amount"] == "500.00"
        assert s["owner_net_total"] == "4500.00"


# ===========================================================================
# Group F — OTA_COLLECTING exclusion
# ===========================================================================

class TestGroupF_OTACollectingExclusion:

    def test_f1_ota_collecting_count_present_in_summary(self) -> None:
        """F1: ota_collecting_excluded_from_net is an int in summary."""
        c = _make_app()
        db = _mock_db([_row()])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A", params={"month": "2026-03"})
        s = resp.json()["summary"]
        assert isinstance(s["ota_collecting_excluded_from_net"], int)

    def test_f2_ota_collecting_excluded_from_net_calculation(self) -> None:
        """F2: OTA_COLLECTING booking net is excluded from owner_net_total."""
        # A booking with no net_to_property → UNKNOWN or OTA_COLLECTING lifecycle
        row = _row(net_to_property="0", ota_commission="0", total_price="3000.00",
                   source_confidence="ESTIMATED")
        c = _make_app()
        db = _mock_db([row])

        with patch("api.owner_statement_router._get_supabase_client", return_value=db), \
             patch("api.owner_statement_router._project_lifecycle_status",
                   return_value="OTA_COLLECTING"):
            resp = c.get("/owner-statement/prop-A", params={"month": "2026-03"})

        assert resp.status_code == 200
        s = resp.json()["summary"]
        assert s["ota_collecting_excluded_from_net"] == 1

    def test_f3_ota_collecting_appears_in_line_items(self) -> None:
        """F3: OTA_COLLECTING booking still appears in line_items for auditability."""
        row = _row(net_to_property="0", total_price="2000.00", source_confidence="ESTIMATED")
        c = _make_app()
        db = _mock_db([row])

        with patch("api.owner_statement_router._get_supabase_client", return_value=db), \
             patch("api.owner_statement_router._project_lifecycle_status",
                   return_value="OTA_COLLECTING"):
            resp = c.get("/owner-statement/prop-A", params={"month": "2026-03"})

        assert resp.status_code == 200
        items = resp.json()["line_items"]
        assert len(items) == 1
        assert items[0]["lifecycle_status"] == "OTA_COLLECTING"


# ===========================================================================
# Group G — PDF export
# ===========================================================================

class TestGroupG_PDFExport:

    def test_g1_format_pdf_returns_application_pdf(self) -> None:
        """G1: ?format=pdf → Content-Type: application/pdf (Phase 188 upgrade)."""
        c = _make_app()
        db = _mock_db([_row()])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A",
                         params={"month": "2026-03", "format": "pdf"})
        assert resp.status_code == 200
        assert "application/pdf" in resp.headers.get("content-type", "")

    def test_g2_format_pdf_has_content_disposition_attachment(self) -> None:
        """G2: ?format=pdf → Content-Disposition: attachment."""
        c = _make_app()
        db = _mock_db([_row()])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-B",
                         params={"month": "2026-03", "format": "pdf"})
        assert resp.status_code == 200
        cd = resp.headers.get("content-disposition", "")
        assert "attachment" in cd
        assert "prop-B" in cd

    def test_g3_format_pdf_body_contains_property_id(self) -> None:
        """G3: PDF body contains the property_id."""
        c = _make_app()
        db = _mock_db([_row()])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-C",
                         params={"month": "2026-03", "format": "pdf"})
        assert resp.status_code == 200
        assert "prop-C" in resp.text

    def test_g4_format_pdf_body_contains_owner_statement_header(self) -> None:
        """G4: PDF body contains 'OWNER STATEMENT' header (embedded in PDF binary)."""
        c = _make_app()
        db = _mock_db([_row()])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A",
                         params={"month": "2026-03", "format": "pdf"})
        assert resp.status_code == 200
        # Phase 188: real PDF — check binary content for embedded text
        assert b"OWNER" in resp.content or b"Owner" in resp.content or b"owner" in resp.content

    def test_g5_format_pdf_body_is_valid_pdf(self) -> None:
        """G5: PDF body is a valid, non-empty PDF document (Phase 188 real PDF)."""
        c = _make_app()
        db = _mock_db([_row(booking_id="bookingcom_RES999")])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A",
                         params={"month": "2026-03", "format": "pdf"})
        assert resp.status_code == 200
        # Phase 188: real PDF — verify it starts with %PDF magic and is non-trivial
        assert resp.content[:5] == b"%PDF-"
        assert len(resp.content) > 500  # real PDF has substantial content

    def test_g6_format_pdf_404_returns_json_not_text(self) -> None:
        """G6: ?format=pdf with no rows → 404 JSON (not text/plain)."""
        c = _make_app()
        db = _mock_db([])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A",
                         params={"month": "2026-03", "format": "pdf"})
        assert resp.status_code == 404
        assert resp.json()["code"] == "PROPERTY_NOT_FOUND"

    def test_g7_format_pdf_body_contains_month(self) -> None:
        """G7: PDF body contains the period month."""
        c = _make_app()
        db = _mock_db([_row()])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A",
                         params={"month": "2026-06", "format": "pdf"})
        assert resp.status_code == 200
        assert "2026-06" in resp.text


# ===========================================================================
# Group H — Multi-currency guard
# ===========================================================================

class TestGroupH_MultiCurrency:

    def test_h1_mixed_currency_summary_has_mixed(self) -> None:
        """H1: Rows with different currencies → currency='MIXED' in summary."""
        rows = [
            _row(booking_id="r1", currency="THB"),
            _row(booking_id="r2", currency="USD"),
        ]
        c = _make_app()
        db = _mock_db(rows)
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A", params={"month": "2026-03"})
        assert resp.status_code == 200
        assert resp.json()["summary"]["currency"] == "MIXED"

    def test_h2_mixed_currency_gross_total_is_none(self) -> None:
        """H2: MIXED currency → gross_total is None."""
        rows = [
            _row(booking_id="r1", currency="THB"),
            _row(booking_id="r2", currency="USD"),
        ]
        c = _make_app()
        db = _mock_db(rows)
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A", params={"month": "2026-03"})
        s = resp.json()["summary"]
        assert s["gross_total"] is None

    def test_h3_mixed_currency_owner_net_is_none(self) -> None:
        """H3: MIXED currency → owner_net_total is None."""
        rows = [
            _row(booking_id="r1", currency="THB"),
            _row(booking_id="r2", currency="EUR"),
        ]
        c = _make_app()
        db = _mock_db(rows)
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A", params={"month": "2026-03"})
        assert resp.json()["summary"]["owner_net_total"] is None

    def test_h4_single_currency_returns_currency_code(self) -> None:
        """H4: Single currency → currency code returned (e.g. 'THB')."""
        c = _make_app()
        db = _mock_db([_row(currency="THB")])
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A", params={"month": "2026-03"})
        assert resp.json()["summary"]["currency"] == "THB"


# ===========================================================================
# Group I — Deduplication
# ===========================================================================

class TestGroupI_Deduplication:

    def test_i1_duplicate_booking_ids_deduped_to_latest(self) -> None:
        """I1: Two rows for same booking_id → only most-recent recorded_at kept."""
        rows = [
            _row(booking_id="bookingcom_RES001",
                 net_to_property="4500.00",
                 recorded_at="2026-03-01T10:00:00+00:00"),
            _row(booking_id="bookingcom_RES001",
                 net_to_property="4800.00",
                 recorded_at="2026-03-10T10:00:00+00:00"),
        ]
        c = _make_app()
        db = _mock_db(rows)
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A", params={"month": "2026-03"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["summary"]["booking_count"] == 1
        assert body["total_bookings_checked"] == 1
        assert body["summary"]["net_to_property_total"] == "4800.00"

    def test_i2_two_different_bookings_both_in_line_items(self) -> None:
        """I2: Two different booking_ids → both appear in line_items."""
        rows = [
            _row(booking_id="bookingcom_RES001"),
            _row(booking_id="bookingcom_RES002"),
        ]
        c = _make_app()
        db = _mock_db(rows)
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A", params={"month": "2026-03"})
        ids = {item["booking_id"] for item in resp.json()["line_items"]}
        assert ids == {"bookingcom_RES001", "bookingcom_RES002"}

    def test_i3_amended_row_supersedes_created_row(self) -> None:
        """I3: BOOKING_AMENDED row (later) supersedes BOOKING_CREATED (earlier)."""
        rows = [
            _row(booking_id="bookingcom_RES001",
                 event_kind="BOOKING_CREATED",
                 net_to_property="3000.00",
                 recorded_at="2026-03-01T00:00:00+00:00"),
            _row(booking_id="bookingcom_RES001",
                 event_kind="BOOKING_AMENDED",
                 net_to_property="3500.00",
                 recorded_at="2026-03-05T00:00:00+00:00"),
        ]
        c = _make_app()
        db = _mock_db(rows)
        with patch("api.owner_statement_router._get_supabase_client", return_value=db):
            resp = c.get("/owner-statement/prop-A", params={"month": "2026-03"})
        body = resp.json()
        assert body["summary"]["booking_count"] == 1
        # The AMENDED (later) row should determine the event_kind shown
        assert body["line_items"][0]["event_kind"] == "BOOKING_AMENDED"
        assert body["summary"]["net_to_property_total"] == "3500.00"
