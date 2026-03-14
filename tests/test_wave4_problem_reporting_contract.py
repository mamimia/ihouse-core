"""
Phases 653–660 — Wave 4 Problem Reporting Contract & E2E Tests

Tests for:
    Phase 653: Contract — create, photo upload
    Phase 654: Contract — auto-maintenance task creation
    Phase 655: Contract — urgent → SSE alert
    Phase 656: Contract — list, filter, pagination
    Phase 657: E2E — report → auto task → SLA (conceptual)
    Phase 658: E2E — urgent report → admin dashboard alert
    Phase 659: Edge — problem without booking
    Phase 660: Edge — multiple photos per report
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch, call

import pytest
from fastapi.testclient import TestClient

import main

_TENANT = "tenant-wave4-test"


def _make_client() -> TestClient:
    return TestClient(main.app)


def _auth_header() -> dict:
    return {"Authorization": "Bearer mock-token"}


# ---------------------------------------------------------------------------
# Mock DB helpers
# ---------------------------------------------------------------------------

class _MockResult:
    def __init__(self, data=None, count=None):
        self.data = data or []
        self.count = count or 0


class _MockTable:
    def __init__(self, rows=None):
        self._rows = rows or []
        self._result = _MockResult(data=self._rows)
        self._inserts: list[dict] = []

    def select(self, *a, **kw): return self
    def eq(self, *a, **kw): return self
    def limit(self, *a): return self
    def order(self, *a, **kw): return self
    def insert(self, data):
        inserted = data if isinstance(data, dict) else data[0] if data else {}
        inserted = {**inserted, "id": "report-uuid-1"}
        self._inserts.append(inserted)
        self._result = _MockResult(data=[inserted])
        return self
    def upsert(self, data, **kw):
        self._result = _MockResult(data=[data] if isinstance(data, dict) else data)
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
        if name not in self._tables:
            self._tables[name] = _MockTable()
        return self._tables[name]


# ===========================================================================
# Phase 653 — Contract: Create & Photo Upload
# ===========================================================================

class TestCreateProblemReport:

    def test_create_report_success(self):
        db = _MockDB({
            "problem_reports": _MockTable(),
            "tasks": _MockTable(),
        })
        with patch("api.problem_report_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/problem-reports/",
                json={
                    "property_id": "prop-1",
                    "reported_by": "WRK-001",
                    "category": "pool",
                    "description": "Pool pump not working",
                    "priority": "normal",
                },
                headers=_auth_header(),
            )
        assert resp.status_code == 201
        body = resp.json()
        assert body["category"] == "pool"
        assert body["status"] == "open"

    def test_create_report_missing_property_id(self):
        with patch("api.problem_report_router._get_supabase_client", return_value=_MockDB()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/problem-reports/",
                json={"reported_by": "WRK-001", "category": "pool", "description": "x"},
                headers=_auth_header(),
            )
        assert resp.status_code == 400

    def test_create_report_invalid_category(self):
        with patch("api.problem_report_router._get_supabase_client", return_value=_MockDB()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/problem-reports/",
                json={"property_id": "p1", "reported_by": "WRK-001", "category": "aliens", "description": "x"},
                headers=_auth_header(),
            )
        assert resp.status_code == 400

    def test_create_report_missing_description(self):
        with patch("api.problem_report_router._get_supabase_client", return_value=_MockDB()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/problem-reports/",
                json={"property_id": "p1", "reported_by": "WRK-001", "category": "pool"},
                headers=_auth_header(),
            )
        assert resp.status_code == 400


class TestPhotoUpload:

    def test_add_photo_success(self):
        db = _MockDB({"problem_report_photos": _MockTable()})
        with patch("api.problem_report_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/problem-reports/report-1/photos",
                json={"photo_url": "https://storage.example.com/img.jpg", "caption": "Pool damage"},
                headers=_auth_header(),
            )
        assert resp.status_code == 201

    def test_add_photo_missing_url(self):
        with patch("api.problem_report_router._get_supabase_client", return_value=_MockDB()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/problem-reports/report-1/photos",
                json={"caption": "No URL"},
                headers=_auth_header(),
            )
        assert resp.status_code == 400


# ===========================================================================
# Phase 654 — Contract: Auto-create maintenance task
# ===========================================================================

class TestAutoMaintenanceTask:

    def test_urgent_creates_critical_task(self):
        tasks_table = _MockTable()
        db = _MockDB({
            "problem_reports": _MockTable(),
            "tasks": tasks_table,
        })
        with patch("api.problem_report_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/problem-reports/",
                json={
                    "property_id": "prop-1",
                    "reported_by": "WRK-001",
                    "category": "electrical",
                    "description": "Main breaker tripped",
                    "priority": "urgent",
                },
                headers=_auth_header(),
            )
        assert resp.status_code == 201
        # Verify task was inserted
        body = resp.json()
        assert body.get("maintenance_task_id") is not None

    def test_normal_creates_medium_task(self):
        tasks_table = _MockTable()
        db = _MockDB({
            "problem_reports": _MockTable(),
            "tasks": tasks_table,
        })
        with patch("api.problem_report_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/problem-reports/",
                json={
                    "property_id": "prop-1",
                    "reported_by": "WRK-001",
                    "category": "plumbing",
                    "description": "Slow drain in bathroom",
                    "priority": "normal",
                },
                headers=_auth_header(),
            )
        assert resp.status_code == 201
        body = resp.json()
        assert body.get("maintenance_task_id") is not None

    def test_auto_task_uses_correct_priority(self):
        """Verify the internal function builds correct task priorities."""
        from api.problem_report_router import _auto_create_maintenance_task
        db = _MockDB({"tasks": _MockTable()})
        task_id = _auto_create_maintenance_task(
            db, "t1", "p1", "booking-1", "report-1",
            "pool", "urgent", "Pool is broken",
        )
        assert task_id is not None
        # Verify the inserted task had CRITICAL priority
        inserted = db._tables["tasks"]._inserts[0]
        assert inserted["priority"] == "CRITICAL"
        assert inserted["ack_sla_minutes"] == 5

    def test_auto_task_normal_has_medium_priority(self):
        from api.problem_report_router import _auto_create_maintenance_task
        db = _MockDB({"tasks": _MockTable()})
        task_id = _auto_create_maintenance_task(
            db, "t1", "p1", None, "report-2",
            "furniture", "normal", "Chair broken",
        )
        assert task_id is not None
        inserted = db._tables["tasks"]._inserts[0]
        assert inserted["priority"] == "MEDIUM"
        assert inserted["ack_sla_minutes"] == 60


# ===========================================================================
# Phase 655 — Contract: Urgent → SSE alert
# ===========================================================================

class TestUrgentSSEAlert:

    def test_urgent_emits_sse(self):
        db = _MockDB({
            "problem_reports": _MockTable(),
            "tasks": _MockTable(),
        })
        with patch("api.problem_report_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT), \
             patch("api.problem_report_router._emit_urgent_sse_alert") as mock_sse:
            resp = _make_client().post(
                "/problem-reports/",
                json={
                    "property_id": "prop-1",
                    "reported_by": "WRK-001",
                    "category": "security",
                    "description": "Door lock broken",
                    "priority": "urgent",
                },
                headers=_auth_header(),
            )
        assert resp.status_code == 201
        mock_sse.assert_called_once()
        call_kwargs = mock_sse.call_args
        assert call_kwargs[1].get("category") or call_kwargs[0][3] == "security"

    def test_normal_does_not_emit_sse(self):
        db = _MockDB({
            "problem_reports": _MockTable(),
            "tasks": _MockTable(),
        })
        with patch("api.problem_report_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT), \
             patch("api.problem_report_router._emit_urgent_sse_alert") as mock_sse:
            resp = _make_client().post(
                "/problem-reports/",
                json={
                    "property_id": "prop-1",
                    "reported_by": "WRK-001",
                    "category": "plumbing",
                    "description": "Slow drain",
                    "priority": "normal",
                },
                headers=_auth_header(),
            )
        assert resp.status_code == 201
        mock_sse.assert_not_called()


# ===========================================================================
# Phase 656 — Contract: List, filter
# ===========================================================================

class TestListAndFilter:

    def test_list_reports(self):
        reports = [
            {"id": "r1", "property_id": "p1", "category": "pool", "status": "open", "priority": "normal",
             "created_at": "2026-03-14T00:00:00Z"},
            {"id": "r2", "property_id": "p1", "category": "plumbing", "status": "resolved", "priority": "urgent",
             "created_at": "2026-03-13T00:00:00Z"},
        ]
        db = _MockDB({"problem_reports": _MockTable(reports)})
        with patch("api.problem_report_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get("/problem-reports/?property_id=p1", headers=_auth_header())
        assert resp.status_code == 200
        assert resp.json()["count"] == 2

    def test_list_filter_by_status(self):
        reports = [{"id": "r1", "status": "open", "property_id": "p1"}]
        db = _MockDB({"problem_reports": _MockTable(reports)})
        with patch("api.problem_report_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get("/problem-reports/?status=open", headers=_auth_header())
        assert resp.status_code == 200

    def test_list_filter_by_priority(self):
        reports = [{"id": "r1", "priority": "urgent", "property_id": "p1"}]
        db = _MockDB({"problem_reports": _MockTable(reports)})
        with patch("api.problem_report_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get("/problem-reports/?priority=urgent", headers=_auth_header())
        assert resp.status_code == 200

    def test_get_single_report(self):
        db = _MockDB({"problem_reports": _MockTable([{
            "id": "r1", "property_id": "p1", "category": "pool",
            "status": "open", "priority": "normal",
        }])})
        with patch("api.problem_report_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get("/problem-reports/r1", headers=_auth_header())
        assert resp.status_code == 200

    def test_get_report_not_found(self):
        db = _MockDB({"problem_reports": _MockTable()})
        with patch("api.problem_report_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get("/problem-reports/missing", headers=_auth_header())
        assert resp.status_code == 404

    def test_list_photos(self):
        photos = [
            {"id": "ph1", "report_id": "r1", "photo_url": "https://a.jpg"},
            {"id": "ph2", "report_id": "r1", "photo_url": "https://b.jpg"},
        ]
        db = _MockDB({"problem_report_photos": _MockTable(photos)})
        with patch("api.problem_report_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get("/problem-reports/r1/photos", headers=_auth_header())
        assert resp.status_code == 200
        assert resp.json()["count"] == 2


# ===========================================================================
# Phase 657 — E2E: Report → auto task → SLA (conceptual)
# ===========================================================================

class TestE2EReportToTask:

    def test_full_flow_report_to_task(self):
        """Create report → auto-creates task → verify task has SLA."""
        from api.problem_report_router import _auto_create_maintenance_task
        db = _MockDB({"tasks": _MockTable()})

        task_id = _auto_create_maintenance_task(
            db, "t1", "prop-1", "booking-1", "report-1",
            "ac_heating", "urgent", "AC completely dead in guest room",
        )

        assert task_id is not None
        inserted = db._tables["tasks"]._inserts[0]
        assert inserted["kind"] == "MAINTENANCE"
        assert inserted["priority"] == "CRITICAL"
        assert inserted["ack_sla_minutes"] == 5  # 5-min ACK SLA!
        assert inserted["worker_role"] == "MAINTENANCE_TECH"
        assert inserted["status"] == "PENDING"

    def test_full_flow_normal_priority(self):
        from api.problem_report_router import _auto_create_maintenance_task
        db = _MockDB({"tasks": _MockTable()})

        task_id = _auto_create_maintenance_task(
            db, "t1", "prop-1", "booking-1", "report-2",
            "cleanliness", "normal", "Guest found stain on carpet",
        )

        assert task_id is not None
        inserted = db._tables["tasks"]._inserts[0]
        assert inserted["priority"] == "MEDIUM"
        assert inserted["ack_sla_minutes"] == 60


# ===========================================================================
# Phase 658 — E2E: Urgent report → admin dashboard alert
# ===========================================================================

class TestE2EUrgentAlert:

    def test_sse_emit_called_with_correct_data(self):
        """Direct test of the SSE alert function."""
        with patch("channels.sse_broker.broker") as mock_broker:
            from api.problem_report_router import _emit_urgent_sse_alert
            _emit_urgent_sse_alert("t1", "report-123", "prop-1", "electrical", "Power outage")
            mock_broker.publish_alert.assert_called_once_with(
                tenant_id="t1",
                event_type="PROBLEM_URGENT",
                report_id="report-123",
                property_id="prop-1",
                category="electrical",
                description="Power outage",
            )


# ===========================================================================
# Phase 659 — Edge: Problem without booking
# ===========================================================================

class TestEdgeNoBooKing:

    def test_create_report_without_booking(self):
        db = _MockDB({
            "problem_reports": _MockTable(),
            "tasks": _MockTable(),
        })
        with patch("api.problem_report_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/problem-reports/",
                json={
                    "property_id": "prop-standalone",
                    "reported_by": "MGR-001",
                    "category": "garden_outdoor",
                    "description": "Tree fell in yard during storm",
                    "priority": "normal",
                    # no booking_id!
                },
                headers=_auth_header(),
            )
        assert resp.status_code == 201
        body = resp.json()
        assert body.get("booking_id") is None
        # Task should still be created (with synthetic booking_id)
        assert body.get("maintenance_task_id") is not None

    def test_auto_task_uses_report_prefix_when_no_booking(self):
        from api.problem_report_router import _auto_create_maintenance_task
        db = _MockDB({"tasks": _MockTable()})
        task_id = _auto_create_maintenance_task(
            db, "t1", "p1", None, "abcdef12-3456",
            "pest", "normal", "Found ants",
        )
        assert task_id is not None
        inserted = db._tables["tasks"]._inserts[0]
        assert inserted["booking_id"].startswith("report_")


# ===========================================================================
# Phase 660 — Edge: Multiple photos per report
# ===========================================================================

class TestEdgeMultiplePhotos:

    def test_add_multiple_photos(self):
        db = _MockDB({"problem_report_photos": _MockTable()})
        with patch("api.problem_report_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            # Add 3 photos to the same report
            for i in range(3):
                resp = _make_client().post(
                    "/problem-reports/report-multi/photos",
                    json={"photo_url": f"https://storage.example.com/img_{i}.jpg", "caption": f"Photo {i}"},
                    headers=_auth_header(),
                )
                assert resp.status_code == 201

    def test_list_multiple_photos(self):
        photos = [
            {"id": f"ph{i}", "report_id": "r1", "photo_url": f"https://example.com/{i}.jpg"}
            for i in range(5)
        ]
        db = _MockDB({"problem_report_photos": _MockTable(photos)})
        with patch("api.problem_report_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get("/problem-reports/r1/photos", headers=_auth_header())
        assert resp.status_code == 200
        assert resp.json()["count"] == 5


# ===========================================================================
# Phase 650 — Status update + audit event
# ===========================================================================

class TestStatusUpdateAudit:

    def test_resolve_report(self):
        report = {"id": "r1", "status": "open", "tenant_id": _TENANT}
        db = _MockDB({"problem_reports": _MockTable([report]), "audit_events": _MockTable()})
        with patch("api.problem_report_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().patch(
                "/problem-reports/r1",
                json={"status": "resolved", "resolved_by": "MGR-001", "resolution_notes": "Fixed pump"},
                headers=_auth_header(),
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "resolved"

    def test_invalid_status_rejected(self):
        report = {"id": "r1", "status": "open", "tenant_id": _TENANT}
        db = _MockDB({"problem_reports": _MockTable([report])})
        with patch("api.problem_report_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().patch(
                "/problem-reports/r1",
                json={"status": "magic"},
                headers=_auth_header(),
            )
        assert resp.status_code == 400

    def test_dismiss_report(self):
        report = {"id": "r1", "status": "open", "tenant_id": _TENANT}
        db = _MockDB({"problem_reports": _MockTable([report]), "audit_events": _MockTable()})
        with patch("api.problem_report_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().patch(
                "/problem-reports/r1",
                json={"status": "dismissed"},
                headers=_auth_header(),
            )
        assert resp.status_code == 200

    def test_update_not_found(self):
        db = _MockDB({"problem_reports": _MockTable()})
        with patch("api.problem_report_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().patch(
                "/problem-reports/missing-id",
                json={"status": "resolved"},
                headers=_auth_header(),
            )
        assert resp.status_code == 404


# ===========================================================================
# Phase 652 — i18n labels
# ===========================================================================

class TestI18nLabels:

    def test_all_categories_have_all_languages(self):
        from i18n.problem_report_labels import PROBLEM_CATEGORIES
        for key, cat in PROBLEM_CATEGORIES.items():
            assert "en" in cat, f"Missing 'en' for {key}"
            assert "th" in cat, f"Missing 'th' for {key}"
            assert "he" in cat, f"Missing 'he' for {key}"
            assert "icon" in cat, f"Missing 'icon' for {key}"

    def test_get_category_label_en(self):
        from i18n.problem_report_labels import get_category_label
        assert get_category_label("pool", "en") == "Pool"

    def test_get_category_label_th(self):
        from i18n.problem_report_labels import get_category_label
        label = get_category_label("pool", "th")
        assert "สระ" in label

    def test_get_category_label_he(self):
        from i18n.problem_report_labels import get_category_label
        label = get_category_label("pool", "he")
        assert "בריכה" in label

    def test_get_category_label_unknown_lang(self):
        from i18n.problem_report_labels import get_category_label
        assert get_category_label("pool", "fr") == "Pool"  # falls back to en

    def test_get_category_label_unknown_category(self):
        from i18n.problem_report_labels import get_category_label
        assert get_category_label("unicorn", "en") == "Unicorn"

    def test_get_all_categories(self):
        from i18n.problem_report_labels import get_all_categories
        cats = get_all_categories("en")
        assert len(cats) == 14

    def test_get_category_icon(self):
        from i18n.problem_report_labels import get_category_icon
        assert get_category_icon("pool") == "🏊"
        assert get_category_icon("unknown") == "❓"

    def test_get_category_specialty(self):
        from i18n.problem_report_labels import get_category_specialty
        assert get_category_specialty("pool") == "pool"
        assert get_category_specialty("plumbing") == "plumbing"
        assert get_category_specialty("unknown") == "general"
