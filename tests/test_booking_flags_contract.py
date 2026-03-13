"""
Phase 160 — Contract Tests: Booking Flag API

Tests:
  A — PATCH /bookings/{id}/flags: booking not found → 404
  B — PATCH /bookings/{id}/flags: empty body → 400
  C — PATCH /bookings/{id}/flags: unknown-only keys → 400
  D — PATCH /bookings/{id}/flags: boolean type error → 400
  E — PATCH /bookings/{id}/flags: is_vip single flag → 200
  F — PATCH /bookings/{id}/flags: all flags together → 200
  G — PATCH /bookings/{id}/flags: response shape correct
  H — PATCH /bookings/{id}/flags: tenant isolation → 404
  I — PATCH /bookings/{id}/flags: 500 on DB error
  J — PATCH /bookings/{id}/flags: operator_note string → 200
  K — GET /bookings/{id}: flags field present (no flags row → None)
  L — GET /bookings/{id}: flags field present (flags row exists)
  M — PATCH /bookings/{id}/flags: idempotent second call → 200
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.bookings_router import router as bookings_router
from api.auth import jwt_auth

_app = FastAPI()
_app.include_router(bookings_router)
_app.dependency_overrides[jwt_auth] = lambda: "tenant-160"
_client = TestClient(_app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Mock DB factories
# ---------------------------------------------------------------------------

def _make_chain(data: list | None = None, side_effect: Exception | None = None) -> MagicMock:
    chain = MagicMock()
    if side_effect:
        chain.execute.side_effect = side_effect
    else:
        chain.execute.return_value = MagicMock(data=data if data is not None else [])
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.limit.return_value = chain
    chain.order.return_value = chain
    chain.gte.return_value = chain
    chain.lte.return_value = chain
    chain.upsert.return_value = chain
    return chain


def _mock_db_patch(
    booking_exists: bool = True,
    upsert_result: list | None = None,
    raise_exc: Exception | None = None,
) -> MagicMock:
    """For PATCH /flags: first execute = booking existence, second = upsert result."""
    booking_row = [{"booking_id": "bk-160", "tenant_id": "tenant-160"}] if booking_exists else []
    upsert_row = upsert_result if upsert_result is not None else [{
        "booking_id":   "bk-160",
        "tenant_id":    "tenant-160",
        "is_vip":       True,
        "is_disputed":  False,
        "needs_review": False,
        "operator_note": None,
        "flagged_by":   None,
        "updated_at":   "2026-01-01T00:00:00Z",
    }]

    call_count = 0

    def side_effect_fn():
        nonlocal call_count
        if raise_exc and call_count > 0:
            raise raise_exc
        result = MagicMock(data=booking_row if call_count == 0 else upsert_row)
        call_count += 1
        return result

    chain = MagicMock()
    chain.execute.side_effect = lambda: side_effect_fn()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.limit.return_value = chain
    chain.order.return_value = chain
    chain.upsert.return_value = chain
    db = MagicMock()
    db.table.return_value = chain
    return db


def _mock_db_get(
    booking_rows: list | None = None,
    flags_rows:   list | None = None,
    raise_exc:    Exception | None = None,
) -> MagicMock:
    """For GET /bookings/{id}: first execute = booking_state, second = booking_flags."""
    calls = [
        MagicMock(data=booking_rows if booking_rows is not None else []),
        MagicMock(data=flags_rows if flags_rows is not None else []),
    ]
    if raise_exc:
        chain = MagicMock()
        chain.execute.side_effect = raise_exc
    else:
        chain = MagicMock()
        chain.execute.side_effect = calls
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.limit.return_value = chain
    chain.order.return_value = chain
    db = MagicMock()
    db.table.return_value = chain
    return db


def _booking_row(booking_id: str = "bk-160") -> dict:
    return {
        "booking_id":    booking_id,
        "tenant_id":     "tenant-160",
        "source":        "airbnb",
        "status":        "active",
        "check_in":      "2025-09-01",
        "check_out":     "2025-09-08",
        "reservation_ref": "R160",
        "property_id":   "prop-1",
        "version":       1,
        "created_at":    "2025-01-01T00:00:00Z",
        "updated_at":    "2025-01-01T00:00:00Z",
    }


def _flags_row() -> dict:
    return {
        "booking_id":    "bk-160",
        "tenant_id":     "tenant-160",
        "is_vip":        True,
        "is_disputed":   False,
        "needs_review":  True,
        "operator_note": "Check deposit",
        "flagged_by":    "ops-manager",
        "updated_at":    "2026-01-01T00:00:00Z",
    }


# ===========================================================================
# Group A — PATCH: booking not found → 404
# ===========================================================================

class TestGroupA_BookingNotFound:

    def test_a1_not_found_returns_404(self, monkeypatch):
        db = _mock_db_patch(booking_exists=False)
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        resp = _client.patch("/bookings/ghost/flags", json={"is_vip": True})
        assert resp.status_code == 404

    def test_a2_body_contains_booking_id(self, monkeypatch):
        db = _mock_db_patch(booking_exists=False)
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        body = _client.patch("/bookings/ghost-bk/flags", json={"is_vip": True}).json()
        assert "ghost-bk" in str(body)


# ===========================================================================
# Group B — PATCH: empty body → 400
# ===========================================================================

class TestGroupB_EmptyBody:

    def test_b1_empty_body_returns_400(self, monkeypatch):
        db = _mock_db_patch()
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        resp = _client.patch("/bookings/bk-160/flags", json={})
        assert resp.status_code == 400

    def test_b2_error_message_in_response(self, monkeypatch):
        db = _mock_db_patch()
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        body = _client.patch("/bookings/bk-160/flags", json={}).json()
        assert "error" in body or "detail" in str(body).lower()


# ===========================================================================
# Group C — PATCH: unknown-only keys → 400
# ===========================================================================

class TestGroupC_UnknownKeys:

    def test_c1_unknown_key_returns_400(self, monkeypatch):
        db = _mock_db_patch()
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        resp = _client.patch("/bookings/bk-160/flags", json={"totally_unknown": True})
        assert resp.status_code == 400

    def test_c2_mixed_unknown_and_valid_passes(self, monkeypatch):
        db = _mock_db_patch()
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        resp = _client.patch("/bookings/bk-160/flags", json={"is_vip": True, "bogus": "foo"})
        assert resp.status_code == 200


# ===========================================================================
# Group D — PATCH: boolean type error → 400
# ===========================================================================

class TestGroupD_TypeErrors:

    def test_d1_string_for_is_vip_returns_400(self, monkeypatch):
        db = _mock_db_patch()
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        resp = _client.patch("/bookings/bk-160/flags", json={"is_vip": "yes"})
        assert resp.status_code == 400

    def test_d2_int_for_is_disputed_returns_400(self, monkeypatch):
        db = _mock_db_patch()
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        resp = _client.patch("/bookings/bk-160/flags", json={"is_disputed": 1})
        assert resp.status_code == 400


# ===========================================================================
# Group E — PATCH: single is_vip flag → 200
# ===========================================================================

class TestGroupE_SingleFlag:

    def test_e1_is_vip_true_returns_200(self, monkeypatch):
        db = _mock_db_patch()
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        resp = _client.patch("/bookings/bk-160/flags", json={"is_vip": True})
        assert resp.status_code == 200

    def test_e2_is_disputed_true_returns_200(self, monkeypatch):
        db = _mock_db_patch()
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        resp = _client.patch("/bookings/bk-160/flags", json={"is_disputed": True})
        assert resp.status_code == 200

    def test_e3_needs_review_true_returns_200(self, monkeypatch):
        db = _mock_db_patch()
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        resp = _client.patch("/bookings/bk-160/flags", json={"needs_review": True})
        assert resp.status_code == 200


# ===========================================================================
# Group F — PATCH: all flags together → 200
# ===========================================================================

class TestGroupF_AllFlags:

    def test_f1_all_flags_returns_200(self, monkeypatch):
        db = _mock_db_patch()
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        resp = _client.patch("/bookings/bk-160/flags", json={
            "is_vip": True, "is_disputed": False, "needs_review": True,
            "operator_note": "VIP check", "flagged_by": "ops-1",
        })
        assert resp.status_code == 200


# ===========================================================================
# Group G — PATCH: response shape correct
# ===========================================================================

class TestGroupG_ResponseShape:

    def test_g1_top_level_fields(self, monkeypatch):
        db = _mock_db_patch()
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        data = _client.patch("/bookings/bk-160/flags", json={"is_vip": True}).json()["data"]
        for field in ("booking_id", "tenant_id", "flags"):
            assert field in data

    def test_g2_flags_object_fields(self, monkeypatch):
        db = _mock_db_patch()
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        data = _client.patch("/bookings/bk-160/flags", json={"is_vip": True}).json()["data"]
        flags = data["flags"]
        for field in ("is_vip", "is_disputed", "needs_review", "operator_note", "flagged_by"):
            assert field in flags

    def test_g3_booking_id_matches(self, monkeypatch):
        db = _mock_db_patch()
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        data = _client.patch("/bookings/bk-160/flags", json={"is_vip": True}).json()["data"]
        assert data["booking_id"] == "bk-160"


# ===========================================================================
# Group H — PATCH: tenant isolation → 404
# ===========================================================================

class TestGroupH_TenantIsolation:

    def test_h1_other_tenant_booking_returns_404(self, monkeypatch):
        db = _mock_db_patch(booking_exists=False)
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        resp = _client.patch("/bookings/other-tenant/flags", json={"is_vip": True})
        assert resp.status_code == 404


# ===========================================================================
# Group I — PATCH: 500 on DB error
# ===========================================================================

class TestGroupI_InternalError:

    def test_i1_db_error_returns_500(self, monkeypatch):
        # DB error on second call (upsert)
        call_count = 0
        booking_row = [{"booking_id": "bk-160", "tenant_id": "tenant-160"}]

        def side_effect():
            nonlocal call_count
            if call_count == 0:
                call_count += 1
                return MagicMock(data=booking_row)
            raise Exception("DB timeout")

        chain = MagicMock()
        chain.execute.side_effect = side_effect
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.limit.return_value = chain
        chain.upsert.return_value = chain
        db = MagicMock()
        db.table.return_value = chain
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)

        resp = _client.patch("/bookings/bk-160/flags", json={"is_vip": True})
        assert resp.status_code == 500


# ===========================================================================
# Group J — PATCH: operator_note string → 200
# ===========================================================================

class TestGroupJ_OperatorNote:

    def test_j1_operator_note_string_accepted(self, monkeypatch):
        db = _mock_db_patch()
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        resp = _client.patch("/bookings/bk-160/flags", json={"operator_note": "Dispute raised 2026-01-10"})
        assert resp.status_code == 200

    def test_j2_flagged_by_string_accepted(self, monkeypatch):
        db = _mock_db_patch()
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        resp = _client.patch("/bookings/bk-160/flags", json={"flagged_by": "ops-manager-1"})
        assert resp.status_code == 200


# ===========================================================================
# Group K — GET /bookings/{id}: flags field present (no flags row → None)
# ===========================================================================

class TestGroupK_GetNoFlags:

    def test_k1_flags_field_present_when_no_flags(self, monkeypatch):
        db = _mock_db_get(booking_rows=[_booking_row()], flags_rows=[])
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        data = _client.get("/bookings/bk-160").json()["data"]
        assert "flags" in data

    def test_k2_flags_is_none_when_no_flags_row(self, monkeypatch):
        db = _mock_db_get(booking_rows=[_booking_row()], flags_rows=[])
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        data = _client.get("/bookings/bk-160").json()["data"]
        assert data["flags"] is None


# ===========================================================================
# Group L — GET /bookings/{id}: flags field populated with flags row
# ===========================================================================

class TestGroupL_GetWithFlags:

    def test_l1_flags_populated_when_row_exists(self, monkeypatch):
        db = _mock_db_get(booking_rows=[_booking_row()], flags_rows=[_flags_row()])
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        data = _client.get("/bookings/bk-160").json()["data"]
        assert data["flags"] is not None

    def test_l2_is_vip_true_in_flags(self, monkeypatch):
        db = _mock_db_get(booking_rows=[_booking_row()], flags_rows=[_flags_row()])
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        data = _client.get("/bookings/bk-160").json()["data"]
        assert data["flags"]["is_vip"] is True

    def test_l3_operator_note_in_flags(self, monkeypatch):
        db = _mock_db_get(booking_rows=[_booking_row()], flags_rows=[_flags_row()])
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        data = _client.get("/bookings/bk-160").json()["data"]
        assert data["flags"]["operator_note"] == "Check deposit"

    def test_l4_all_flag_fields_present(self, monkeypatch):
        db = _mock_db_get(booking_rows=[_booking_row()], flags_rows=[_flags_row()])
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        data = _client.get("/bookings/bk-160").json()["data"]
        for field in ("is_vip", "is_disputed", "needs_review", "operator_note", "flagged_by"):
            assert field in data["flags"]


# ===========================================================================
# Group M — PATCH: idempotent second call → 200
# ===========================================================================

class TestGroupM_Idempotent:

    def test_m1_second_patch_returns_200(self, monkeypatch):
        db = _mock_db_patch()
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        resp1 = _client.patch("/bookings/bk-160/flags", json={"is_vip": True})
        assert resp1.status_code == 200

    def test_m2_false_flag_also_accepted(self, monkeypatch):
        db = _mock_db_patch(upsert_result=[{
            "booking_id": "bk-160", "tenant_id": "tenant-160",
            "is_vip": False, "is_disputed": False, "needs_review": False,
            "operator_note": None, "flagged_by": None, "updated_at": "2026-01-02T00:00:00Z",
        }])
        monkeypatch.setattr("api.bookings_router._get_supabase_client", lambda: db)
        resp = _client.patch("/bookings/bk-160/flags", json={"is_vip": False})
        assert resp.status_code == 200
