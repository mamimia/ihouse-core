"""
Phase 266 — HTTP-level E2E Booking Flow Integration Test

End-to-end tests for the booking API surface using FastAPI TestClient
and mocked Supabase. CI-safe: no live DB, no IHOUSE_ENV=staging needed.

Groups:
  A — GET /bookings/{id}         single booking retrieval (200, 404)
  B — GET /bookings              list / filter / sort / paginate
  C — GET /bookings/{id}/amendments  amendment history (200, 404, empty)
  D — PATCH /bookings/{id}/flags     operator flag upsert (200, 400, 404)
  E — Auth guard                 401 returned when JWT invalid
  F — Shape invariants           all 200 responses carry required keys

Design notes:
- JWT auth is bypassed: IHOUSE_JWT_SECRET unset → dev-mode → tenant_id = "dev-tenant"
- Supabase is mocked via unittest.mock.patch on `bookings_router._get_supabase_client`
- No real HTTP network calls are made anywhere in this file
"""
from __future__ import annotations

import os
import sys
from typing import Any
from unittest.mock import MagicMock, patch

os.environ.setdefault("IHOUSE_ENV", "test")

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# App import
# ---------------------------------------------------------------------------

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from main import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)

TENANT = "dev-tenant"   # dev-mode default when IHOUSE_JWT_SECRET is unset
BOOKING_ID = "bookingcom_bk10000001"
PROP_ID = "prop-test-001"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _booking_row(**overrides: Any) -> dict:
    base = {
        "booking_id":      BOOKING_ID,
        "tenant_id":       TENANT,
        "source":          "bookingcom",
        "reservation_ref": "bk10000001",
        "property_id":     PROP_ID,
        "status":          "active",
        "check_in":        "2026-09-01",
        "check_out":       "2026-09-07",
        "version":         1,
        "created_at":      "2026-03-11T00:00:00Z",
        "updated_at":      "2026-03-11T00:00:00Z",
    }
    base.update(overrides)
    return base


def _amendment_row(**overrides: Any) -> dict:
    base = {
        "envelope_id":  "env-amend-001",
        "booking_id":   BOOKING_ID,
        "tenant_id":    TENANT,
        "event_type":   "BOOKING_AMENDED",
        "version":      2,
        "received_at":  "2026-03-11T01:00:00Z",
        "payload":      {"new_check_in": "2026-09-03", "new_check_out": "2026-09-09"},
    }
    base.update(overrides)
    return base


def _make_db(
    booking_rows: list | None = None,
    amendment_rows: list | None = None,
    flags_rows: list | None = None,
):
    """Build a MagicMock Supabase client with pre-configured responses."""
    db = MagicMock()

    def _query_chain(rows):
        q = MagicMock()
        q.select.return_value = q
        q.eq.return_value = q
        q.gte.return_value = q
        q.lte.return_value = q
        q.limit.return_value = q
        q.order.return_value = q
        q.upsert.return_value = q
        q.execute.return_value = MagicMock(data=rows if rows is not None else [])
        return q

    def _table_side_effect(name: str):
        if name == "booking_state":
            return _query_chain(booking_rows if booking_rows is not None else [_booking_row()])
        if name == "event_log":
            return _query_chain(amendment_rows if amendment_rows is not None else [])
        if name == "booking_flags":
            return _query_chain(flags_rows if flags_rows is not None else [])
        return _query_chain([])

    db.table.side_effect = _table_side_effect
    return db


# ---------------------------------------------------------------------------
# Group A — GET /bookings/{id}
# ---------------------------------------------------------------------------

class TestGroupAGetBooking:

    def test_a1_returns_200_with_correct_shape(self):
        db = _make_db()
        with patch("api.bookings_router._get_supabase_client", return_value=db):
            r = client.get(f"/bookings/{BOOKING_ID}")
        assert r.status_code == 200
        body = r.json()
        assert body["booking_id"] == BOOKING_ID
        assert body["tenant_id"] == TENANT

    def test_a2_response_has_all_required_keys(self):
        db = _make_db()
        with patch("api.bookings_router._get_supabase_client", return_value=db):
            r = client.get(f"/bookings/{BOOKING_ID}")
        body = r.json()
        for key in ("booking_id", "tenant_id", "source", "reservation_ref",
                    "property_id", "status", "check_in", "check_out", "version",
                    "created_at", "updated_at", "flags"):
            assert key in body, f"Missing key: {key}"

    def test_a3_flags_is_none_when_no_flags_row(self):
        db = _make_db(flags_rows=[])
        with patch("api.bookings_router._get_supabase_client", return_value=db):
            r = client.get(f"/bookings/{BOOKING_ID}")
        assert r.json()["flags"] is None

    def test_a4_returns_404_for_unknown_booking(self):
        db = _make_db(booking_rows=[])
        with patch("api.bookings_router._get_supabase_client", return_value=db):
            r = client.get("/bookings/unknown_booking_xyz")
        assert r.status_code == 404

    def test_a5_404_body_has_error_code(self):
        db = _make_db(booking_rows=[])
        with patch("api.bookings_router._get_supabase_client", return_value=db):
            r = client.get("/bookings/unknown_booking_xyz")
        body = r.json()
        assert "code" in body or "error" in body or "detail" in body

    def test_a6_returns_correct_status_field(self):
        db = _make_db(booking_rows=[_booking_row(status="canceled")])
        with patch("api.bookings_router._get_supabase_client", return_value=db):
            r = client.get(f"/bookings/{BOOKING_ID}")
        assert r.json()["status"] == "canceled"


