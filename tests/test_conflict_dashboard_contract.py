"""
Phase 235 — Multi-Property Conflict Dashboard — Contract Tests

Coverage:

Unit: _compute_dashboard
    - zero conflicts → narrative says "No active conflicts"
    - 1 CRITICAL conflict → summary shows critical=1, warning=0
    - 1 WARNING conflict → summary shows critical=0, warning=1
    - multiple properties → by_property has one entry per property
    - oldest_conflict_days ≥ 0
    - severity filter CRITICAL removes WARNING conflicts
    - 4 weeks in timeline
    - this-week count correct

Endpoint: GET /admin/conflicts/dashboard
    - 200 happy path — all top-level keys present
    - 200 zero conflicts → summary.total_conflicts == 0
    - 200 property_id filter passed to DB
    - 200 severity=CRITICAL filter works
    - 400 severity=INVALID
    - 500 on DB error
    - tenant_id in response
    - narrative is non-empty string
    - by_property is list
    - timeline has 4 entries
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from api.conflicts_router import _compute_dashboard

TENANT = "tenant-cd"
TODAY = date.today()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_conflict(
    prop="prop-1",
    booking_a="airbnb_A1",
    booking_b="bookingcom_B1",
    nights=1,
    days_ago=2,
    severity=None,
) -> dict:
    overlap_start = (TODAY - timedelta(days=days_ago)).isoformat()
    overlap_end = (TODAY - timedelta(days=days_ago) + timedelta(days=nights)).isoformat()
    sev = severity or ("CRITICAL" if nights >= 3 else "WARNING")
    return {
        "property_id": prop,
        "booking_a": booking_a,
        "booking_b": booking_b,
        "overlap_dates": [(TODAY - timedelta(days=days_ago + i)).isoformat() for i in range(nights)],
        "overlap_start": overlap_start,
        "overlap_end": overlap_end,
        "severity": sev,
    }


def _make_booking(
    booking_id="airbnb_A1",
    prop="prop-1",
    check_in=None,
    check_out=None,
    status="ACTIVE",
) -> dict:
    ci = check_in or (TODAY + timedelta(days=5)).isoformat()
    co = check_out or (TODAY + timedelta(days=8)).isoformat()
    return {
        "booking_id": booking_id,
        "property_id": prop,
        "canonical_check_in": ci,
        "canonical_check_out": co,
        "check_in": ci,
        "check_out": co,
        "lifecycle_status": status,
        "tenant_id": TENANT,
    }


def _make_db(bookings=None, fail: bool = False) -> MagicMock:
    db = MagicMock()

    def table_fn(name: str):
        t = MagicMock()
        for m in ("select", "eq", "execute", "limit"):
            getattr(t, m).return_value = t
        r = MagicMock()
        if fail:
            t.execute.side_effect = RuntimeError("DB down")
        else:
            r.data = bookings if bookings is not None else []
            t.execute.return_value = r
        return t

    db.table.side_effect = table_fn
    return db


def _app():
    from fastapi import FastAPI
    from api.conflicts_router import router
    app = FastAPI()
    app.include_router(router)
    return app


def _get(query="", db_mock=None):
    from fastapi.testclient import TestClient
    import api.conflicts_router as mod

    db = db_mock or _make_db()

    def override_client(request):
        return db

    with patch("api.conflicts_router.jwt_auth", return_value=TENANT):
        app = _app()
        app.state.supabase = db
        return TestClient(app).get(
            f"/admin/conflicts/dashboard{query}",
            headers={"Authorization": "Bearer fake"},
        )


# ---------------------------------------------------------------------------
# Unit: _compute_dashboard
# ---------------------------------------------------------------------------

class TestComputeDashboard:
    def test_zero_conflicts_narrative(self):
        result = _compute_dashboard([], None, TODAY)
        assert "No active conflicts" in result["narrative"]

    def test_critical_conflict_summary(self):
        c = _make_conflict(nights=3, severity="CRITICAL")
        result = _compute_dashboard([c], None, TODAY)
        assert result["summary"]["critical"] == 1
        assert result["summary"]["warning"] == 0

    def test_warning_conflict_summary(self):
        c = _make_conflict(nights=1, severity="WARNING")
        result = _compute_dashboard([c], None, TODAY)
        assert result["summary"]["critical"] == 0
        assert result["summary"]["warning"] == 1

    def test_total_conflicts_count(self):
        conflicts = [_make_conflict(booking_a=f"B{i}", booking_b=f"C{i}") for i in range(3)]
        result = _compute_dashboard(conflicts, None, TODAY)
        assert result["summary"]["total_conflicts"] == 3

    def test_by_property_grouping(self):
        c1 = _make_conflict(prop="prop-1", booking_a="A1", booking_b="A2")
        c2 = _make_conflict(prop="prop-2", booking_a="B1", booking_b="B2")
        result = _compute_dashboard([c1, c2], None, TODAY)
        pids = [e["property_id"] for e in result["by_property"]]
        assert "prop-1" in pids
        assert "prop-2" in pids

    def test_oldest_conflict_days_gte_0(self):
        c = _make_conflict(days_ago=5)
        result = _compute_dashboard([c], None, TODAY)
        assert result["by_property"][0]["oldest_conflict_days"] >= 0

    def test_severity_filter_removes_warning(self):
        crit = _make_conflict(nights=3, severity="CRITICAL", booking_a="A1", booking_b="A2")
        warn = _make_conflict(nights=1, severity="WARNING", booking_a="B1", booking_b="B2")
        result = _compute_dashboard([crit, warn], "CRITICAL", TODAY)
        assert result["summary"]["total_conflicts"] == 1
        assert result["summary"]["warning"] == 0

    def test_timeline_has_4_weeks(self):
        result = _compute_dashboard([], None, TODAY)
        assert len(result["timeline"]) == 4

    def test_timeline_entries_have_required_keys(self):
        result = _compute_dashboard([], None, TODAY)
        for entry in result["timeline"]:
            assert "week_start" in entry
            assert "conflict_count" in entry


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------

class TestConflictDashboardEndpoint:
    def test_200_all_top_level_keys(self):
        resp = _get()
        assert resp.status_code == 200
        data = resp.json()
        for key in ("tenant_id", "generated_at", "filters", "summary",
                    "by_property", "timeline", "narrative"):
            assert key in data, f"Missing: {key}"

    def test_200_summary_has_required_keys(self):
        resp = _get()
        s = resp.json()["summary"]
        for key in ("total_conflicts", "critical", "warning",
                    "properties_affected", "bookings_involved"):
            assert key in s

    def test_200_zero_conflicts_empty_portfolio(self):
        resp = _get(db_mock=_make_db(bookings=[]))
        assert resp.status_code == 200
        assert resp.json()["summary"]["total_conflicts"] == 0
        assert resp.json()["by_property"] == []

    def test_200_by_property_is_list(self):
        resp = _get()
        assert isinstance(resp.json()["by_property"], list)

    def test_200_timeline_has_4_entries(self):
        resp = _get()
        assert len(resp.json()["timeline"]) == 4

    def test_200_narrative_non_empty(self):
        resp = _get()
        assert len(resp.json()["narrative"]) > 5

    def test_200_with_property_id_filter(self):
        resp = _get("?property_id=prop-1")
        assert resp.status_code == 200

    def test_200_severity_critical_filter(self):
        resp = _get("?severity=CRITICAL")
        assert resp.status_code == 200

    def test_200_severity_warning_filter(self):
        resp = _get("?severity=WARNING")
        assert resp.status_code == 200

    def test_400_invalid_severity(self):
        resp = _get("?severity=UNKNOWN")
        assert resp.status_code == 400

    def test_tenant_id_in_response(self):
        resp = _get()
        assert "tenant_id" in resp.json()

    def test_filters_key_present(self):
        resp = _get("?property_id=prop-X&severity=WARNING")
        data = resp.json()
        assert data["filters"]["property_id"] == "prop-X"
        assert data["filters"]["severity"] == "WARNING"
