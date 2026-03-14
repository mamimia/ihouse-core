"""
Phases 636–645 — Wave 3 Task Enhancement Contract Tests

Tests for all Wave 3 API routers:
    - Cleaning Checklist Template CRUD (Phase 626)
    - Default Template Seeder (Phase 627)
    - Cleaning Progress: start, update, photos, supplies (Phases 628-630)
    - Cleaning Complete Blocking (Phase 631)
    - Reference vs Cleaning Photo Comparison (Phase 632)
    - Task Navigate to Property (Phase 633)
    - Task Automator CHECKOUT_VERIFY (Phase 634)
    - Worker Calendar (Phase 635)
    - Edge cases (Phases 644-645)
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import main

_TENANT = "tenant-wave3-test"


def _make_client() -> TestClient:
    return TestClient(main.app)


def _auth_header() -> dict:
    return {"Authorization": "Bearer mock-token"}


# ---------------------------------------------------------------------------
# Mock DB helpers (same pattern as Wave 1/2)
# ---------------------------------------------------------------------------

class _MockResult:
    def __init__(self, data=None, count=None):
        self.data = data or []
        self.count = count or 0


class _MockTable:
    def __init__(self, rows=None):
        self._rows = rows or []
        self._result = _MockResult(data=self._rows)

    def select(self, *a, **kw): return self
    def eq(self, *a, **kw): return self
    def limit(self, *a): return self
    def order(self, *a, **kw): return self
    def insert(self, data):
        self._rows = [data] if isinstance(data, dict) else data
        self._result = _MockResult(data=[{**d, "id": "mock-uuid"} for d in (self._rows if isinstance(self._rows, list) else [self._rows])])
        return self
    def upsert(self, data, **kw):
        self._rows = [data] if isinstance(data, dict) else data
        self._result = _MockResult(data=self._rows)
        return self
    def update(self, data):
        if self._rows:
            for r in self._rows:
                if isinstance(r, dict):
                    r.update(data)
        self._result = _MockResult(data=self._rows)
        return self
    def delete(self):
        self._result = _MockResult(data=self._rows)
        return self
    def execute(self):
        return self._result


class _MockDB:
    def __init__(self, tables: dict = None):
        self._tables = tables or {}

    def table(self, name: str):
        return self._tables.get(name, _MockTable())


def _task_db(extra_tables=None):
    """DB with a task row and property row."""
    task = {
        "task_id": "abc123", "tenant_id": _TENANT, "kind": "CLEANING",
        "status": "PENDING", "priority": "MEDIUM", "urgency": "normal",
        "worker_role": "CLEANER", "ack_sla_minutes": 60,
        "booking_id": "booking-1", "property_id": "prop-1",
        "due_date": "2026-04-01", "title": "Pre-arrival cleaning",
        "created_at": "2026-03-14T00:00:00Z", "updated_at": "2026-03-14T00:00:00Z",
    }
    prop = {
        "property_id": "prop-1", "tenant_id": _TENANT,
        "display_name": "Villa Seaview", "latitude": 13.756, "longitude": 100.501,
    }
    tables = {
        "tasks": _MockTable([task]),
        "properties": _MockTable([prop]),
    }
    if extra_tables:
        tables.update(extra_tables)
    return _MockDB(tables)


def _progress_row():
    return {
        "id": "progress-uuid-1",
        "task_id": "abc123",
        "tenant_id": _TENANT,
        "booking_id": "booking-1",
        "property_id": "prop-1",
        "template_id": "tmpl-1",
        "checklist_state": [
            {"room": "bedroom_1", "label": "Change sheets", "done": False, "requires_photo": True},
            {"room": "bathroom_1", "label": "Clean toilet", "done": False, "requires_photo": True},
            {"room": "kitchen", "label": "Clean counters", "done": False, "requires_photo": False},
        ],
        "supply_state": [
            {"item": "sheets", "label": "Enough clean sheets?", "status": "unchecked"},
            {"item": "towels", "label": "Enough clean towels?", "status": "unchecked"},
        ],
        "all_photos_taken": False,
        "all_items_done": False,
        "all_supplies_ok": False,
        "worker_id": "WRK-001",
    }


# ===========================================================================
# Phase 626 — Cleaning Checklist Template CRUD
# ===========================================================================

class TestCleaningTemplate:

    def test_upsert_template(self):
        with patch("api.cleaning_task_router._get_supabase_client", return_value=_MockDB({"cleaning_checklist_templates": _MockTable()})), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/properties/prop-1/cleaning-checklist",
                json={"items": [{"room": "bedroom", "label": "Make bed"}], "name": "Custom"},
                headers=_auth_header(),
            )
        assert resp.status_code == 200
        assert resp.json()["saved"] is True
        assert resp.json()["item_count"] == 1

    def test_upsert_template_empty_items(self):
        with patch("api.cleaning_task_router._get_supabase_client", return_value=_MockDB()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/properties/prop-1/cleaning-checklist",
                json={"items": []},
                headers=_auth_header(),
            )
        assert resp.status_code == 400

    def test_get_template_property_specific(self):
        tmpl = {"id": "t1", "tenant_id": _TENANT, "property_id": "prop-1", "name": "Custom", "items": [{"room": "bed"}]}
        with patch("api.cleaning_task_router._get_supabase_client", return_value=_MockDB({"cleaning_checklist_templates": _MockTable([tmpl])})), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get("/properties/prop-1/cleaning-checklist", headers=_auth_header())
        assert resp.status_code == 200
        assert resp.json()["source"] == "property"

    def test_get_template_fallback_to_default(self):
        with patch("api.cleaning_task_router._get_supabase_client", return_value=_MockDB()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get("/properties/prop-1/cleaning-checklist", headers=_auth_header())
        assert resp.status_code == 200
        assert resp.json()["source"] == "default"


# ===========================================================================
# Phase 627 — Default Template Seeder
# ===========================================================================

class TestDefaultSeeder:

    def test_default_template_structure(self):
        from tasks.cleaning_template_seeder import get_default_template
        tmpl = get_default_template()
        assert "items" in tmpl
        assert "supply_checks" in tmpl
        assert len(tmpl["items"]) > 10
        assert len(tmpl["supply_checks"]) >= 5

    def test_default_template_has_thai(self):
        from tasks.cleaning_template_seeder import get_default_template
        tmpl = get_default_template()
        for item in tmpl["items"]:
            assert "label_th" in item
            assert len(item["label_th"]) > 0

    def test_rooms_requiring_photos(self):
        from tasks.cleaning_template_seeder import get_rooms_requiring_photos
        rooms = get_rooms_requiring_photos()
        assert len(rooms) >= 3
        assert "bedroom_1" in rooms
        assert "bathroom_1" in rooms


# ===========================================================================
# Phase 628 — Cleaning Progress: Start Cleaning
# ===========================================================================

class TestStartCleaning:

    def test_start_cleaning_success(self):
        db = _task_db({"cleaning_task_progress": _MockTable(), "cleaning_checklist_templates": _MockTable([{
            "id": "tmpl-1", "items": [{"room": "bed", "label": "Sheets", "requires_photo": True}],
            "supply_checks": [{"item": "sheets", "label": "Sheets ok?"}],
        }])})
        with patch("api.cleaning_task_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/tasks/abc123/start-cleaning",
                json={"worker_id": "WRK-001"},
                headers=_auth_header(),
            )
        assert resp.status_code == 200
        assert resp.json()["started"] is True

    def test_start_cleaning_missing_worker_id(self):
        with patch("api.cleaning_task_router._get_supabase_client", return_value=_task_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/tasks/abc123/start-cleaning",
                json={},
                headers=_auth_header(),
            )
        assert resp.status_code == 400

    def test_start_cleaning_task_not_found(self):
        with patch("api.cleaning_task_router._get_supabase_client", return_value=_MockDB({"tasks": _MockTable()})), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/tasks/missing/start-cleaning",
                json={"worker_id": "WRK-001"},
                headers=_auth_header(),
            )
        assert resp.status_code == 404

    def test_start_cleaning_already_started(self):
        db = _task_db({"cleaning_task_progress": _MockTable([_progress_row()])})
        with patch("api.cleaning_task_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/tasks/abc123/start-cleaning",
                json={"worker_id": "WRK-001"},
                headers=_auth_header(),
            )
        assert resp.status_code == 409


# ===========================================================================
# Phase 628 — Cleaning Progress: Update
# ===========================================================================

class TestUpdateProgress:

    def test_update_progress(self):
        db = _MockDB({"cleaning_task_progress": _MockTable([_progress_row()])})
        with patch("api.cleaning_task_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().patch(
                "/tasks/abc123/cleaning-progress",
                json={"items": [{"index": 0, "done": True}, {"index": 1, "done": True}]},
                headers=_auth_header(),
            )
        assert resp.status_code == 200
        assert resp.json()["items_completed"] == 2

    def test_update_progress_all_done(self):
        db = _MockDB({"cleaning_task_progress": _MockTable([_progress_row()])})
        with patch("api.cleaning_task_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().patch(
                "/tasks/abc123/cleaning-progress",
                json={"items": [{"index": 0, "done": True}, {"index": 1, "done": True}, {"index": 2, "done": True}]},
                headers=_auth_header(),
            )
        assert resp.status_code == 200
        assert resp.json()["all_items_done"] is True

    def test_update_progress_not_found(self):
        with patch("api.cleaning_task_router._get_supabase_client", return_value=_MockDB()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().patch(
                "/tasks/missing/cleaning-progress",
                json={"items": [{"index": 0, "done": True}]},
                headers=_auth_header(),
            )
        assert resp.status_code == 404

    def test_update_progress_invalid_body(self):
        with patch("api.cleaning_task_router._get_supabase_client", return_value=_MockDB({"cleaning_task_progress": _MockTable([_progress_row()])})), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().patch(
                "/tasks/abc123/cleaning-progress",
                json={"items": "not a list"},
                headers=_auth_header(),
            )
        assert resp.status_code == 400


# ===========================================================================
# Phase 629 — Room Photo Upload
# ===========================================================================

class TestCleaningPhotos:

    def test_add_photo(self):
        db = _MockDB({
            "cleaning_task_progress": _MockTable([_progress_row()]),
            "cleaning_photos": _MockTable(),
        })
        with patch("api.cleaning_task_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/tasks/abc123/cleaning-photos",
                json={"room_label": "bedroom_1", "photo_url": "https://storage.example.com/img.jpg", "taken_by": "WRK-001"},
                headers=_auth_header(),
            )
        assert resp.status_code == 201
        assert resp.json()["saved"] is True

    def test_add_photo_missing_fields(self):
        with patch("api.cleaning_task_router._get_supabase_client", return_value=_MockDB({"cleaning_task_progress": _MockTable([_progress_row()])})), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/tasks/abc123/cleaning-photos",
                json={"room_label": "bedroom_1"},
                headers=_auth_header(),
            )
        assert resp.status_code == 400

    def test_add_photo_no_progress(self):
        with patch("api.cleaning_task_router._get_supabase_client", return_value=_MockDB()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/tasks/missing/cleaning-photos",
                json={"room_label": "bed", "photo_url": "https://x.com/i.jpg"},
                headers=_auth_header(),
            )
        assert resp.status_code == 404


# ===========================================================================
# Phase 630 — Supply Check
# ===========================================================================

class TestSupplyCheck:

    def test_update_supply_check(self):
        db = _MockDB({"cleaning_task_progress": _MockTable([_progress_row()])})
        with patch("api.cleaning_task_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().patch(
                "/tasks/abc123/supply-check",
                json={"supplies": [{"index": 0, "status": "ok"}, {"index": 1, "status": "ok"}]},
                headers=_auth_header(),
            )
        assert resp.status_code == 200
        assert resp.json()["all_supplies_ok"] is True
        assert resp.json()["supply_alert"] is False

    def test_supply_check_empty_alert(self):
        db = _MockDB({"cleaning_task_progress": _MockTable([_progress_row()])})
        with patch("api.cleaning_task_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().patch(
                "/tasks/abc123/supply-check",
                json={"supplies": [{"index": 0, "status": "ok"}, {"index": 1, "status": "empty"}]},
                headers=_auth_header(),
            )
        assert resp.status_code == 200
        assert resp.json()["supply_alert"] is True
        assert "towels" in resp.json()["empty_items"]

    def test_supply_check_invalid_status(self):
        db = _MockDB({"cleaning_task_progress": _MockTable([_progress_row()])})
        with patch("api.cleaning_task_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().patch(
                "/tasks/abc123/supply-check",
                json={"supplies": [{"index": 0, "status": "broken"}]},
                headers=_auth_header(),
            )
        assert resp.status_code == 400


# ===========================================================================
# Phase 631 — Cleaning Complete Blocking
# ===========================================================================

class TestCompleteBlocking:

    def test_complete_all_conditions_met(self):
        p = _progress_row()
        p["all_items_done"] = True
        p["all_photos_taken"] = True
        p["all_supplies_ok"] = True
        db = _MockDB({"cleaning_task_progress": _MockTable([p]), "tasks": _MockTable([{"task_id": "abc123"}])})
        with patch("api.cleaning_task_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/tasks/abc123/complete-cleaning",
                json={},
                headers=_auth_header(),
            )
        assert resp.status_code == 200
        assert resp.json()["completed"] is True

    def test_complete_blocked_photos_missing(self):
        p = _progress_row()
        p["all_items_done"] = True
        p["all_photos_taken"] = False
        p["all_supplies_ok"] = True
        db = _MockDB({"cleaning_task_progress": _MockTable([p])})
        with patch("api.cleaning_task_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/tasks/abc123/complete-cleaning",
                json={},
                headers=_auth_header(),
            )
        assert resp.status_code == 409
        assert "photos_missing" in resp.json()["blockers"]

    def test_complete_blocked_items_incomplete(self):
        p = _progress_row()
        p["all_items_done"] = False
        p["all_photos_taken"] = True
        p["all_supplies_ok"] = True
        db = _MockDB({"cleaning_task_progress": _MockTable([p])})
        with patch("api.cleaning_task_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/tasks/abc123/complete-cleaning",
                json={},
                headers=_auth_header(),
            )
        assert resp.status_code == 409
        assert "checklist_incomplete" in resp.json()["blockers"]

    def test_complete_force_ignores_supplies(self):
        p = _progress_row()
        p["all_items_done"] = True
        p["all_photos_taken"] = True
        p["all_supplies_ok"] = False
        db = _MockDB({"cleaning_task_progress": _MockTable([p]), "tasks": _MockTable([{"task_id": "abc123"}])})
        with patch("api.cleaning_task_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/tasks/abc123/complete-cleaning",
                json={"force_complete": True},
                headers=_auth_header(),
            )
        assert resp.status_code == 200
        assert resp.json()["completed"] is True

    def test_complete_no_progress(self):
        with patch("api.cleaning_task_router._get_supabase_client", return_value=_MockDB()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/tasks/missing/complete-cleaning",
                json={},
                headers=_auth_header(),
            )
        assert resp.status_code == 404


# ===========================================================================
# Phase 632 — Reference vs Cleaning Photos
# ===========================================================================

class TestReferenceComparison:

    def test_comparison_view(self):
        progress = _progress_row()
        ref_photos = [
            {"room_label": "bedroom_1", "photo_url": "https://ref/bed.jpg"},
            {"room_label": "kitchen", "photo_url": "https://ref/kitchen.jpg"},
        ]
        clean_photos = [
            {"room_label": "bedroom_1", "photo_url": "https://clean/bed.jpg"},
        ]
        db = _MockDB({
            "cleaning_task_progress": _MockTable([progress]),
            "property_reference_photos": _MockTable(ref_photos),
            "cleaning_photos": _MockTable(clean_photos),
        })
        with patch("api.cleaning_task_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get("/tasks/abc123/reference-vs-cleaning", headers=_auth_header())
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["comparisons"]) >= 2

    def test_comparison_no_progress(self):
        with patch("api.cleaning_task_router._get_supabase_client", return_value=_MockDB()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get("/tasks/missing/reference-vs-cleaning", headers=_auth_header())
        assert resp.status_code == 404


# ===========================================================================
# Phase 633 — Task Navigate to Property
# ===========================================================================

class TestTaskNavigate:

    def test_navigate_success(self):
        with patch("tasks.task_router._get_supabase_client", return_value=_task_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get("/tasks/abc123/navigate", headers=_auth_header())
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_gps"] is True
        assert body["latitude"] == 13.756
        assert "maps.google.com" in body["map_url"]

    def test_navigate_task_not_found(self):
        with patch("tasks.task_router._get_supabase_client", return_value=_MockDB({"tasks": _MockTable()})), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get("/tasks/missing/navigate", headers=_auth_header())
        assert resp.status_code == 404

    def test_navigate_no_gps(self):
        prop_no_gps = {
            "property_id": "prop-1", "tenant_id": _TENANT,
            "display_name": "Villa", "latitude": None, "longitude": None,
        }
        db = _MockDB({
            "tasks": _MockTable([{"task_id": "abc123", "property_id": "prop-1"}]),
            "properties": _MockTable([prop_no_gps]),
        })
        with patch("tasks.task_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get("/tasks/abc123/navigate", headers=_auth_header())
        assert resp.status_code == 200
        assert resp.json()["has_gps"] is False


# ===========================================================================
# Phase 634 — CHECKOUT_VERIFY Auto-Created
# ===========================================================================

class TestCheckoutVerifyAutoCreated:

    def test_booking_created_emits_3_tasks(self):
        from tasks.task_automator import tasks_for_booking_created
        tasks = tasks_for_booking_created(
            tenant_id="t1", booking_id="b1", property_id="p1",
            check_in="2026-04-01", check_out="2026-04-05",
            created_at="2026-03-14T00:00:00Z",
        )
        assert len(tasks) == 3
        kinds = [t.kind.value for t in tasks]
        assert "CHECKIN_PREP" in kinds
        assert "CLEANING" in kinds
        assert "CHECKOUT_VERIFY" in kinds

    def test_checkout_verify_due_date(self):
        from tasks.task_automator import tasks_for_booking_created
        tasks = tasks_for_booking_created(
            tenant_id="t1", booking_id="b1", property_id="p1",
            check_in="2026-04-01", check_out="2026-04-05",
            created_at="2026-03-14T00:00:00Z",
        )
        co = [t for t in tasks if t.kind.value == "CHECKOUT_VERIFY"][0]
        assert co.due_date == "2026-04-05"

    def test_no_checkout_without_check_out(self):
        from tasks.task_automator import tasks_for_booking_created
        tasks = tasks_for_booking_created(
            tenant_id="t1", booking_id="b1", property_id="p1",
            check_in="2026-04-01",
            created_at="2026-03-14T00:00:00Z",
        )
        assert len(tasks) == 2  # backward compatible

    def test_amended_reschedules_checkout_verify(self):
        from tasks.task_automator import actions_for_booking_amended
        from tasks.task_model import Task, TaskKind, TaskPriority
        cv = Task.build(
            kind=TaskKind.CHECKOUT_VERIFY, tenant_id="t1",
            booking_id="b1", property_id="p1",
            due_date="2026-04-05", title="Checkout verify",
            created_at="2026-03-14T00:00:00Z",
        )
        actions = actions_for_booking_amended(
            booking_id="b1", new_check_in="2026-04-01",
            existing_tasks=[cv], new_check_out="2026-04-07",
        )
        assert len(actions) == 1
        assert actions[0].new_due_date == "2026-04-07"


# ===========================================================================
# Phase 635 — Worker Calendar
# ===========================================================================

class TestWorkerCalendar:

    def test_calendar_returns_grouped(self):
        tasks = [
            {"task_id": "t1", "kind": "CLEANING", "status": "PENDING", "priority": "MEDIUM",
             "property_id": "p1", "booking_id": "b1", "due_date": "2026-04-01", "title": "Clean", "urgency": "normal"},
            {"task_id": "t2", "kind": "CHECKIN_PREP", "status": "PENDING", "priority": "HIGH",
             "property_id": "p1", "booking_id": "b1", "due_date": "2026-04-02", "title": "Prep", "urgency": "urgent"},
            {"task_id": "t3", "kind": "CLEANING", "status": "COMPLETED", "priority": "LOW",
             "property_id": "p2", "booking_id": "b2", "due_date": "2026-04-01", "title": "Done", "urgency": "normal"},
        ]
        db = _MockDB({"tasks": _MockTable(tasks)})
        with patch("api.worker_calendar_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get("/workers/WRK-001/calendar", headers=_auth_header())
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_tasks"] == 2  # COMPLETED filtered out

    def test_today_tasks(self):
        from datetime import date
        today = date.today().isoformat()
        tasks = [
            {"task_id": "t1", "kind": "CLEANING", "status": "PENDING", "priority": "MEDIUM",
             "property_id": "p1", "booking_id": "b1", "due_date": today, "title": "Today clean", "urgency": "normal"},
        ]
        db = _MockDB({"tasks": _MockTable(tasks)})
        with patch("api.worker_calendar_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(f"/workers/WRK-001/tasks/today", headers=_auth_header())
        assert resp.status_code == 200
        assert resp.json()["count"] == 1


# ===========================================================================
# Phase 644 — Edge: No template → uses global fallback
# ===========================================================================

class TestEdgeNoTemplate:

    def test_start_cleaning_uses_default_when_no_template(self):
        """When no property-specific template exists, default seeder template is used."""
        db = _task_db({
            "cleaning_task_progress": _MockTable(),
            "cleaning_checklist_templates": _MockTable(),  # empty = no template found
        })
        with patch("api.cleaning_task_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/tasks/abc123/start-cleaning",
                json={"worker_id": "WRK-001"},
                headers=_auth_header(),
            )
        assert resp.status_code == 200
        # Default template has 21 items
        assert resp.json()["checklist_items"] > 10


# ===========================================================================
# Phase 645 — Edge: Worker has multiple tasks same day
# ===========================================================================

class TestEdgeMultipleTasks:

    def test_worker_multiple_tasks_same_day(self):
        from datetime import date
        today = date.today().isoformat()
        tasks = [
            {"task_id": "t1", "kind": "CLEANING", "status": "PENDING", "priority": "MEDIUM",
             "property_id": "p1", "booking_id": "b1", "due_date": today, "title": "Clean p1", "urgency": "normal"},
            {"task_id": "t2", "kind": "CHECKIN_PREP", "status": "PENDING", "priority": "HIGH",
             "property_id": "p2", "booking_id": "b2", "due_date": today, "title": "Prep p2", "urgency": "urgent"},
            {"task_id": "t3", "kind": "MAINTENANCE", "status": "ACKNOWLEDGED", "priority": "CRITICAL",
             "property_id": "p3", "booking_id": "b3", "due_date": today, "title": "Fix p3", "urgency": "critical"},
        ]
        db = _MockDB({"tasks": _MockTable(tasks)})
        with patch("api.worker_calendar_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(f"/workers/WRK-001/tasks/today", headers=_auth_header())
        assert resp.status_code == 200
        assert resp.json()["count"] == 3
