"""
Phase 216 — Portfolio Dashboard UI: Contract Tests

Tests for:
    portfolio_dashboard_router.py
        GET /portfolio/dashboard
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import main

_TENANT = "tenant-portfolio-test"


def _make_client() -> TestClient:
    return TestClient(main.app)


# ---------------------------------------------------------------------------
# Minimal DB mocks
# ---------------------------------------------------------------------------

class _MockResult:
    def __init__(self, data=None):
        self.data = data or []


class _PortfolioDB:
    """
    Mock DB. Each table can return configurable rows for the dashboard.
    booking_state           → occupancy
    booking_financial_facts → revenue
    tasks                   → tasks
    outbound_sync_log       → sync health
    """
    def __init__(self, occ=None, rev=None, tasks=None, sync=None):
        self._occ   = occ   or []
        self._rev   = rev   or []
        self._tasks = tasks or []
        self._sync  = sync  or []
        self._table = None

    def table(self, name):
        self._table = name
        return self

    def select(self, *a, **kw):
        return self

    def eq(self, *a, **kw):
        return self

    def gte(self, *a, **kw):
        return self

    def lt(self, *a, **kw):
        return self

    def in_(self, *a, **kw):
        return self

    def order(self, *a, **kw):
        return self

    def limit(self, *a, **kw):
        return self

    def execute(self):
        if self._table == "booking_state":
            return _MockResult(self._occ)
        if self._table == "booking_financial_facts":
            return _MockResult(self._rev)
        if self._table == "tasks":
            return _MockResult(self._tasks)
        if self._table == "outbound_sync_log":
            return _MockResult(self._sync)
        return _MockResult([])


def _occ_row(property_id="prop-001", check_in="2026-03-11", check_out="2026-03-15"):
    return {
        "property_id": property_id,
        "booking_id":  f"bk-{property_id}",
        "check_in":    check_in,
        "check_out":   check_out,
        "status":      "active",
    }


def _rev_row(property_id="prop-001", gross="1000.00", net="800.00", month="2026-03"):
    return {
        "property_id":     property_id,
        "booking_id":      f"bk-rev-{property_id}",
        "total_price":     gross,
        "net_to_property": net,
        "currency":        "USD",
        "recorded_at":     f"{month}-10T10:00:00",
        "event_kind":      "BOOKING_CREATED",
        "canonical_status": "ACTIVE",
        "payout_status":   None,
    }


def _task_row(property_id="prop-001", status="pending", escalation_level=0):
    return {
        "property_id":     property_id,
        "task_id":         f"task-{property_id}",
        "status":          status,
        "escalation_level": escalation_level,
    }


def _sync_row(property_id="prop-001", provider="airbnb", status="success",
              executed_at="2026-03-11T01:00:00"):
    return {
        "property_id": property_id,
        "provider":    provider,
        "status":      status,
        "executed_at": executed_at,
        "error_message": None,
    }


# ===========================================================================
# Helper unit tests (pure functions)
# ===========================================================================

from api.portfolio_dashboard_router import (
    _occupancy_for_property,
    _revenue_for_property,
    _tasks_for_property,
    _sync_health_for_property,
)


class TestOccupancyForProperty:

    def test_active_count(self):
        rows = [_occ_row("prop-001"), _occ_row("prop-001")]
        occ = _occupancy_for_property(rows, "prop-001", "2026-03-11")
        assert occ["active_bookings"] == 2

    def test_arrivals_match_today(self):
        rows = [_occ_row("prop-001", check_in="2026-03-11")]
        occ = _occupancy_for_property(rows, "prop-001", "2026-03-11")
        assert occ["arrivals_today"] == 1

    def test_departures_match_today(self):
        rows = [_occ_row("prop-001", check_out="2026-03-11")]
        occ = _occupancy_for_property(rows, "prop-001", "2026-03-11")
        assert occ["departures_today"] == 1
        assert occ["cleanings_today"] == 1

    def test_no_rows_returns_zeros(self):
        occ = _occupancy_for_property([], "prop-empty", "2026-03-11")
        assert occ["active_bookings"] == 0


class TestRevenueForProperty:

    def test_totals_summed(self):
        rows = [
            _rev_row("prop-001"),
            {**_rev_row("prop-001"), "booking_id": "bk-rev-prop-001-b"},
        ]
        rev = _revenue_for_property(rows, "prop-001")
        assert rev["booking_count"] == 2
        assert rev["gross_total"] == "2000.00"


    def test_no_rows(self):
        rev = _revenue_for_property([], "prop-empty")
        assert rev["booking_count"] == 0
        assert rev["gross_total"] is None

    def test_mixed_currency_nullifies(self):
        rows = [
            {**_rev_row("prop-001"), "currency": "USD"},
            {**_rev_row("prop-001"), "currency": "THB", "booking_id": "bk-2"},
        ]
        rev = _revenue_for_property(rows, "prop-001")
        assert rev["currency"] == "MIXED"
        assert rev["gross_total"] is None


class TestTasksForProperty:

    def test_pending_count(self):
        rows = [_task_row("prop-001"), _task_row("prop-001", status="in_progress")]
        t = _tasks_for_property(rows, "prop-001")
        assert t["pending_tasks"] == 2

    def test_escalated_count(self):
        rows = [_task_row("prop-001", escalation_level=1), _task_row("prop-001", escalation_level=0)]
        t = _tasks_for_property(rows, "prop-001")
        assert t["escalated_tasks"] == 1

    def test_no_rows(self):
        t = _tasks_for_property([], "prop-empty")
        assert t["pending_tasks"] == 0


class TestSyncHealthForProperty:

    def test_not_stale_recent_sync(self):
        rows = [_sync_row("prop-001", executed_at="2026-03-11T01:00:00")]
        h = _sync_health_for_property(rows, "prop-001", "2026-03-11T02:00:00Z")
        assert h["stale"] is False

    def test_stale_old_sync(self):
        rows = [_sync_row("prop-001", executed_at="2026-03-09T00:00:00")]
        h = _sync_health_for_property(rows, "prop-001", "2026-03-11T02:00:00Z")
        assert h["stale"] is True

    def test_no_rows_returns_none(self):
        h = _sync_health_for_property([], "prop-empty", "2026-03-11T02:00:00Z")
        assert h["stale"] is None
        assert h["last_sync_at"] is None


# ===========================================================================
# GET /portfolio/dashboard
# ===========================================================================

class TestPortfolioDashboard:

    def test_happy_path_single_property(self):
        db = _PortfolioDB(
            occ=[_occ_row()],
            rev=[_rev_row()],
            tasks=[_task_row()],
            sync=[_sync_row()],
        )
        with patch("api.portfolio_dashboard_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/portfolio/dashboard",
                headers={"Authorization": "Bearer mock"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["property_count"] == 1
        assert body["properties"][0]["property_id"] == "prop-001"

    def test_response_has_all_sections(self):
        db = _PortfolioDB(occ=[_occ_row()], rev=[_rev_row()], tasks=[_task_row()], sync=[_sync_row()])
        with patch("api.portfolio_dashboard_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/portfolio/dashboard",
                headers={"Authorization": "Bearer mock"},
            )
        card = resp.json()["properties"][0]
        assert "occupancy"   in card
        assert "revenue"     in card
        assert "tasks"       in card
        assert "sync_health" in card

    def test_empty_db_returns_zero_properties(self):
        db = _PortfolioDB()
        with patch("api.portfolio_dashboard_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/portfolio/dashboard",
                headers={"Authorization": "Bearer mock"},
            )
        assert resp.status_code == 200
        assert resp.json()["property_count"] == 0

    def test_multiple_properties_derived(self):
        db = _PortfolioDB(
            occ=[_occ_row("prop-001"), _occ_row("prop-002")],
            rev=[_rev_row("prop-003")],
        )
        with patch("api.portfolio_dashboard_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/portfolio/dashboard",
                headers={"Authorization": "Bearer mock"},
            )
        assert resp.json()["property_count"] == 3  # union of all sources

    def test_custom_as_of_date(self):
        db = _PortfolioDB(occ=[_occ_row(check_in="2026-01-15")])
        with patch("api.portfolio_dashboard_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/portfolio/dashboard",
                params={"as_of": "2026-01-15"},
                headers={"Authorization": "Bearer mock"},
            )
        body = resp.json()
        assert body["as_of"] == "2026-01-15"
        assert body["properties"][0]["occupancy"]["arrivals_today"] == 1

    def test_custom_revenue_month(self):
        db = _PortfolioDB(rev=[_rev_row(month="2026-01")])
        with patch("api.portfolio_dashboard_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/portfolio/dashboard",
                params={"month": "2026-01"},
                headers={"Authorization": "Bearer mock"},
            )
        assert resp.json()["revenue_month"] == "2026-01"

    def test_stale_property_sorted_first(self):
        db = _PortfolioDB(
            sync=[
                _sync_row("prop-fresh", executed_at="2026-03-11T01:00:00"),
                _sync_row("prop-stale", executed_at="2026-03-08T00:00:00"),
            ]
        )
        from datetime import datetime as _dt, timezone as _tz
        frozen = _dt(2026, 3, 11, 2, 0, 0, tzinfo=_tz.utc)
        with patch("api.portfolio_dashboard_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT), \
             patch("api.portfolio_dashboard_router.datetime") as mock_dt:
            mock_dt.now.return_value = frozen
            mock_dt.fromisoformat = _dt.fromisoformat
            mock_dt.side_effect = lambda *a, **kw: _dt(*a, **kw)
            resp = _make_client().get(
                "/portfolio/dashboard",
                params={"as_of": "2026-03-11"},
                headers={"Authorization": "Bearer mock"},
            )
        props = resp.json()["properties"]
        assert props[0]["property_id"] == "prop-stale"

    def test_response_has_generated_at(self):
        db = _PortfolioDB()
        with patch("api.portfolio_dashboard_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/portfolio/dashboard",
                headers={"Authorization": "Bearer mock"},
            )
        assert "generated_at" in resp.json()
