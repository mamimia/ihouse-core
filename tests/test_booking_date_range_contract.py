"""
Phase 109 — Booking Date Range Search contract tests.

Extends GET /bookings with:
  ?check_in_from=YYYY-MM-DD   (optional — gte filter on check_in)
  ?check_in_to=YYYY-MM-DD     (optional — lte filter on check_in)

Both params are optional and independent. Either or both can be provided
alongside the existing property_id, status, and limit params.

Uses FastAPI TestClient + mocked Supabase — no live DB required.

Groups:
  A — Date range filter success (from only, to only, both, combined with status)
  B — Validation errors (bad date formats for from and to)
  C — Compound filters (date + property_id, date + status, all four combined)
  D — Edge cases (same from/to, no date params still works, end of month)
  E — 400 error body contract (code + detail field)
  F — Regression: existing Phase 106 filters still work
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Test app builder
# ---------------------------------------------------------------------------

def _make_test_app(mock_db=None, mock_tenant_id="tenant_test"):
    from fastapi import FastAPI
    from api.bookings_router import router
    from api.auth import jwt_auth

    app = FastAPI()

    async def _stub_auth():
        return mock_tenant_id

    app.dependency_overrides[jwt_auth] = _stub_auth
    app.include_router(router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Reusable row fixtures
# ---------------------------------------------------------------------------

def _booking(
    booking_id="bookingcom_R001",
    tenant_id="tenant_test",
    source="bookingcom",
    reservation_ref="R001",
    property_id="prop_001",
    status="active",
    check_in="2026-04-01",
    check_out="2026-04-07",
    version=1,
    created_at="2026-03-09T00:00:00+00:00",
    updated_at="2026-03-09T00:00:00+00:00",
):
    return {
        "booking_id": booking_id,
        "tenant_id": tenant_id,
        "source": source,
        "reservation_ref": reservation_ref,
        "property_id": property_id,
        "status": status,
        "check_in": check_in,
        "check_out": check_out,
        "version": version,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def _mock_db_list(rows):
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=rows)
    chain.eq.return_value = chain
    chain.gte.return_value = chain
    chain.lte.return_value = chain
    chain.or_.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain

    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value = chain
    return mock_db, chain


# ---------------------------------------------------------------------------
# Group A — Date range filter success
# ---------------------------------------------------------------------------

class TestDateRangeSuccess:

    def test_check_in_from_only_returns_200(self):
        rows = [_booking(check_in="2026-04-01"), _booking(booking_id="bookingcom_R002", check_in="2026-05-01")]
        mock_db, _ = _mock_db_list(rows)
        client = _make_test_app(mock_db)

        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/bookings?check_in_from=2026-04-01")

        assert resp.status_code == 200
        body = resp.json()["data"]
        assert "bookings" in body
        assert body["count"] == 2

    def test_check_in_to_only_returns_200(self):
        rows = [_booking(check_in="2026-03-15")]
        mock_db, _ = _mock_db_list(rows)
        client = _make_test_app(mock_db)

        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/bookings?check_in_to=2026-04-30")

        assert resp.status_code == 200
        assert resp.json()["data"]["count"] == 1

    def test_check_in_from_and_to_both_returns_200(self):
        rows = [_booking(check_in="2026-04-05")]
        mock_db, _ = _mock_db_list(rows)
        client = _make_test_app(mock_db)

        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/bookings?check_in_from=2026-04-01&check_in_to=2026-04-30")

        assert resp.status_code == 200
        assert resp.json()["data"]["count"] == 1

    def test_date_range_combined_with_status_returns_200(self):
        rows = [_booking(check_in="2026-04-05", status="active")]
        mock_db, _ = _mock_db_list(rows)
        client = _make_test_app(mock_db)

        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/bookings?check_in_from=2026-04-01&status=active")

        assert resp.status_code == 200
        assert resp.json()["data"]["bookings"][0]["status"] == "active"

    def test_empty_range_result_returns_200_not_404(self):
        mock_db, _ = _mock_db_list([])
        client = _make_test_app(mock_db)

        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/bookings?check_in_from=2030-01-01")

        assert resp.status_code == 200
        assert resp.json()["data"]["count"] == 0
        assert resp.json()["data"]["bookings"] == []


# ---------------------------------------------------------------------------
# Group B — Validation errors
# ---------------------------------------------------------------------------

class TestDateRangeValidation:

    @pytest.mark.parametrize("bad_date", [
        "2026-13-01",   # month 13
        "2026-00-01",   # month 0
        "2026-04-00",   # day 0
        "2026-04-32",   # day 32
        "26-04-01",     # 2-digit year
        "2026/04/01",   # wrong separator
        "April",        # plain text
        "2026-4-1",     # no padding
        "20260401",     # no separator
    ])
    def test_invalid_check_in_from_returns_400(self, bad_date):
        mock_db, _ = _mock_db_list([])
        client = _make_test_app(mock_db)

        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            resp = client.get(f"/bookings?check_in_from={bad_date}")

        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert "check_in_from" in body.get("error", {}).get("message", "")

    @pytest.mark.parametrize("bad_date", [
        "2026-13-01",
        "2026-00-15",
        "26-04-01",
        "2026/04/30",
        "2026-4-30",
    ])
    def test_invalid_check_in_to_returns_400(self, bad_date):
        mock_db, _ = _mock_db_list([])
        client = _make_test_app(mock_db)

        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            resp = client.get(f"/bookings?check_in_to={bad_date}")

        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert "check_in_to" in body.get("error", {}).get("message", "")

    @pytest.mark.parametrize("good_date", [
        "2026-01-01", "2026-12-31", "2026-04-30", "2025-02-28",
    ])
    def test_valid_dates_accepted(self, good_date):
        mock_db, _ = _mock_db_list([])
        client = _make_test_app(mock_db)

        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            resp = client.get(f"/bookings?check_in_from={good_date}")

        assert resp.status_code == 200, f"Expected 200 for date={good_date}"


# ---------------------------------------------------------------------------
# Group C — Compound filters
# ---------------------------------------------------------------------------

class TestCompoundFilters:

    def test_date_plus_property_id(self):
        rows = [_booking(property_id="prop_A", check_in="2026-04-10")]
        mock_db, _ = _mock_db_list(rows)
        client = _make_test_app(mock_db)

        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/bookings?property_id=prop_A&check_in_from=2026-04-01")

        assert resp.status_code == 200
        assert resp.json()["data"]["bookings"][0]["property_id"] == "prop_A"

    def test_all_four_filters_combined(self):
        rows = [_booking(property_id="prop_X", status="active", check_in="2026-04-15")]
        mock_db, _ = _mock_db_list(rows)
        client = _make_test_app(mock_db)

        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            resp = client.get(
                "/bookings?property_id=prop_X&status=active"
                "&check_in_from=2026-04-01&check_in_to=2026-04-30"
            )

        assert resp.status_code == 200
        bk = resp.json()["data"]["bookings"][0]
        assert bk["property_id"] == "prop_X"
        assert bk["status"] == "active"
        assert bk["check_in"] == "2026-04-15"

    def test_date_range_plus_limit(self):
        rows = [_booking(booking_id=f"bookingcom_R{i:03d}") for i in range(3)]
        mock_db, _ = _mock_db_list(rows)
        client = _make_test_app(mock_db)

        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/bookings?check_in_from=2026-04-01&limit=10")

        assert resp.status_code == 200
        assert resp.json()["data"]["limit"] == 10


# ---------------------------------------------------------------------------
# Group D — Edge cases
# ---------------------------------------------------------------------------

class TestDateRangeEdgeCases:

    def test_same_from_and_to_returns_200(self):
        rows = [_booking(check_in="2026-04-15")]
        mock_db, _ = _mock_db_list(rows)
        client = _make_test_app(mock_db)

        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/bookings?check_in_from=2026-04-15&check_in_to=2026-04-15")

        assert resp.status_code == 200

    def test_no_date_params_still_works(self):
        """Phase 106 baseline: no date params returns 200 as before."""
        rows = [_booking()]
        mock_db, _ = _mock_db_list(rows)
        client = _make_test_app(mock_db)

        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/bookings")

        assert resp.status_code == 200

    def test_end_of_month_dates_accepted(self):
        for date in ["2026-01-31", "2026-03-31", "2026-04-30", "2026-11-30"]:
            mock_db, _ = _mock_db_list([])
            client = _make_test_app(mock_db)
            with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
                resp = client.get(f"/bookings?check_in_from={date}")
            assert resp.status_code == 200, f"Expected 200 for date={date}"

    def test_booking_state_not_touched(self):
        """Only booking_state is queried — never event_log."""
        mock_db, _ = _mock_db_list([])
        client = _make_test_app(mock_db)

        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            client.get("/bookings?check_in_from=2026-04-01")

        table_calls = [str(c) for c in mock_db.table.call_args_list]
        assert not any("event_log" in c for c in table_calls)


# ---------------------------------------------------------------------------
# Group E — 400 error body contract
# ---------------------------------------------------------------------------

class TestDateRange400Contract:

    def test_from_error_body_has_code_and_detail(self):
        mock_db, _ = _mock_db_list([])
        client = _make_test_app(mock_db)

        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/bookings?check_in_from=bad-date")

        body = resp.json()
        assert resp.status_code == 400
        assert "code" in body.get("error", {})
        assert "message" in body.get("error", {})
        assert body["error"]["code"] == "VALIDATION_ERROR"

    def test_to_error_body_has_code_and_detail(self):
        mock_db, _ = _mock_db_list([])
        client = _make_test_app(mock_db)

        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/bookings?check_in_to=2026/04/30")

        body = resp.json()
        assert resp.status_code == 400
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert "check_in_to" in body.get("error", {}).get("message", "")


# ---------------------------------------------------------------------------
# Group F — Regression: existing Phase 106 filters still work
# ---------------------------------------------------------------------------

class TestPhase106Regression:

    def test_property_id_filter_still_works(self):
        rows = [_booking(property_id="prop_Z")]
        mock_db, _ = _mock_db_list(rows)
        client = _make_test_app(mock_db)

        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/bookings?property_id=prop_Z")

        assert resp.status_code == 200

    def test_status_filter_still_works(self):
        rows = [_booking(status="canceled")]
        mock_db, _ = _mock_db_list(rows)
        client = _make_test_app(mock_db)

        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/bookings?status=canceled")

        assert resp.status_code == 200
        assert resp.json()["data"]["bookings"][0]["status"] == "canceled"

    def test_invalid_status_still_returns_400(self):
        mock_db, _ = _mock_db_list([])
        client = _make_test_app(mock_db)

        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/bookings?status=unknown_status")

        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_limit_clamping_still_works(self):
        mock_db, _ = _mock_db_list([])
        client = _make_test_app(mock_db)

        with patch("api.bookings_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/bookings?limit=999")

        assert resp.json()["data"]["limit"] == 100
