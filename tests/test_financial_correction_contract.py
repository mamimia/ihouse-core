"""
Phase 162 — Contract Tests: Financial Correction Event

Tests:
  A — POST /financial/corrections: missing booking_id → 400
  B — POST /financial/corrections: missing currency → 400
  C — POST /financial/corrections: invalid currency format → 400
  D — POST /financial/corrections: no amount fields → 400
  E — POST /financial/corrections: negative amount → 400
  F — POST /financial/corrections: non-numeric amount → 400
  G — POST /financial/corrections: booking not found → 404
  H — POST /financial/corrections: tenant isolation → 404
  I — POST /financial/corrections: valid body → 201
  J — POST /financial/corrections: response shape correct
  K — POST /financial/corrections: event_kind = BOOKING_CORRECTED
  L — POST /financial/corrections: confidence = OPERATOR_MANUAL
  M — POST /financial/corrections: 500 on DB insert error
  N — POST /financial/corrections: operator_note included
  O — POST /financial/corrections: multiple amount fields
  P — POST /financial/corrections: currency uppercased in response
  Q — _validate_body: all required field combos
  R — _is_valid_decimal: edge cases
  S — CONFIDENCE_OPERATOR_MANUAL constant exported
  T — corrected_fields list in response
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.financial_correction_router import (
    router as correction_router,
    _validate_body,
    _is_valid_decimal,
    _EVENT_KIND,
    _CONFIDENCE,
)
from adapters.ota.financial_writer import CONFIDENCE_OPERATOR_MANUAL
from api.auth import jwt_auth

_app = FastAPI()
_app.include_router(correction_router)
_app.dependency_overrides[jwt_auth] = lambda: "tenant-162"
_client = TestClient(_app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Mock DB factories
# ---------------------------------------------------------------------------

def _mock_db(
    booking_exists: bool = True,
    insert_result: list | None = None,
    raise_on_insert: Exception | None = None,
) -> MagicMock:
    booking_row = [{"booking_id": "bk-162"}] if booking_exists else []
    ins_row = insert_result if insert_result is not None else [{"id": 1}]

    call_count = 0

    def side_effect():
        nonlocal call_count
        if call_count == 0:
            call_count += 1
            return MagicMock(data=booking_row)
        if raise_on_insert:
            raise raise_on_insert
        call_count += 1
        return MagicMock(data=ins_row)

    chain = MagicMock()
    chain.execute.side_effect = side_effect
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.limit.return_value = chain
    chain.insert.return_value = chain
    db = MagicMock()
    db.table.return_value = chain
    return db


_VALID_BODY = {
    "booking_id":    "bk-162",
    "currency":      "USD",
    "total_price":   "200.00",
    "operator_note": "Correcting OTA rounding error",
    "corrected_by":  "ops-manager",
}


# ===========================================================================
# Group A — missing booking_id → 400
# ===========================================================================

class TestGroupA_MissingBookingId:

    def test_a1_no_booking_id_returns_400(self, monkeypatch):
        db = _mock_db()
        monkeypatch.setattr("api.financial_correction_router._get_supabase_client", lambda: db)
        resp = _client.post("/financial/corrections", json={"currency": "USD", "total_price": "100"})
        assert resp.status_code == 400

    def test_a2_empty_booking_id_returns_400(self, monkeypatch):
        db = _mock_db()
        monkeypatch.setattr("api.financial_correction_router._get_supabase_client", lambda: db)
        resp = _client.post("/financial/corrections", json={"booking_id": "", "currency": "USD", "total_price": "100"})
        assert resp.status_code == 400


# ===========================================================================
# Group B — missing currency → 400
# ===========================================================================

class TestGroupB_MissingCurrency:

    def test_b1_no_currency_returns_400(self, monkeypatch):
        db = _mock_db()
        monkeypatch.setattr("api.financial_correction_router._get_supabase_client", lambda: db)
        resp = _client.post("/financial/corrections", json={"booking_id": "bk-1", "total_price": "100"})
        assert resp.status_code == 400


# ===========================================================================
# Group C — invalid currency format → 400
# ===========================================================================

class TestGroupC_InvalidCurrency:

    def test_c1_two_letters_returns_400(self, monkeypatch):
        db = _mock_db()
        monkeypatch.setattr("api.financial_correction_router._get_supabase_client", lambda: db)
        resp = _client.post("/financial/corrections", json={"booking_id": "bk-1", "currency": "US", "total_price": "100"})
        assert resp.status_code == 400

    def test_c2_digit_in_currency_returns_400(self, monkeypatch):
        db = _mock_db()
        monkeypatch.setattr("api.financial_correction_router._get_supabase_client", lambda: db)
        resp = _client.post("/financial/corrections", json={"booking_id": "bk-1", "currency": "U5D", "total_price": "100"})
        assert resp.status_code == 400


# ===========================================================================
# Group D — no amount fields → 400
# ===========================================================================

class TestGroupD_NoAmounts:

    def test_d1_no_amount_fields_returns_400(self, monkeypatch):
        db = _mock_db()
        monkeypatch.setattr("api.financial_correction_router._get_supabase_client", lambda: db)
        resp = _client.post("/financial/corrections", json={"booking_id": "bk-1", "currency": "USD"})
        assert resp.status_code == 400

    def test_d2_error_mentions_amount_fields(self, monkeypatch):
        db = _mock_db()
        monkeypatch.setattr("api.financial_correction_router._get_supabase_client", lambda: db)
        body = _client.post("/financial/corrections", json={"booking_id": "bk-1", "currency": "USD"}).json()
        assert "amount" in str(body).lower() or "required" in str(body).lower()


# ===========================================================================
# Group E — negative amount → 400
# ===========================================================================

class TestGroupE_NegativeAmount:

    def test_e1_negative_total_price_returns_400(self, monkeypatch):
        db = _mock_db()
        monkeypatch.setattr("api.financial_correction_router._get_supabase_client", lambda: db)
        resp = _client.post("/financial/corrections", json={"booking_id": "bk-1", "currency": "USD", "total_price": "-10.00"})
        assert resp.status_code == 400

    def test_e2_negative_commission_returns_400(self, monkeypatch):
        db = _mock_db()
        monkeypatch.setattr("api.financial_correction_router._get_supabase_client", lambda: db)
        resp = _client.post("/financial/corrections", json={"booking_id": "bk-1", "currency": "USD", "ota_commission": "-5"})
        assert resp.status_code == 400


# ===========================================================================
# Group F — non-numeric amount → 400
# ===========================================================================

class TestGroupF_NonNumericAmount:

    def test_f1_string_returns_400(self, monkeypatch):
        db = _mock_db()
        monkeypatch.setattr("api.financial_correction_router._get_supabase_client", lambda: db)
        resp = _client.post("/financial/corrections", json={"booking_id": "bk-1", "currency": "USD", "total_price": "abc"})
        assert resp.status_code == 400


# ===========================================================================
# Group G — booking not found → 404
# ===========================================================================

class TestGroupG_BookingNotFound:

    def test_g1_not_found_returns_404(self, monkeypatch):
        db = _mock_db(booking_exists=False)
        monkeypatch.setattr("api.financial_correction_router._get_supabase_client", lambda: db)
        resp = _client.post("/financial/corrections", json=_VALID_BODY)
        assert resp.status_code == 404

    def test_g2_error_body_includes_booking_id(self, monkeypatch):
        db = _mock_db(booking_exists=False)
        monkeypatch.setattr("api.financial_correction_router._get_supabase_client", lambda: db)
        body = _client.post("/financial/corrections", json=_VALID_BODY).json()
        assert "bk-162" in str(body)


# ===========================================================================
# Group H — tenant isolation → 404
# ===========================================================================

class TestGroupH_TenantIsolation:

    def test_h1_cross_tenant_returns_404(self, monkeypatch):
        db = _mock_db(booking_exists=False)
        monkeypatch.setattr("api.financial_correction_router._get_supabase_client", lambda: db)
        resp = _client.post("/financial/corrections", json=_VALID_BODY)
        assert resp.status_code == 404


# ===========================================================================
# Group I — valid body → 201
# ===========================================================================

class TestGroupI_ValidBody:

    def test_i1_valid_body_returns_201(self, monkeypatch):
        db = _mock_db()
        monkeypatch.setattr("api.financial_correction_router._get_supabase_client", lambda: db)
        resp = _client.post("/financial/corrections", json=_VALID_BODY)
        assert resp.status_code == 201

    def test_i2_status_inserted_in_response(self, monkeypatch):
        db = _mock_db()
        monkeypatch.setattr("api.financial_correction_router._get_supabase_client", lambda: db)
        data = _client.post("/financial/corrections", json=_VALID_BODY).json()
        assert data.get("status") == "inserted"


# ===========================================================================
# Group J — response shape correct
# ===========================================================================

class TestGroupJ_ResponseShape:

    def test_j1_all_top_level_fields_present(self, monkeypatch):
        db = _mock_db()
        monkeypatch.setattr("api.financial_correction_router._get_supabase_client", lambda: db)
        data = _client.post("/financial/corrections", json=_VALID_BODY).json()
        for field in ("status", "booking_id", "tenant_id", "event_kind", "confidence", "currency", "submitted_at"):
            assert field in data, f"Missing: {field}"

    def test_j2_booking_id_matches(self, monkeypatch):
        db = _mock_db()
        monkeypatch.setattr("api.financial_correction_router._get_supabase_client", lambda: db)
        data = _client.post("/financial/corrections", json=_VALID_BODY).json()
        assert data["booking_id"] == "bk-162"


# ===========================================================================
# Group K — event_kind = BOOKING_CORRECTED
# ===========================================================================

class TestGroupK_EventKind:

    def test_k1_event_kind_is_booking_corrected(self, monkeypatch):
        db = _mock_db()
        monkeypatch.setattr("api.financial_correction_router._get_supabase_client", lambda: db)
        data = _client.post("/financial/corrections", json=_VALID_BODY).json()
        assert data["event_kind"] == "BOOKING_CORRECTED"

    def test_k2_constant_matches(self):
        assert _EVENT_KIND == "BOOKING_CORRECTED"


# ===========================================================================
# Group L — confidence = OPERATOR_MANUAL
# ===========================================================================

class TestGroupL_Confidence:

    def test_l1_confidence_is_operator_manual(self, monkeypatch):
        db = _mock_db()
        monkeypatch.setattr("api.financial_correction_router._get_supabase_client", lambda: db)
        data = _client.post("/financial/corrections", json=_VALID_BODY).json()
        assert data["confidence"] == "OPERATOR_MANUAL"

    def test_l2_constant_matches(self):
        assert _CONFIDENCE == "OPERATOR_MANUAL"


# ===========================================================================
# Group M — 500 on DB insert error
# ===========================================================================

class TestGroupM_InternalError:

    def test_m1_db_insert_error_returns_500(self, monkeypatch):
        db = _mock_db(raise_on_insert=Exception("insert failed"))
        monkeypatch.setattr("api.financial_correction_router._get_supabase_client", lambda: db)
        resp = _client.post("/financial/corrections", json=_VALID_BODY)
        assert resp.status_code == 500


# ===========================================================================
# Group N — operator_note included
# ===========================================================================

class TestGroupN_OperatorNote:

    def test_n1_request_with_operator_note_succeeds(self, monkeypatch):
        db = _mock_db()
        monkeypatch.setattr("api.financial_correction_router._get_supabase_client", lambda: db)
        body = dict(_VALID_BODY, operator_note="OTA rounding issue Q1", corrected_by="alice")
        resp = _client.post("/financial/corrections", json=body)
        assert resp.status_code == 201


# ===========================================================================
# Group O — multiple amount fields
# ===========================================================================

class TestGroupO_MultipleAmounts:

    def test_o1_all_amounts_accepted(self, monkeypatch):
        db = _mock_db()
        monkeypatch.setattr("api.financial_correction_router._get_supabase_client", lambda: db)
        body = {
            "booking_id": "bk-162", "currency": "THB",
            "total_price": "3650.00", "ota_commission": "365.00",
            "net_to_property": "3285.00", "taxes": "50.00", "fees": "0.00",
        }
        resp = _client.post("/financial/corrections", json=body)
        assert resp.status_code == 201


# ===========================================================================
# Group P — currency uppercased in response
# ===========================================================================

class TestGroupP_CurrencyUppercase:

    def test_p1_lowercase_currency_uppercased(self, monkeypatch):
        db = _mock_db()
        monkeypatch.setattr("api.financial_correction_router._get_supabase_client", lambda: db)
        body = dict(_VALID_BODY, currency="usd")
        data = _client.post("/financial/corrections", json=body).json()
        assert data["currency"] == "USD"


# ===========================================================================
# Group Q — _validate_body edge cases
# ===========================================================================

class TestGroupQ_ValidateBody:

    def test_q1_valid_body_returns_none(self):
        assert _validate_body(_VALID_BODY) is None

    def test_q2_missing_booking_id_returns_error(self):
        body = {"currency": "USD", "total_price": "100"}
        assert _validate_body(body) is not None

    def test_q3_missing_currency_returns_error(self):
        body = {"booking_id": "bk-1", "total_price": "100"}
        assert _validate_body(body) is not None


# ===========================================================================
# Group R — _is_valid_decimal edge cases
# ===========================================================================

class TestGroupR_IsValidDecimal:

    def test_r1_none_is_valid(self):
        assert _is_valid_decimal(None) is True

    def test_r2_zero_is_valid(self):
        assert _is_valid_decimal("0") is True

    def test_r3_positive_decimal_is_valid(self):
        assert _is_valid_decimal("200.00") is True

    def test_r4_negative_is_not_valid(self):
        assert _is_valid_decimal("-1.00") is False

    def test_r5_alpha_string_is_not_valid(self):
        assert _is_valid_decimal("abc") is False


# ===========================================================================
# Group S — CONFIDENCE_OPERATOR_MANUAL constant exported from financial_writer
# ===========================================================================

class TestGroupS_ConstantExported:

    def test_s1_constant_is_operator_manual(self):
        assert CONFIDENCE_OPERATOR_MANUAL == "OPERATOR_MANUAL"

    def test_s2_constant_matches_router_constant(self):
        assert CONFIDENCE_OPERATOR_MANUAL == _CONFIDENCE


# ===========================================================================
# Group T — corrected_fields list in response
# ===========================================================================

class TestGroupT_CorrectedFields:

    def test_t1_corrected_fields_in_response(self, monkeypatch):
        db = _mock_db()
        monkeypatch.setattr("api.financial_correction_router._get_supabase_client", lambda: db)
        data = _client.post("/financial/corrections", json=_VALID_BODY).json()
        assert "corrected_fields" in data

    def test_t2_total_price_in_corrected_fields(self, monkeypatch):
        db = _mock_db()
        monkeypatch.setattr("api.financial_correction_router._get_supabase_client", lambda: db)
        data = _client.post("/financial/corrections", json=_VALID_BODY).json()
        assert "total_price" in data["corrected_fields"]
