"""
Contract tests — Phase 301: Owner Portal Rich Data Service
===========================================================

Covers:
- owner_portal_data.py: get_property_booking_counts
- owner_portal_data.py: get_property_upcoming_bookings
- owner_portal_data.py: get_property_recent_bookings
- owner_portal_data.py: _enrich_booking_row (nights calculation)
- owner_portal_data.py: get_property_financial_summary
- owner_portal_data.py: get_property_occupancy_rate
- owner_portal_data.py: get_owner_property_rich_summary (owner vs viewer)
- owner_portal_router: GET /owner/portal/{property_id}/summary (Phase 301 upgrade)
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("IHOUSE_JWT_SECRET", "test-secret-hs256-key-ok")
os.environ.setdefault("IHOUSE_GUEST_TOKEN_SECRET", "test-guest-secret-hs256")
os.environ.setdefault("SUPABASE_URL", "http://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _date_offset(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d")


def _make_db_with_bookings(rows: list[dict]) -> MagicMock:
    db = MagicMock()
    chain = db.table.return_value
    for attr in ("select", "eq", "gte", "in_", "order", "limit", "execute"):
        chain = getattr(chain, attr).return_value
    chain.data = rows
    return db


def _make_db_chained(data: list[dict]) -> MagicMock:
    db = MagicMock()
    chain = MagicMock()
    for method in ("select", "eq", "gte", "lte", "in_", "order", "limit", "execute"):
        setattr(chain, method, MagicMock(return_value=chain))
    chain.execute.return_value = MagicMock(data=data)
    db.table.return_value = chain
    return db


# ---------------------------------------------------------------------------
# get_property_booking_counts
# ---------------------------------------------------------------------------

class TestGetPropertyBookingCounts:
    def test_counts_by_status(self):
        from services.owner_portal_data import get_property_booking_counts
        rows = [
            {"status": "confirmed"},
            {"status": "confirmed"},
            {"status": "cancelled"},
            {"status": "checked_in"},
        ]
        db = _make_db_chained(rows)
        result = get_property_booking_counts(db, "prop-1")
        assert result["total"] == 4
        assert result["confirmed"] == 2
        assert result["cancelled"] == 1
        assert result["checked_in"] == 1

    def test_returns_zeros_on_error(self):
        from services.owner_portal_data import get_property_booking_counts
        db = MagicMock()
        db.table.side_effect = Exception("DB error")
        result = get_property_booking_counts(db, "prop-1")
        assert result["total"] == 0

    def test_unknown_status_goes_to_pending(self):
        from services.owner_portal_data import get_property_booking_counts
        rows = [{"status": "some_unknown_status"}]
        db = _make_db_chained(rows)
        result = get_property_booking_counts(db, "prop-1")
        assert result["total"] == 1
        assert result["pending"] >= 1


# ---------------------------------------------------------------------------
# _enrich_booking_row / nights calculation
# ---------------------------------------------------------------------------

class TestEnrichBookingRow:
    def test_nights_calculated(self):
        from services.owner_portal_data import _enrich_booking_row
        row = {
            "booking_ref": "B1",
            "check_in_date": "2026-04-01",
            "check_out_date": "2026-04-05",
            "status": "confirmed",
            "source": "airbnb",
        }
        result = _enrich_booking_row(row)
        assert result["nights"] == 4
        assert result["channel"] == "airbnb"

    def test_bad_dates_returns_none_nights(self):
        from services.owner_portal_data import _enrich_booking_row
        row = {"booking_ref": "B2", "check_in_date": "bad", "check_out_date": None,
               "status": "confirmed", "source": ""}
        result = _enrich_booking_row(row)
        assert result["nights"] is None

    def test_same_day_checkout_zero_nights(self):
        from services.owner_portal_data import _enrich_booking_row
        row = {"booking_ref": "B3", "check_in_date": "2026-04-01",
               "check_out_date": "2026-04-01", "status": "confirmed", "source": ""}
        result = _enrich_booking_row(row)
        assert result["nights"] == 0


# ---------------------------------------------------------------------------
# get_property_upcoming_bookings
# ---------------------------------------------------------------------------

class TestGetPropertyUpcomingBookings:
    def test_returns_enriched_bookings(self):
        from services.owner_portal_data import get_property_upcoming_bookings
        rows = [
            {"booking_ref": "B1", "check_in_date": _date_offset(2),
             "check_out_date": _date_offset(5), "status": "confirmed", "source": "agoda"},
        ]
        db = _make_db_chained(rows)
        result = get_property_upcoming_bookings(db, "prop-1", limit=5)
        assert len(result) == 1
        assert result[0]["nights"] == 3

    def test_returns_empty_on_error(self):
        from services.owner_portal_data import get_property_upcoming_bookings
        db = MagicMock()
        db.table.side_effect = Exception("DB error")
        result = get_property_upcoming_bookings(db, "prop-1")
        assert result == []


# ---------------------------------------------------------------------------
# get_property_financial_summary
# ---------------------------------------------------------------------------

class TestGetPropertyFinancialSummary:
    def test_aggregates_revenue(self):
        from services.owner_portal_data import get_property_financial_summary
        import services.owner_portal_data as mod

        # Two calls: first returns booking_ids, second returns facts
        booking_rows = [{"booking_id": "b1"}, {"booking_id": "b2"}]
        fact_rows = [
            {"booking_id": "b1", "gross_revenue": 1000, "net_to_property": 850,
             "management_fee": 100, "ota_commission": 50},
            {"booking_id": "b2", "gross_revenue": 500, "net_to_property": 420,
             "management_fee": 50, "ota_commission": 30},
        ]

        call_count = [0]
        def side_effect(*args, **kwargs):
            chain = MagicMock()
            for m in ("select", "eq", "gte", "in_", "order", "limit"):
                setattr(chain, m, MagicMock(return_value=chain))
            call_count[0] += 1
            if call_count[0] == 1:
                chain.execute.return_value = MagicMock(data=booking_rows)
            else:
                chain.execute.return_value = MagicMock(data=fact_rows)
            return chain

        db = MagicMock()
        db.table.side_effect = side_effect

        result = get_property_financial_summary(db, "prop-1", days=90)
        assert result["gross_revenue_total"] == 1500.0
        assert result["net_revenue_total"] == 1270.0
        assert result["booking_count_with_financials"] == 2

    def test_returns_zeros_when_no_bookings(self):
        from services.owner_portal_data import get_property_financial_summary
        db = _make_db_chained([])
        result = get_property_financial_summary(db, "prop-1")
        assert result["gross_revenue_total"] == 0.0
        assert result["booking_count_with_financials"] == 0


# ---------------------------------------------------------------------------
# get_property_occupancy_rate
# ---------------------------------------------------------------------------

class TestGetPropertyOccupancyRate:
    def test_occupancy_calculated(self):
        from services.owner_portal_data import get_property_occupancy_rate
        today = datetime.now(timezone.utc)
        ci = (today - timedelta(days=5)).strftime("%Y-%m-%d")
        co = (today - timedelta(days=3)).strftime("%Y-%m-%d")
        rows = [{"check_in_date": ci, "check_out_date": co, "status": "checked_out"}]
        db = _make_db_chained(rows)
        result = get_property_occupancy_rate(db, "prop-1", days=30)
        assert result["occupied_nights"] >= 0
        assert 0.0 <= result["occupancy_pct"] <= 100.0
        assert result["period_days"] == 30

    def test_zero_occupancy_on_no_bookings(self):
        from services.owner_portal_data import get_property_occupancy_rate
        db = _make_db_chained([])
        result = get_property_occupancy_rate(db, "prop-1", days=30)
        assert result["occupancy_pct"] == 0.0


# ---------------------------------------------------------------------------
# get_owner_property_rich_summary
# ---------------------------------------------------------------------------

class TestGetOwnerPropertyRichSummary:
    def test_owner_gets_financials(self):
        from services.owner_portal_data import get_owner_property_rich_summary
        with patch("services.owner_portal_data.get_property_booking_counts",
                   return_value={"total": 5}), \
             patch("services.owner_portal_data.get_property_upcoming_bookings",
                   return_value=[]), \
             patch("services.owner_portal_data.get_property_occupancy_rate",
                   return_value={"occupancy_pct": 40.0, "occupied_nights": 12, "period_days": 30}), \
             patch("services.owner_portal_data.get_property_financial_summary",
                   return_value={"gross_revenue_total": 5000.0}) as mock_fin:
            result = get_owner_property_rich_summary(MagicMock(), "p1", role="owner")
        assert "financials" in result
        assert result["financials"]["gross_revenue_total"] == 5000.0
        mock_fin.assert_called_once()

    def test_viewer_no_financials(self):
        from services.owner_portal_data import get_owner_property_rich_summary
        with patch("services.owner_portal_data.get_property_booking_counts",
                   return_value={"total": 3}), \
             patch("services.owner_portal_data.get_property_upcoming_bookings",
                   return_value=[]), \
             patch("services.owner_portal_data.get_property_occupancy_rate",
                   return_value={"occupancy_pct": 20.0, "occupied_nights": 6, "period_days": 30}), \
             patch("services.owner_portal_data.get_property_financial_summary") as mock_fin:
            result = get_owner_property_rich_summary(MagicMock(), "p1", role="viewer")
        assert "financials" not in result
        mock_fin.assert_not_called()

    def test_structure_has_all_keys(self):
        from services.owner_portal_data import get_owner_property_rich_summary
        with patch("services.owner_portal_data.get_property_booking_counts",
                   return_value={"total": 0}), \
             patch("services.owner_portal_data.get_property_upcoming_bookings",
                   return_value=[]), \
             patch("services.owner_portal_data.get_property_occupancy_rate",
                   return_value={"occupancy_pct": 0.0, "occupied_nights": 0, "period_days": 30}):
            result = get_owner_property_rich_summary(MagicMock(), "p1", role="viewer")
        assert "property_id" in result
        assert "role" in result
        assert "booking_counts" in result
        assert "upcoming_bookings" in result
        assert "occupancy" in result


# ---------------------------------------------------------------------------
# Router test: GET /owner/portal/{property_id}/summary (Phase 301 upgrade)
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.owner_portal_router import router
    _app = FastAPI()
    _app.include_router(router)
    return TestClient(_app)


class TestOwnerPortalSummaryRouter:
    def test_403_when_no_access(self, client):
        with patch("api.owner_portal_router._get_db"), \
             patch("api.owner_portal_router.has_owner_access", return_value=False):
            resp = client.get(
                "/owner/portal/prop-1/summary",
                headers={"Authorization": "Bearer dummy"},
            )
        assert resp.status_code == 403

    def test_200_with_rich_summary(self, client):
        rich = {
            "property_id": "prop-1",
            "role": "owner",
            "booking_counts": {"total": 5},
            "upcoming_bookings": [],
            "occupancy": {"occupancy_pct": 30.0},
            "financials": {"gross_revenue_total": 2000.0},
        }
        with patch("api.owner_portal_router._get_db"), \
             patch("api.owner_portal_router.has_owner_access", return_value=True), \
             patch("api.owner_portal_router.get_owner_properties",
                   return_value=[{"property_id": "prop-1", "role": "owner"}]), \
             patch("api.owner_portal_router.get_owner_property_rich_summary",
                   return_value=rich):
            resp = client.get(
                "/owner/portal/prop-1/summary",
                headers={"Authorization": "Bearer dummy"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["property_id"] == "prop-1"
        assert "financials" in body
        assert "occupancy" in body

    def test_viewer_summary_no_financials(self, client):
        rich = {
            "property_id": "prop-1",
            "role": "viewer",
            "booking_counts": {"total": 2},
            "upcoming_bookings": [],
            "occupancy": {"occupancy_pct": 10.0},
        }
        with patch("api.owner_portal_router._get_db"), \
             patch("api.owner_portal_router.has_owner_access", return_value=True), \
             patch("api.owner_portal_router.get_owner_properties",
                   return_value=[{"property_id": "prop-1", "role": "viewer"}]), \
             patch("api.owner_portal_router.get_owner_property_rich_summary",
                   return_value=rich):
            resp = client.get(
                "/owner/portal/prop-1/summary",
                headers={"Authorization": "Bearer dummy"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert "financials" not in body
        assert body["role"] == "viewer"
