"""
Phase 222 — AI Context Aggregation Endpoints — Contract Tests

Tests cover:
    - _fetch_property_meta: found, not_found, error
    - _fetch_active_bookings: happy path, empty, error
    - _fetch_open_tasks: happy path, age_minutes annotation, error
    - _fetch_sync_health: counts failures correctly
    - _fetch_financial_snapshot: groups by currency, empty
    - _fetch_availability_summary: computes occupancy rate
    - _fetch_tenant_tasks_summary: by_priority, by_kind, critical_past_ack_sla
    - _fetch_tenant_operations: arrivals + departures for today
    - _fetch_dlq_summary: alert flag at threshold
    - _fetch_sync_summary: failure_rate_24h calculation
    - get_property_ai_context endpoint: 403 on not_found, 200 shape
    - get_operations_day_ai_context endpoint: 200 shape + ai_hints
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from api.ai_context_router import (
    _fetch_property_meta,
    _fetch_active_bookings,
    _fetch_open_tasks,
    _fetch_sync_health,
    _fetch_financial_snapshot,
    _fetch_availability_summary,
    _fetch_tenant_tasks_summary,
    _fetch_tenant_operations,
    _fetch_dlq_summary,
    _fetch_sync_summary,
    get_property_ai_context,
    get_operations_day_ai_context,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_db(table_data: dict) -> MagicMock:
    """
    Create a mock Supabase DB client that returns table_data[table_name]
    as the result of any .execute() call.
    """
    def table(name):
        m = MagicMock()
        rows = table_data.get(name, [])

        # Chain all common query methods
        for method in (
            "select", "eq", "in_", "order", "limit",
            "gte", "is_", "execute",
        ):
            getattr(m, method).return_value = m

        result = MagicMock()
        result.data = rows
        result.count = len(rows)
        m.execute.return_value = result
        return m

    db = MagicMock()
    db.table.side_effect = table
    return db


def _error_db() -> MagicMock:
    """A DB client that raises on every query."""
    db = MagicMock()
    db.table.side_effect = Exception("DB down")
    return db


TENANT = "tenant-test"
PROP = "prop-001"


# ---------------------------------------------------------------------------
# _fetch_property_meta
# ---------------------------------------------------------------------------

class TestFetchPropertyMeta:
    def test_returns_meta_when_found(self):
        db = _mock_db({"properties": [{"property_id": PROP, "name": "Villa A", "address": "Bangkok", "property_type": "villa", "created_at": "2025-01-01"}]})
        result = _fetch_property_meta(db, TENANT, PROP)
        assert result["name"] == "Villa A"
        assert result["property_id"] == PROP

    def test_returns_not_found_status_when_empty(self):
        db = _mock_db({"properties": []})
        result = _fetch_property_meta(db, TENANT, PROP)
        assert result["status"] == "not_found"

    def test_returns_error_status_on_db_failure(self):
        result = _fetch_property_meta(_error_db(), TENANT, PROP)
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# _fetch_active_bookings
# ---------------------------------------------------------------------------

class TestFetchActiveBookings:
    def test_returns_list_on_success(self):
        rows = [{"booking_id": "b1", "source": "airbnb", "status": "active", "check_in": "2026-03-15", "check_out": "2026-03-18", "nights": 3, "currency": "THB", "total_amount": 9000}]
        db = _mock_db({"booking_state": rows})
        result = _fetch_active_bookings(db, TENANT, PROP)
        assert len(result) == 1
        assert result[0]["booking_id"] == "b1"

    def test_returns_empty_list_on_no_rows(self):
        db = _mock_db({"booking_state": []})
        assert _fetch_active_bookings(db, TENANT, PROP) == []

    def test_returns_empty_list_on_error(self):
        assert _fetch_active_bookings(_error_db(), TENANT, PROP) == []


# ---------------------------------------------------------------------------
# _fetch_open_tasks
# ---------------------------------------------------------------------------

class TestFetchOpenTasks:
    def test_annotates_age_minutes(self):
        old_time = (datetime.now(tz=timezone.utc) - timedelta(hours=2)).isoformat()
        rows = [{"task_id": "t1", "kind": "CLEANING", "status": "PENDING", "priority": "NORMAL", "created_at": old_time, "acknowledged_at": None, "description": ""}]
        db = _mock_db({"tasks": rows})
        result = _fetch_open_tasks(db, TENANT, PROP)
        assert len(result) == 1
        age = result[0]["age_minutes"]
        assert age is not None
        assert 110 <= age <= 130  # ~120 minutes ± tolerance

    def test_handles_missing_created_at(self):
        rows = [{"task_id": "t2", "kind": "GENERAL", "status": "PENDING", "priority": "HIGH", "created_at": None, "acknowledged_at": None, "description": ""}]
        db = _mock_db({"tasks": rows})
        result = _fetch_open_tasks(db, TENANT, PROP)
        assert result[0]["age_minutes"] is None

    def test_returns_empty_list_on_error(self):
        assert _fetch_open_tasks(_error_db(), TENANT, PROP) == []


# ---------------------------------------------------------------------------
# _fetch_sync_health
# ---------------------------------------------------------------------------

class TestFetchSyncHealth:
    def test_counts_failures_correctly(self):
        rows = [
            {"provider": "airbnb", "status": "success", "synced_at": "2026-03-11T00:00:00+00:00", "booking_id": "b1"},
            {"provider": "airbnb", "status": "failed", "synced_at": "2026-03-11T01:00:00+00:00", "booking_id": "b2"},
            {"provider": "airbnb", "status": "error", "synced_at": "2026-03-11T02:00:00+00:00", "booking_id": "b3"},
        ]
        db = _mock_db({"outbound_sync_log": rows})
        result = _fetch_sync_health(db, TENANT, PROP)
        assert result["recent_count"] == 3
        assert result["recent_failed"] == 2

    def test_returns_zero_on_empty(self):
        db = _mock_db({"outbound_sync_log": []})
        result = _fetch_sync_health(db, TENANT, PROP)
        assert result["recent_count"] == 0
        assert result["recent_failed"] == 0

    def test_degrades_gracefully_on_error(self):
        result = _fetch_sync_health(_error_db(), TENANT, PROP)
        assert result["recent_count"] == 0
        assert "error" in result


# ---------------------------------------------------------------------------
# _fetch_financial_snapshot
# ---------------------------------------------------------------------------

class TestFetchFinancialSnapshot:
    def test_groups_by_currency(self):
        rows = [
            {"booking_id": "b1", "currency": "THB", "gross_amount": 10000, "net_amount": 9000, "commission_amount": 1000, "lifecycle_status": "confirmed"},
            {"booking_id": "b2", "currency": "THB", "gross_amount": 5000, "net_amount": 4500, "commission_amount": 500, "lifecycle_status": "active"},
            {"booking_id": "b3", "currency": "USD", "gross_amount": 300, "net_amount": 270, "commission_amount": 30, "lifecycle_status": "confirmed"},
        ]
        db = _mock_db({"booking_financial_facts": rows})
        result = _fetch_financial_snapshot(db, TENANT, PROP)
        assert result["total_bookings"] == 3
        currencies = {c["currency"]: c for c in result["currencies"]}
        assert "THB" in currencies
        assert "USD" in currencies
        assert currencies["THB"]["gross_total"] == 15000.0

    def test_returns_zero_on_empty(self):
        db = _mock_db({"booking_financial_facts": []})
        result = _fetch_financial_snapshot(db, TENANT, PROP)
        assert result["total_bookings"] == 0

    def test_degrades_on_error(self):
        result = _fetch_financial_snapshot(_error_db(), TENANT, PROP)
        assert result["total_bookings"] == 0
        assert "error" in result


# ---------------------------------------------------------------------------
# _fetch_availability_summary
# ---------------------------------------------------------------------------

class TestFetchAvailabilitySummary:
    def test_counts_occupied_nights(self):
        today = date.today()
        rows = [{"booking_id": "b1", "check_in": today.isoformat(), "check_out": (today + timedelta(days=5)).isoformat(), "status": "active"}]
        db = _mock_db({"booking_state": rows})
        result = _fetch_availability_summary(db, TENANT, PROP)
        assert result["occupied_nights_next_30"] == 5
        assert result["available_nights_next_30"] == 25
        assert abs(result["occupancy_rate_next_30"] - 5/30) < 0.001

    def test_returns_zero_on_no_bookings(self):
        db = _mock_db({"booking_state": []})
        result = _fetch_availability_summary(db, TENANT, PROP)
        assert result["occupied_nights_next_30"] == 0

    def test_degrades_on_error(self):
        result = _fetch_availability_summary(_error_db(), TENANT, PROP)
        assert result["occupied_nights_next_30"] is None


# ---------------------------------------------------------------------------
# _fetch_tenant_tasks_summary
# ---------------------------------------------------------------------------

class TestFetchTenantTasksSummary:
    def test_groups_by_priority_and_kind(self):
        today = date.today().isoformat()
        rows = [
            {"task_id": "t1", "kind": "CLEANING", "status": "PENDING", "priority": "HIGH", "created_at": datetime.now(tz=timezone.utc).isoformat(), "due_date": today},
            {"task_id": "t2", "kind": "CLEANING", "status": "IN_PROGRESS", "priority": "NORMAL", "created_at": datetime.now(tz=timezone.utc).isoformat(), "due_date": today},
            {"task_id": "t3", "kind": "MAINTENANCE", "status": "PENDING", "priority": "HIGH", "created_at": datetime.now(tz=timezone.utc).isoformat(), "due_date": today},
        ]
        db = _mock_db({"tasks": rows})
        result = _fetch_tenant_tasks_summary(db, TENANT)
        assert result["total_open"] == 3
        # Phase 1043: by_priority_actionable counts only overdue + due_today tasks
        assert result["by_priority_actionable"]["HIGH"] == 2
        assert result["by_kind"]["CLEANING"] == 2
        assert result["by_kind"]["MAINTENANCE"] == 1

    def test_date_aware_buckets_split_correctly(self):
        today = date.today().isoformat()
        future = (date.today() + timedelta(days=30)).isoformat()
        overdue = (date.today() - timedelta(days=1)).isoformat()
        rows = [
            {"task_id": "t1", "kind": "CLEANING", "status": "PENDING", "priority": "HIGH", "created_at": datetime.now(tz=timezone.utc).isoformat(), "due_date": overdue},
            {"task_id": "t2", "kind": "CLEANING", "status": "PENDING", "priority": "HIGH", "created_at": datetime.now(tz=timezone.utc).isoformat(), "due_date": today},
            {"task_id": "t3", "kind": "CLEANING", "status": "PENDING", "priority": "HIGH", "created_at": datetime.now(tz=timezone.utc).isoformat(), "due_date": future},
        ]
        db = _mock_db({"tasks": rows})
        result = _fetch_tenant_tasks_summary(db, TENANT)
        assert result["total_open"] == 3
        assert result["overdue"] == 1
        assert result["due_today"] == 1
        assert result["future"] == 1
        assert result["actionable_now"] == 2
        assert result["by_priority_actionable"].get("HIGH", 0) == 2  # future HIGH excluded

    def test_all_future_tasks_yield_zero_actionable(self):
        future = (date.today() + timedelta(days=30)).isoformat()
        rows = [
            {"task_id": "t1", "kind": "CHECKIN_PREP", "status": "PENDING", "priority": "HIGH", "created_at": datetime.now(tz=timezone.utc).isoformat(), "due_date": future},
            {"task_id": "t2", "kind": "CHECKIN_PREP", "status": "PENDING", "priority": "HIGH", "created_at": datetime.now(tz=timezone.utc).isoformat(), "due_date": future},
        ]
        db = _mock_db({"tasks": rows})
        result = _fetch_tenant_tasks_summary(db, TENANT)
        assert result["total_open"] == 2
        assert result["actionable_now"] == 0
        assert result["future"] == 2
        assert result["by_priority_actionable"] == {}

    def test_critcal_past_ack_sla_counts_pending_over_5min(self):
        old_time = (datetime.now(tz=timezone.utc) - timedelta(minutes=10)).isoformat()
        fresh_time = (datetime.now(tz=timezone.utc) - timedelta(seconds=30)).isoformat()
        today = date.today().isoformat()
        rows = [
            {"task_id": "t1", "kind": "GENERAL", "status": "PENDING", "priority": "CRITICAL", "created_at": old_time, "due_date": today},
            {"task_id": "t2", "kind": "GENERAL", "status": "PENDING", "priority": "CRITICAL", "created_at": fresh_time, "due_date": today},
        ]
        db = _mock_db({"tasks": rows})
        result = _fetch_tenant_tasks_summary(db, TENANT)
        assert result["critical_past_ack_sla"] == 1  # only the old one

    def test_returns_zeros_on_empty(self):
        db = _mock_db({"tasks": []})
        result = _fetch_tenant_tasks_summary(db, TENANT)
        assert result["total_open"] == 0
        assert result["actionable_now"] == 0
        assert result["critical_past_ack_sla"] == 0


# ---------------------------------------------------------------------------
# _fetch_tenant_operations
# ---------------------------------------------------------------------------

class TestFetchTenantOperations:
    def test_counts_todays_arrivals_departures(self):
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        rows = [
            {"booking_id": "b1", "property_id": PROP, "check_in": today, "check_out": (date.today() + timedelta(days=3)).isoformat(), "status": "active"},
            {"booking_id": "b2", "property_id": PROP, "check_in": yesterday, "check_out": today, "status": "active"},
        ]
        db = _mock_db({"booking_state": rows})
        result = _fetch_tenant_operations(db, TENANT)
        assert result["arrivals_count"] == 1
        assert result["departures_count"] == 1
        assert result["cleanings_due"] == 1

    def test_degrades_on_error(self):
        result = _fetch_tenant_operations(_error_db(), TENANT)
        assert result["arrivals_count"] == 0


# ---------------------------------------------------------------------------
# _fetch_dlq_summary
# ---------------------------------------------------------------------------

class TestFetchDlqSummary:
    def test_alert_false_below_threshold(self):
        rows = [{"id": 1}, {"id": 2}]
        db = _mock_db({"ota_dead_letter": rows})
        result = _fetch_dlq_summary(db)
        assert result["unprocessed_count"] == 2
        assert result["alert"] is False

    def test_alert_true_at_or_above_five(self):
        rows = [{"id": i} for i in range(5)]
        db = _mock_db({"ota_dead_letter": rows})
        # count is set to len(rows)
        result = _fetch_dlq_summary(db)
        assert result["alert"] is True

    def test_degrades_on_error(self):
        result = _fetch_dlq_summary(_error_db())
        assert result["unprocessed_count"] is None


# ---------------------------------------------------------------------------
# _fetch_sync_summary
# ---------------------------------------------------------------------------

class TestFetchSyncSummary:
    def test_computes_failure_rate(self):
        rows = [
            {"status": "success"},
            {"status": "failed"},
            {"status": "failed"},
            {"status": "success"},
        ]
        db = _mock_db({"outbound_sync_log": rows})
        result = _fetch_sync_summary(db, TENANT)
        assert result["event_count_24h"] == 4
        assert result["failure_count_24h"] == 2
        assert abs(result["failure_rate_24h"] - 0.5) < 0.001

    def test_returns_none_rate_on_empty(self):
        db = _mock_db({"outbound_sync_log": []})
        result = _fetch_sync_summary(db, TENANT)
        assert result["failure_rate_24h"] is None


# ---------------------------------------------------------------------------
# Endpoint integration tests (via FastAPI TestClient)
# ---------------------------------------------------------------------------

class TestGetPropertyAiContextEndpoint:
    def _make_client(self, property_rows, booking_rows, task_rows, sync_rows, financial_rows):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from api.ai_context_router import router

        app = FastAPI()
        app.include_router(router)

        # Bypass JWT auth
        from api.ai_context_router import get_property_ai_context
        import api.auth as auth_mod
        app.dependency_overrides = {}

        # Patch jwt_auth globally
        with patch("api.ai_context_router.jwt_auth", return_value=TENANT):
            pass  # just confirming it's patchable

        return TestClient(app)

    def test_returns_403_when_property_not_found(self):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from api.ai_context_router import router
        import api.ai_context_router as ctx_mod

        app = FastAPI()
        app.include_router(router)

        db = _mock_db({"properties": []})  # not_found

        with patch("api.ai_context_router.jwt_auth", return_value=TENANT), \
             patch.object(ctx_mod, "_get_db", return_value=db):
            client = TestClient(app)
            resp = client.get(f"/ai/context/property/{PROP}", headers={"Authorization": "Bearer fake"})

        assert resp.status_code == 403

    def test_returns_200_with_expected_shape(self):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from api.ai_context_router import router
        import api.ai_context_router as ctx_mod

        app = FastAPI()
        app.include_router(router)

        today = date.today().isoformat()
        db = _mock_db({
            "properties": [{"property_id": PROP, "name": "Villa A", "address": "BKK", "property_type": "villa", "created_at": "2025-01-01"}],
            "booking_state": [{"booking_id": "b1", "source": "airbnb", "status": "active", "check_in": today, "check_out": today, "nights": 1, "currency": "THB", "total_amount": 3000}],
            "tasks": [],
            "outbound_sync_log": [],
            "booking_financial_facts": [],
        })

        with patch("api.ai_context_router.jwt_auth", return_value=TENANT), \
             patch.object(ctx_mod, "_get_db", return_value=db):
            client = TestClient(app)
            resp = client.get(f"/ai/context/property/{PROP}", headers={"Authorization": "Bearer fake"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["context_type"] == "property"
        assert data["property_id"] == PROP
        assert "bookings" in data
        assert "tasks" in data
        assert "sync" in data
        assert "financial" in data
        assert "availability" in data
        assert "ai_hints" in data
        assert "response_ms" in data


class TestGetOperationsDayAiContextEndpoint:
    def test_returns_200_with_expected_shape(self):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from api.ai_context_router import router
        import api.ai_context_router as ctx_mod

        app = FastAPI()
        app.include_router(router)

        db = _mock_db({
            "booking_state": [],
            "tasks": [],
            "ota_dead_letter": [],
            "outbound_sync_log": [],
        })

        with patch("api.ai_context_router.jwt_auth", return_value=TENANT), \
             patch.object(ctx_mod, "_get_db", return_value=db):
            client = TestClient(app)
            resp = client.get("/ai/context/operations-day", headers={"Authorization": "Bearer fake"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["context_type"] == "operations-day"
        assert "operations" in data
        assert "tasks" in data
        assert "dlq" in data
        assert "outbound_sync" in data
        assert "ai_hints" in data
        hints = data["ai_hints"]
        assert "critical_tasks_over_sla" in hints
        assert "dlq_alert" in hints
        assert "sync_degraded" in hints

    def test_ai_hints_sync_degraded_flag(self):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from api.ai_context_router import router
        import api.ai_context_router as ctx_mod

        app = FastAPI()
        app.include_router(router)

        # 3/3 sync failures in 24h → failure_rate_24h = 1.0 → sync_degraded = True
        db = _mock_db({
            "booking_state": [],
            "tasks": [],
            "ota_dead_letter": [],
            "outbound_sync_log": [{"status": "failed"}, {"status": "failed"}, {"status": "failed"}],
        })

        with patch("api.ai_context_router.jwt_auth", return_value=TENANT), \
             patch.object(ctx_mod, "_get_db", return_value=db):
            client = TestClient(app)
            resp = client.get("/ai/context/operations-day", headers={"Authorization": "Bearer fake"})

        assert resp.status_code == 200
        assert resp.json()["ai_hints"]["sync_degraded"] is True