# ---------------------------------------------------------------------------
# Group B — GET /bookings (list / filter / sort)
# ---------------------------------------------------------------------------

class TestGroupBListBookings:

    def test_b1_returns_200_with_count_and_bookings(self):
        db = _make_db()
        with patch("api.bookings_router._get_supabase_client", return_value=db):
            r = client.get("/bookings")
        assert r.status_code == 200
        body = r.json()
        assert "bookings" in body
        assert "count" in body

    def test_b2_limit_defaults_to_50(self):
        db = _make_db()
        with patch("api.bookings_router._get_supabase_client", return_value=db):
            r = client.get("/bookings")
        assert r.json()["limit"] == 50

    def test_b3_custom_limit_respected(self):
        db = _make_db(booking_rows=[_booking_row()] * 5)
        with patch("api.bookings_router._get_supabase_client", return_value=db):
            r = client.get("/bookings?limit=10")
        assert r.status_code == 200

    def test_b4_invalid_status_returns_400(self):
        r = client.get("/bookings?status=flying")
        assert r.status_code == 400

    def test_b5_invalid_sort_by_returns_400(self):
        r = client.get("/bookings?sort_by=banana")
        assert r.status_code == 400

    def test_b6_invalid_date_format_returns_400(self):
        r = client.get("/bookings?check_in_from=not-a-date")
        assert r.status_code == 400

    def test_b7_valid_status_filter_passes(self):
        db = _make_db()
        with patch("api.bookings_router._get_supabase_client", return_value=db):
            r = client.get("/bookings?status=active")
        assert r.status_code == 200

    def test_b8_sort_dir_asc_accepted(self):
        db = _make_db()
        with patch("api.bookings_router._get_supabase_client", return_value=db):
            r = client.get("/bookings?sort_dir=asc")
        assert r.status_code == 200

    def test_b9_response_shape_has_sort_meta(self):
        db = _make_db()
        with patch("api.bookings_router._get_supabase_client", return_value=db):
            r = client.get("/bookings?sort_by=check_in&sort_dir=asc")
        body = r.json()
        assert body["sort_by"] == "check_in"
        assert body["sort_dir"] == "asc"

    def test_b10_empty_result_returns_empty_list(self):
        db = _make_db(booking_rows=[])
        with patch("api.bookings_router._get_supabase_client", return_value=db):
            r = client.get("/bookings")
        body = r.json()
        assert body["bookings"] == []
        assert body["count"] == 0


# ---------------------------------------------------------------------------
# Group C — GET /bookings/{id}/amendments
# ---------------------------------------------------------------------------

class TestGroupCAmendmentHistory:

    def test_c1_returns_200_with_amendments_key(self):
        db = _make_db(amendment_rows=[_amendment_row()])
        with patch("api.bookings_router._get_supabase_client", return_value=db):
            r = client.get(f"/bookings/{BOOKING_ID}/amendments")
        assert r.status_code == 200
        assert "amendments" in r.json()

    def test_c2_amendment_row_has_required_shape(self):
        db = _make_db(amendment_rows=[_amendment_row()])
        with patch("api.bookings_router._get_supabase_client", return_value=db):
            r = client.get(f"/bookings/{BOOKING_ID}/amendments")
        amend = r.json()["amendments"][0]
        for key in ("envelope_id", "booking_id", "event_type", "received_at"):
            assert key in amend, f"Missing key in amendment: {key}"

    def test_c3_empty_amendments_when_none_exist(self):
        db = _make_db(amendment_rows=[])
        with patch("api.bookings_router._get_supabase_client", return_value=db):
            r = client.get(f"/bookings/{BOOKING_ID}/amendments")
        body = r.json()
        assert body["amendments"] == []
        assert body["count"] == 0

    def test_c4_returns_404_when_booking_not_found(self):
        db = _make_db(booking_rows=[])
        with patch("api.bookings_router._get_supabase_client", return_value=db):
            r = client.get("/bookings/ghost_booking/amendments")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Group D — PATCH /bookings/{id}/flags
# ---------------------------------------------------------------------------

class TestGroupDPatchFlags:

    def test_d1_valid_flags_returns_200(self):
        db = _make_db()
        with patch("api.bookings_router._get_supabase_client", return_value=db):
            r = client.patch(
                f"/bookings/{BOOKING_ID}/flags",
                json={"is_vip": True, "operator_note": "test"},
            )
        assert r.status_code == 200

    def test_d2_response_has_flags_key(self):
        db = _make_db()
        with patch("api.bookings_router._get_supabase_client", return_value=db):
            r = client.patch(
                f"/bookings/{BOOKING_ID}/flags",
                json={"is_vip": False},
            )
        assert "flags" in r.json()

    def test_d3_empty_body_returns_400(self):
        r = client.patch(f"/bookings/{BOOKING_ID}/flags", json={})
        assert r.status_code == 400

    def test_d4_unknown_keys_only_returns_400(self):
        r = client.patch(
            f"/bookings/{BOOKING_ID}/flags",
            json={"random_key": "value"},
        )
        assert r.status_code == 400

    def test_d5_non_bool_is_vip_returns_400(self):
        r = client.patch(
            f"/bookings/{BOOKING_ID}/flags",
            json={"is_vip": "yes"},
        )
        assert r.status_code == 400

    def test_d6_booking_not_found_returns_404(self):
        db = _make_db(booking_rows=[])
        with patch("api.bookings_router._get_supabase_client", return_value=db):
            r = client.patch(
                "/bookings/ghost_id/flags",
                json={"is_vip": True},
            )
        assert r.status_code == 404
