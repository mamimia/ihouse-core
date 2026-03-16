"""
Phase E — Mobile Cleaner Flow — Contract Tests
================================================

Groups:
    A — Task list endpoint: returns CLEANING tasks with filters
    B — Start-cleaning: creates progress record
    C — Checklist progress: marks items done, recalculates all_items_done
    D — Photo upload: recalculates all_photos_taken
    E — Supply check: recalculates all_supplies_ok
    F — Complete-cleaning: blocks when pre-conditions not met (409)
    G — Complete-cleaning: succeeds when all conditions met (200)
    H — Frontend file structure test
    I — Security: cleaner visibility invariants

CI-safe: pure in-memory tests using mock DB.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("IHOUSE_ENV", "test")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

pytest.importorskip("fastapi")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.cleaning_task_router import router as cleaning_router
from tasks.task_router import router as task_router
from api.auth import jwt_auth


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

TENANT = "t-test"
TASK_ID = "task-clean-001"
PROPERTY_ID = "prop-villa-01"
BOOKING_ID = "booking-001"


def _make_app(tenant_id: str = TENANT) -> TestClient:
    app = FastAPI()

    async def _stub_auth():
        return tenant_id

    app.dependency_overrides[jwt_auth] = _stub_auth
    app.include_router(cleaning_router)
    app.include_router(task_router)
    return TestClient(app, raise_server_exceptions=False)


def _make_task_db(tasks: list | None = None) -> MagicMock:
    """DB mock for GET /tasks — returns task list."""
    db = MagicMock()
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=tasks or [])
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    db.table.return_value = chain
    return db


def _sample_task(status: str = "PENDING", kind: str = "CLEANING") -> dict:
    return {
        "task_id": TASK_ID,
        "tenant_id": TENANT,
        "property_id": PROPERTY_ID,
        "booking_id": BOOKING_ID,
        "kind": kind,
        "status": status,
        "title": "Standard Cleaning",
        "due_date": "2026-03-16",
        "created_at": "2026-03-16T10:00:00Z",
        "updated_at": "2026-03-16T10:00:00Z",
        "priority": "NORMAL",
        "urgency": "ROUTINE",
        "worker_role": "CLEANER",
        "ack_sla_minutes": 30,
        "description": "Post check-out cleaning",
        "notes": None,
        "canceled_reason": None,
    }


def _make_progress_db(
    *,
    task_exists: bool = True,
    progress_exists: bool = True,
    all_items_done: bool = False,
    all_photos_taken: bool = False,
    all_supplies_ok: bool = False,
    completed_at: str | None = None,
) -> MagicMock:
    """DB mock for cleaning endpoints."""
    db = MagicMock()

    task_chain = MagicMock()
    task_chain.execute.return_value = MagicMock(
        data=[_sample_task("IN_PROGRESS")] if task_exists else []
    )
    task_chain.select.return_value = task_chain
    task_chain.eq.return_value = task_chain
    task_chain.limit.return_value = task_chain

    progress_data = {
        "id": "progress-001",
        "task_id": TASK_ID,
        "tenant_id": TENANT,
        "booking_id": BOOKING_ID,
        "property_id": PROPERTY_ID,
        "checklist_state": [
            {"room": "bedroom", "label": "Bedroom", "done": all_items_done, "requires_photo": True},
            {"room": "bathroom", "label": "Bathroom", "done": all_items_done, "requires_photo": True},
        ],
        "supply_state": [
            {"item": "towels", "label": "Fresh Towels", "status": "ok" if all_supplies_ok else "unchecked"},
        ],
        "all_items_done": all_items_done,
        "all_photos_taken": all_photos_taken,
        "all_supplies_ok": all_supplies_ok,
        "completed_at": completed_at,
    }

    progress_chain = MagicMock()
    progress_chain.execute.return_value = MagicMock(
        data=[progress_data] if progress_exists else []
    )
    progress_chain.select.return_value = progress_chain
    progress_chain.eq.return_value = progress_chain
    progress_chain.limit.return_value = progress_chain

    # Insert / update chains
    insert_chain = MagicMock()
    insert_chain.execute.return_value = MagicMock(data=[{"id": "progress-001"}])
    insert_chain.insert.return_value = insert_chain

    update_chain = MagicMock()
    update_chain.execute.return_value = MagicMock(data=[progress_data])
    update_chain.update.return_value = update_chain
    update_chain.eq.return_value = update_chain

    # Template chain
    template_chain = MagicMock()
    template_chain.execute.return_value = MagicMock(data=[{
        "id": "tmpl-001",
        "items": [
            {"room": "bedroom", "label": "Bedroom", "requires_photo": True},
            {"room": "bathroom", "label": "Bathroom", "requires_photo": True},
        ],
        "supply_checks": [{"item": "towels", "label": "Fresh Towels"}],
    }])
    template_chain.select.return_value = template_chain
    template_chain.eq.return_value = template_chain
    template_chain.limit.return_value = template_chain

    # Photos chain
    photos_chain = MagicMock()
    photos_chain.execute.return_value = MagicMock(data=[
        {"room_label": "bedroom"}, {"room_label": "bathroom"},
    ] if all_photos_taken else [])
    photos_chain.select.return_value = photos_chain
    photos_chain.eq.return_value = photos_chain
    photos_chain.insert.return_value = photos_chain

    call_counts = {"n": 0}

    def table_side(name: str):
        call_counts["n"] += 1
        if name == "tasks":
            return MagicMock(
                select=lambda *a, **kw: task_chain,
                update=lambda d: update_chain,
            )
        if name == "cleaning_task_progress":
            return MagicMock(
                select=lambda *a, **kw: progress_chain,
                insert=lambda d: insert_chain,
                update=lambda d: update_chain,
            )
        if name == "cleaning_checklist_templates":
            return MagicMock(select=lambda *a, **kw: template_chain)
        if name == "cleaning_photos":
            return MagicMock(
                select=lambda *a, **kw: photos_chain,
                insert=lambda d: photos_chain,
            )
        return MagicMock()

    db.table.side_effect = table_side
    return db


# ===========================================================================
# Group A — Task list: CLEANING tasks with filters
# ===========================================================================

class TestGroupA_TaskList:

    def test_a1_returns_cleaning_tasks(self) -> None:
        """A1: GET /tasks with kind=CLEANING returns task list."""
        client = _make_app()
        db = _make_task_db([_sample_task()])
        with patch("tasks.task_router._get_supabase_client", return_value=db):
            resp = client.get("/tasks?kind=CLEANING")
        assert resp.status_code == 200
        body = resp.json()
        assert "tasks" in body
        assert isinstance(body["tasks"], list)

    def test_a2_filter_by_due_date(self) -> None:
        """A2: GET /tasks with due_date filter returns 200."""
        client = _make_app()
        db = _make_task_db([_sample_task()])
        with patch("tasks.task_router._get_supabase_client", return_value=db):
            resp = client.get("/tasks?kind=CLEANING&due_date=2026-03-16")
        assert resp.status_code == 200

    def test_a3_empty_task_list(self) -> None:
        """A3: No tasks returns empty list, not error."""
        client = _make_app()
        db = _make_task_db([])
        with patch("tasks.task_router._get_supabase_client", return_value=db):
            resp = client.get("/tasks?kind=CLEANING")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_a4_invalid_kind_returns_400(self) -> None:
        """A4: Invalid kind returns 400."""
        client = _make_app()
        db = _make_task_db()
        with patch("tasks.task_router._get_supabase_client", return_value=db):
            resp = client.get("/tasks?kind=INVALID_KIND")
        assert resp.status_code == 400


# ===========================================================================
# Group B — Start-cleaning creates progress
# ===========================================================================

class TestGroupB_StartCleaning:

    def test_b1_start_cleaning_returns_200(self) -> None:
        """B1: Starting a cleaning task returns 200."""
        client = _make_app()
        db = _make_progress_db(progress_exists=False)
        with patch("api.cleaning_task_router._get_supabase_client", return_value=db):
            resp = client.post(f"/tasks/{TASK_ID}/start-cleaning", json={"worker_id": "wrk-01"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["started"] is True

    def test_b2_start_requires_worker_id(self) -> None:
        """B2: Missing worker_id returns 400."""
        client = _make_app()
        db = _make_progress_db()
        with patch("api.cleaning_task_router._get_supabase_client", return_value=db):
            resp = client.post(f"/tasks/{TASK_ID}/start-cleaning", json={})
        assert resp.status_code == 400

    def test_b3_start_unknown_task_returns_404(self) -> None:
        """B3: Starting unknown task returns 404."""
        client = _make_app()
        db = _make_progress_db(task_exists=False)
        with patch("api.cleaning_task_router._get_supabase_client", return_value=db):
            resp = client.post("/tasks/ghost-task/start-cleaning", json={"worker_id": "wrk-01"})
        assert resp.status_code == 404

    def test_b4_duplicate_start_returns_409(self) -> None:
        """B4: Starting an already-started cleaning task returns 409."""
        client = _make_app()
        db = _make_progress_db(progress_exists=True)
        with patch("api.cleaning_task_router._get_supabase_client", return_value=db):
            resp = client.post(f"/tasks/{TASK_ID}/start-cleaning", json={"worker_id": "wrk-01"})
        assert resp.status_code == 409


# ===========================================================================
# Group C — Checklist progress update
# ===========================================================================

class TestGroupC_ChecklistProgress:

    def test_c1_update_progress_returns_200(self) -> None:
        """C1: Marking checklist item as done returns 200."""
        client = _make_app()
        db = _make_progress_db()
        with patch("api.cleaning_task_router._get_supabase_client", return_value=db):
            resp = client.patch(
                f"/tasks/{TASK_ID}/cleaning-progress",
                json={"items": [{"index": 0, "done": True}]},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["updated"] is True
        assert body["items_completed"] >= 0

    def test_c2_empty_items_returns_400(self) -> None:
        """C2: Empty items list returns 400."""
        client = _make_app()
        db = _make_progress_db()
        with patch("api.cleaning_task_router._get_supabase_client", return_value=db):
            resp = client.patch(f"/tasks/{TASK_ID}/cleaning-progress", json={"items": []})
        assert resp.status_code == 400

    def test_c3_no_progress_returns_404(self) -> None:
        """C3: Update on non-started task returns 404."""
        client = _make_app()
        db = _make_progress_db(progress_exists=False)
        with patch("api.cleaning_task_router._get_supabase_client", return_value=db):
            resp = client.patch(
                f"/tasks/{TASK_ID}/cleaning-progress",
                json={"items": [{"index": 0, "done": True}]},
            )
        assert resp.status_code == 404


# ===========================================================================
# Group D — Photo upload
# ===========================================================================

class TestGroupD_PhotoUpload:

    def test_d1_upload_photo_returns_201(self) -> None:
        """D1: Uploading room photo returns 201."""
        client = _make_app()
        db = _make_progress_db()
        with patch("api.cleaning_task_router._get_supabase_client", return_value=db):
            resp = client.post(
                f"/tasks/{TASK_ID}/cleaning-photos",
                json={"room_label": "bedroom", "photo_url": "https://cdn/bedroom.jpg", "taken_by": "wrk-01"},
            )
        assert resp.status_code == 201
        assert resp.json()["saved"] is True

    def test_d2_missing_fields_returns_400(self) -> None:
        """D2: Missing room_label or photo_url returns 400."""
        client = _make_app()
        db = _make_progress_db()
        with patch("api.cleaning_task_router._get_supabase_client", return_value=db):
            resp = client.post(f"/tasks/{TASK_ID}/cleaning-photos", json={"room_label": "bedroom"})
        assert resp.status_code == 400


# ===========================================================================
# Group E — Supply check
# ===========================================================================

class TestGroupE_SupplyCheck:

    def test_e1_update_supplies_returns_200(self) -> None:
        """E1: Updating supply status returns 200."""
        client = _make_app()
        db = _make_progress_db()
        with patch("api.cleaning_task_router._get_supabase_client", return_value=db):
            resp = client.patch(
                f"/tasks/{TASK_ID}/supply-check",
                json={"supplies": [{"index": 0, "status": "ok"}]},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["updated"] is True

    def test_e2_invalid_status_returns_400(self) -> None:
        """E2: Invalid supply status returns 400."""
        client = _make_app()
        db = _make_progress_db()
        with patch("api.cleaning_task_router._get_supabase_client", return_value=db):
            resp = client.patch(
                f"/tasks/{TASK_ID}/supply-check",
                json={"supplies": [{"index": 0, "status": "broken"}]},
            )
        assert resp.status_code == 400

    def test_e3_empty_supply_flags_alert(self) -> None:
        """E3: Supply status 'empty' triggers supply_alert flag."""
        client = _make_app()
        db = _make_progress_db()
        with patch("api.cleaning_task_router._get_supabase_client", return_value=db):
            resp = client.patch(
                f"/tasks/{TASK_ID}/supply-check",
                json={"supplies": [{"index": 0, "status": "empty"}]},
            )
        assert resp.status_code == 200
        assert resp.json()["supply_alert"] is True


# ===========================================================================
# Group F — Complete-cleaning: blocks when pre-conditions not met
# ===========================================================================

class TestGroupF_CompleteBlocked:

    def test_f1_incomplete_checklist_returns_409(self) -> None:
        """F1: Incomplete checklist → 409."""
        client = _make_app()
        db = _make_progress_db(all_items_done=False, all_photos_taken=True, all_supplies_ok=True)
        with patch("api.cleaning_task_router._get_supabase_client", return_value=db):
            resp = client.post(f"/tasks/{TASK_ID}/complete-cleaning", json={})
        assert resp.status_code == 409
        assert "checklist_incomplete" in resp.json().get("blockers", [])

    def test_f2_missing_photos_returns_409(self) -> None:
        """F2: Missing photos → 409."""
        client = _make_app()
        db = _make_progress_db(all_items_done=True, all_photos_taken=False, all_supplies_ok=True)
        with patch("api.cleaning_task_router._get_supabase_client", return_value=db):
            resp = client.post(f"/tasks/{TASK_ID}/complete-cleaning", json={})
        assert resp.status_code == 409
        assert "photos_missing" in resp.json().get("blockers", [])

    def test_f3_supplies_not_ok_returns_409(self) -> None:
        """F3: Supplies not checked → 409 (unless force_complete)."""
        client = _make_app()
        db = _make_progress_db(all_items_done=True, all_photos_taken=True, all_supplies_ok=False)
        with patch("api.cleaning_task_router._get_supabase_client", return_value=db):
            resp = client.post(f"/tasks/{TASK_ID}/complete-cleaning", json={})
        assert resp.status_code == 409
        assert "supplies_not_ok" in resp.json().get("blockers", [])

    def test_f4_force_complete_bypasses_supplies(self) -> None:
        """F4: force_complete=True bypasses supplies check."""
        client = _make_app()
        db = _make_progress_db(all_items_done=True, all_photos_taken=True, all_supplies_ok=False)
        with patch("api.cleaning_task_router._get_supabase_client", return_value=db):
            resp = client.post(f"/tasks/{TASK_ID}/complete-cleaning", json={"force_complete": True})
        assert resp.status_code == 200
        assert resp.json()["completed"] is True


# ===========================================================================
# Group G — Complete-cleaning: succeeds
# ===========================================================================

class TestGroupG_CompleteSuccess:

    def test_g1_all_conditions_met_returns_200(self) -> None:
        """G1: All pre-conditions met → 200."""
        client = _make_app()
        db = _make_progress_db(all_items_done=True, all_photos_taken=True, all_supplies_ok=True)
        with patch("api.cleaning_task_router._get_supabase_client", return_value=db):
            resp = client.post(f"/tasks/{TASK_ID}/complete-cleaning", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert body["completed"] is True
        assert body["task_id"] == TASK_ID
        assert "completed_at" in body

    def test_g2_no_progress_returns_404(self) -> None:
        """G2: Complete on non-started task → 404."""
        client = _make_app()
        db = _make_progress_db(progress_exists=False)
        with patch("api.cleaning_task_router._get_supabase_client", return_value=db):
            resp = client.post(f"/tasks/{TASK_ID}/complete-cleaning", json={})
        assert resp.status_code == 404


# ===========================================================================
# Group H — Frontend structure
# ===========================================================================

class TestGroupH_FrontendStructure:

    _ui = os.path.join(os.path.dirname(__file__), "..", "ihouse-ui")

    def _read(self, rel: str) -> str:
        path = os.path.join(self._ui, rel)
        with open(path) as f:
            return f.read()

    def test_h1_cleaner_page_exists(self) -> None:
        """H1: Cleaner page file exists at expected path."""
        path = os.path.join(self._ui, "app/(app)/ops/cleaner/page.tsx")
        assert os.path.isfile(path), f"Missing: {path}"

    def test_h2_cleaner_page_exports_default(self) -> None:
        """H2: Cleaner page exports a default function."""
        content = self._read("app/(app)/ops/cleaner/page.tsx")
        assert "export default" in content

    def test_h3_cleaner_page_has_use_client(self) -> None:
        """H3: Cleaner page is a client component."""
        content = self._read("app/(app)/ops/cleaner/page.tsx")
        assert "'use client'" in content

    def test_h4_cleaner_page_mentions_cleaning(self) -> None:
        """H4: Cleaner page contains 'cleaning' keyword."""
        content = self._read("app/(app)/ops/cleaner/page.tsx")
        assert "cleaning" in content.lower()

    def test_h5_cleaner_page_has_no_revenue_access(self) -> None:
        """H5: Cleaner page does NOT fetch revenue/financial data (checking code, not comments)."""
        content = self._read("app/(app)/ops/cleaner/page.tsx")
        # Strip comment block at top to avoid false positives on JSDoc
        code_start = content.find("import ")
        code = content[code_start:] if code_start >= 0 else content
        assert "revenue" not in code.lower()
        assert "financial" not in code.lower()
        assert "payout" not in code.lower()

    def test_h6_cleaner_page_has_no_passport_access(self) -> None:
        """H6: Cleaner page does NOT access passport data."""
        content = self._read("app/(app)/ops/cleaner/page.tsx")
        assert "passport" not in content.lower()


# ===========================================================================
# Group I — Security invariants
# ===========================================================================

class TestGroupI_SecurityInvariants:

    def test_i1_auth_guard_on_tasks(self) -> None:
        """I1: Task list requires auth — reject app returns 403."""
        from fastapi import HTTPException

        app = FastAPI()

        async def _reject():
            raise HTTPException(status_code=403, detail="AUTH_FAILED")

        app.dependency_overrides[jwt_auth] = _reject
        app.include_router(task_router)
        client = TestClient(app, raise_server_exceptions=False)
        assert client.get("/tasks?kind=CLEANING").status_code == 403

    def test_i2_auth_guard_on_start_cleaning(self) -> None:
        """I2: Start-cleaning requires auth."""
        from fastapi import HTTPException

        app = FastAPI()

        async def _reject():
            raise HTTPException(status_code=403, detail="AUTH_FAILED")

        app.dependency_overrides[jwt_auth] = _reject
        app.include_router(cleaning_router)
        client = TestClient(app, raise_server_exceptions=False)
        assert client.post(f"/tasks/{TASK_ID}/start-cleaning", json={"worker_id": "x"}).status_code == 403

    def test_i3_auth_guard_on_complete_cleaning(self) -> None:
        """I3: Complete-cleaning requires auth."""
        from fastapi import HTTPException

        app = FastAPI()

        async def _reject():
            raise HTTPException(status_code=403, detail="AUTH_FAILED")

        app.dependency_overrides[jwt_auth] = _reject
        app.include_router(cleaning_router)
        client = TestClient(app, raise_server_exceptions=False)
        assert client.post(f"/tasks/{TASK_ID}/complete-cleaning", json={}).status_code == 403
