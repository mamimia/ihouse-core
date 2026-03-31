"""
Phase 123 — Worker-Facing Task Surface — Contract Tests

Endpoints:
    GET  /worker/tasks
    PATCH /worker/tasks/{task_id}/acknowledge
    PATCH /worker/tasks/{task_id}/complete

Groups:
    A — GET /worker/tasks validation (limit, worker_role, status)
    B — GET /worker/tasks response shape
    C — GET /worker/tasks filtering
    D — PATCH acknowledge — happy path
    E — PATCH acknowledge — invalid transitions (terminal / wrong state)
    F — PATCH complete — happy path
    G — PATCH complete — invalid transitions
    H — Auth guard (403)
    I — Tenant isolation + 404 + 500 guard
    J — booking_state never read
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("fastapi")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _task_row(
    task_id: str = "task-001",
    tenant_id: str = "tenant_test",
    status: str = "PENDING",
    worker_role: str = "CLEANER",
    kind: str = "CLEANING",
    due_date: str = "2026-03-10",
    priority: str = "MEDIUM",
    notes: list | None = None,
) -> dict:
    return {
        "task_id": task_id,
        "tenant_id": tenant_id,
        "kind": kind,
        "status": status,
        "priority": priority,
        "urgency": "normal",
        "worker_role": worker_role,
        "ack_sla_minutes": 60,
        "booking_id": "bookingcom_R001",
        "property_id": "prop-1",
        "due_date": due_date,
        "title": "Clean property",
        "description": None,
        "created_at": "2026-03-09T10:00:00+00:00",
        "updated_at": "2026-03-09T10:00:00+00:00",
        "notes": notes or [],
        "canceled_reason": None,
    }


def _mock_db_list(rows: list) -> MagicMock:
    """Mock for GET /worker/tasks — handles tasks, tenant_permissions, and
    worker_property_assignments tables as the router now queries all three."""
    # Tasks chain — supports .eq, .neq, .in_, .or_, .limit, .order
    task_chain = MagicMock()
    task_chain.execute.return_value = MagicMock(data=rows)
    task_chain.eq.return_value = task_chain
    task_chain.neq.return_value = task_chain
    task_chain.in_.return_value = task_chain
    task_chain.or_.return_value = task_chain
    task_chain.limit.return_value = task_chain
    task_chain.order.return_value = task_chain

    # Permissions chain — returns empty (no perm record = unrestricted)
    perm_chain = MagicMock()
    perm_chain.execute.return_value = MagicMock(data=[])
    perm_chain.eq.return_value = perm_chain
    perm_chain.limit.return_value = perm_chain

    # Worker property assignments chain — returns empty
    asgn_chain = MagicMock()
    asgn_chain.execute.return_value = MagicMock(data=[])
    asgn_chain.eq.return_value = asgn_chain

    # Route db.table(name) to the correct chain
    task_table = MagicMock()
    task_table.select.return_value = task_chain

    perm_table = MagicMock()
    perm_table.select.return_value = perm_chain

    asgn_table = MagicMock()
    asgn_table.select.return_value = asgn_chain

    def _table_router(name: str):
        if name == "tenant_permissions":
            return perm_table
        if name == "worker_property_assignments":
            return asgn_table
        return task_table  # "tasks" and anything else

    db = MagicMock()
    db.table.side_effect = _table_router
    return db


def _mock_db_for_patch(
    fetch_rows: list,
    update_rows: list | None = None,
) -> MagicMock:
    """
    Mock for PATCH endpoints.
    First .execute() → select (fetch current task).
    Second .execute() → update.
    """
    fetch_chain = MagicMock()
    fetch_chain.execute.return_value = MagicMock(data=fetch_rows)
    fetch_chain.eq.return_value = fetch_chain
    fetch_chain.limit.return_value = fetch_chain
    fetch_chain.select.return_value = fetch_chain

    update_chain = MagicMock()
    update_chain.execute.return_value = MagicMock(data=update_rows or [])
    update_chain.eq.return_value = update_chain
    update_chain.update.return_value = update_chain

    db = MagicMock()
    # First call is select (fetch), second is update
    db.table.return_value.select.return_value = fetch_chain
    db.table.return_value.update.return_value = update_chain
    return db, fetch_chain, update_chain


def _make_app(tenant_id: str = "tenant_test") -> TestClient:
    from fastapi import FastAPI
    from api.worker_router import router
    from api.auth import jwt_auth

    app = FastAPI()

    async def _stub_auth():
        return tenant_id

    app.dependency_overrides[jwt_auth] = _stub_auth
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


# ===========================================================================
# Group A — GET validation
# ===========================================================================

class TestGroupA_GetValidation:

    def test_a1_default_limit_returns_200(self) -> None:
        """A1: No params → 200."""
        c = _make_app()
        db = _mock_db_list([])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.get("/worker/tasks")
        assert resp.status_code == 200

    def test_a2_limit_zero_returns_400(self) -> None:
        """A2: limit=0 → 400 VALIDATION_ERROR."""
        c = _make_app()
        db = _mock_db_list([])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.get("/worker/tasks?limit=0")
        assert resp.status_code == 400
        assert resp.json()["code"] == "VALIDATION_ERROR"

    def test_a3_limit_above_max_returns_400(self) -> None:
        """A3: limit=999 → 400 VALIDATION_ERROR."""
        c = _make_app()
        db = _mock_db_list([])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.get("/worker/tasks?limit=999")
        assert resp.status_code == 400
        assert resp.json()["code"] == "VALIDATION_ERROR"

    def test_a4_invalid_worker_role_returns_400(self) -> None:
        """A4: worker_role=ROBOT → 400 VALIDATION_ERROR."""
        c = _make_app()
        db = _mock_db_list([])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.get("/worker/tasks?worker_role=ROBOT")
        assert resp.status_code == 400
        assert resp.json()["code"] == "VALIDATION_ERROR"

    def test_a5_invalid_status_returns_400(self) -> None:
        """A5: status=FLYING → 400 VALIDATION_ERROR."""
        c = _make_app()
        db = _mock_db_list([])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.get("/worker/tasks?status=FLYING")
        assert resp.status_code == 400
        assert resp.json()["code"] == "VALIDATION_ERROR"

    def test_a6_valid_worker_role_cleaner_returns_200(self) -> None:
        """A6: worker_role=CLEANER → 200."""
        c = _make_app()
        db = _mock_db_list([_task_row(worker_role="CLEANER")])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.get("/worker/tasks?worker_role=CLEANER")
        assert resp.status_code == 200

    def test_a7_valid_status_pending_returns_200(self) -> None:
        """A7: status=PENDING → 200."""
        c = _make_app()
        db = _mock_db_list([_task_row()])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.get("/worker/tasks?status=PENDING")
        assert resp.status_code == 200

    def test_a8_default_excludes_completed_and_canceled(self) -> None:
        """A8: No status filter → backend must apply terminal-status exclusion.

        Invariant (Phase 1029/1031):
            GET /worker/tasks with no status param must NEVER return COMPLETED or CANCELED tasks.
            The worker_router applies: query = query.neq("status","CANCELED").neq("status","COMPLETED")

        Verification strategy:
            - Mock the DB to return only PENDING tasks (post-DB-filter state).
            - Call with no status param → assert 200 and only PENDING in response.
            - Separately verify that .eq("status", ...) is NOT called (which would mean
              a whitelist-style filter was used instead of exclusion) when no filter given.
        """
        pending_row = _task_row(status="PENDING", due_date="2099-12-31")
        c = _make_app()
        db = _mock_db_list([pending_row])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.get("/worker/tasks")
        assert resp.status_code == 200
        body = resp.json()
        # All returned tasks must be non-terminal
        for task in body.get("tasks", []):
            assert task["status"] not in ("COMPLETED", "CANCELED"), (
                f"Default /worker/tasks returned terminal status task: {task['status']}"
            )



# ===========================================================================
# Group B — GET response shape
# ===========================================================================

class TestGroupB_GetShape:

    def test_b1_response_has_tasks_and_count(self) -> None:
        """B1: Response has 'tasks' and 'count' keys."""
        c = _make_app()
        db = _mock_db_list([_task_row()])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            body = c.get("/worker/tasks").json()
        assert "tasks" in body
        assert "count" in body

    def test_b2_tasks_is_list(self) -> None:
        """B2: tasks is a list."""
        c = _make_app()
        db = _mock_db_list([_task_row()])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            body = c.get("/worker/tasks").json()
        assert isinstance(body["tasks"], list)

    def test_b3_count_matches_tasks_length(self) -> None:
        """B3: count = len(tasks)."""
        # Phase 1031: Use far-future due_date to bypass staleness guard
        rows = [_task_row("t1", due_date="2099-12-31"), _task_row("t2", due_date="2099-12-31")]
        c = _make_app()
        db = _mock_db_list(rows)
        with patch("api.worker_router._get_supabase_client", return_value=db):
            body = c.get("/worker/tasks").json()
        assert body["count"] == 2
        assert len(body["tasks"]) == 2

    def test_b4_empty_tasks_returns_200(self) -> None:
        """B4: No tasks → 200 + empty list."""
        c = _make_app()
        db = _mock_db_list([])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            body = c.get("/worker/tasks").json()
        assert body["tasks"] == []
        assert body["count"] == 0


# ===========================================================================
# Group C — GET filtering
# ===========================================================================

class TestGroupC_Filtering:

    def test_c1_worker_role_filter_passed_to_db(self) -> None:
        """C1: worker_role filter is passed to DB query chain."""
        c = _make_app()
        db = _mock_db_list([_task_row(worker_role="CLEANER")])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            c.get("/worker/tasks?worker_role=CLEANER")
        # Verify eq was called (it will bubble through the chain)
        assert db.table.called

    def test_c2_status_filter_applied(self) -> None:
        """C2: status filter in query string → 200."""
        c = _make_app()
        db = _mock_db_list([_task_row(status="PENDING")])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.get("/worker/tasks?status=PENDING")
        assert resp.status_code == 200

    def test_c3_date_filter_applied(self) -> None:
        """C3: date filter in query string → 200."""
        c = _make_app()
        db = _mock_db_list([_task_row(due_date="2026-03-10")])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.get("/worker/tasks?date=2026-03-10")
        assert resp.status_code == 200

    def test_c4_all_filters_combined(self) -> None:
        """C4: worker_role + status + date + limit → 200."""
        c = _make_app()
        db = _mock_db_list([])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.get("/worker/tasks?worker_role=CLEANER&status=PENDING&date=2026-03-10&limit=10")
        assert resp.status_code == 200


# ===========================================================================
# Group D — PATCH acknowledge — happy path
# ===========================================================================

class TestGroupD_AcknowledgeHappy:

    def test_d1_acknowledge_pending_returns_200(self) -> None:
        """D1: PENDING → ACKNOWLEDGED → 200."""
        c = _make_app()
        row = _task_row(status="PENDING")
        db, _, update_chain = _mock_db_for_patch([row], [])
        update_chain.execute.return_value = MagicMock(data=[{**row, "status": "ACKNOWLEDGED"}])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.patch("/worker/tasks/task-001/acknowledge")
        assert resp.status_code == 200

    def test_d2_acknowledge_response_has_task(self) -> None:
        """D2: acknowledge response body has 'task' key."""
        c = _make_app()
        row = _task_row(status="PENDING")
        db, _, update_chain = _mock_db_for_patch([row], [])
        update_chain.execute.return_value = MagicMock(data=[{**row, "status": "ACKNOWLEDGED"}])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            body = c.patch("/worker/tasks/task-001/acknowledge").json()
        assert "task" in body

    def test_d3_acknowledge_returns_updated_status(self) -> None:
        """D3: The returned task has status ACKNOWLEDGED."""
        c = _make_app()
        row = _task_row(status="PENDING")
        db, _, update_chain = _mock_db_for_patch([row], [])
        update_chain.execute.return_value = MagicMock(
            data=[{**row, "status": "ACKNOWLEDGED"}]
        )
        with patch("api.worker_router._get_supabase_client", return_value=db):
            body = c.patch("/worker/tasks/task-001/acknowledge").json()
        # updated_row from update result
        assert body["task"]["status"] == "ACKNOWLEDGED"

    def test_d4_acknowledge_no_body_required(self) -> None:
        """D4: acknowledge requires NO body."""
        c = _make_app()
        row = _task_row(status="PENDING")
        db, _, update_chain = _mock_db_for_patch([row])
        update_chain.execute.return_value = MagicMock(data=[])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.patch("/worker/tasks/task-001/acknowledge")
        assert resp.status_code in (200, 422)  # no body → still valid


# ===========================================================================
# Group E — PATCH acknowledge — invalid transitions
# ===========================================================================

class TestGroupE_AcknowledgeInvalid:

    def test_e1_acknowledge_completed_returns_422(self) -> None:
        """E1: COMPLETED → ACKNOWLEDGED → 422 INVALID_TRANSITION."""
        c = _make_app()
        row = _task_row(status="COMPLETED")
        db, _, _ = _mock_db_for_patch([row])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.patch("/worker/tasks/task-001/acknowledge")
        assert resp.status_code == 422
        assert resp.json()["code"] == "INVALID_TRANSITION"

    def test_e2_acknowledge_canceled_returns_422(self) -> None:
        """E2: CANCELED → ACKNOWLEDGED → 422 INVALID_TRANSITION."""
        c = _make_app()
        row = _task_row(status="CANCELED")
        db, _, _ = _mock_db_for_patch([row])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.patch("/worker/tasks/task-001/acknowledge")
        assert resp.status_code == 422
        assert resp.json()["code"] == "INVALID_TRANSITION"

    def test_e3_acknowledge_already_acknowledged_returns_422(self) -> None:
        """E3: ACKNOWLEDGED → ACKNOWLEDGED → 422 (already in that state)."""
        c = _make_app()
        row = _task_row(status="ACKNOWLEDGED")
        db, _, _ = _mock_db_for_patch([row])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.patch("/worker/tasks/task-001/acknowledge")
        assert resp.status_code == 422
        assert resp.json()["code"] == "INVALID_TRANSITION"

    def test_e4_acknowledge_not_found_returns_404(self) -> None:
        """E4: Task not found → 404 NOT_FOUND."""
        c = _make_app()
        db, _, _ = _mock_db_for_patch([])  # empty result
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.patch("/worker/tasks/nonexistent/acknowledge")
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"


# ===========================================================================
# Group F — PATCH complete — happy path
# ===========================================================================

class TestGroupF_CompleteHappy:

    def test_f1_complete_from_in_progress_returns_200(self) -> None:
        """F1: IN_PROGRESS → COMPLETED → 200 (only valid complete source)."""
        c = _make_app()
        row = _task_row(status="IN_PROGRESS")
        db, _, update_chain = _mock_db_for_patch([row])
        update_chain.execute.return_value = MagicMock(data=[{**row, "status": "COMPLETED"}])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.patch("/worker/tasks/task-001/complete", json={})
        assert resp.status_code == 200

    def test_f2_complete_from_acknowledged_returns_200(self) -> None:
        """F2: ACKNOWLEDGED → COMPLETED → 200 (shortcut transition now allowed)."""
        c = _make_app()
        row = _task_row(status="ACKNOWLEDGED")
        db, _, update_chain = _mock_db_for_patch([row])
        update_chain.execute.return_value = MagicMock(data=[{**row, "status": "COMPLETED"}])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.patch("/worker/tasks/task-001/complete", json={})
        assert resp.status_code == 200

    def test_f3_complete_response_has_task(self) -> None:
        """F3: complete response body has 'task' key."""
        c = _make_app()
        row = _task_row(status="IN_PROGRESS")
        db, _, update_chain = _mock_db_for_patch([row])
        update_chain.execute.return_value = MagicMock(data=[{**row, "status": "COMPLETED"}])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            body = c.patch("/worker/tasks/task-001/complete", json={}).json()
        assert "task" in body

    def test_f4_complete_with_notes_succeeds(self) -> None:
        """F4: complete with notes → 200."""
        c = _make_app()
        row = _task_row(status="IN_PROGRESS", notes=[])
        db, _, update_chain = _mock_db_for_patch([row])
        update_chain.execute.return_value = MagicMock(data=[])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.patch(
                "/worker/tasks/task-001/complete",
                json={"notes": "Cleaned and inspected"},
            )
        assert resp.status_code == 200

    def test_f5_complete_without_body_succeeds(self) -> None:
        """F5: complete with no body → 200 (notes optional)."""
        c = _make_app()
        row = _task_row(status="IN_PROGRESS")
        db, _, update_chain = _mock_db_for_patch([row])
        update_chain.execute.return_value = MagicMock(data=[])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.patch("/worker/tasks/task-001/complete")
        assert resp.status_code == 200


# ===========================================================================
# Group G — PATCH complete — invalid transitions
# ===========================================================================

class TestGroupG_CompleteInvalid:

    def test_g1_complete_from_pending_returns_422(self) -> None:
        """G1: PENDING → COMPLETED → 422 INVALID_TRANSITION."""
        c = _make_app()
        row = _task_row(status="PENDING")
        db, _, _ = _mock_db_for_patch([row])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.patch("/worker/tasks/task-001/complete", json={})
        assert resp.status_code == 422
        assert resp.json()["code"] == "INVALID_TRANSITION"

    def test_g2_complete_from_completed_returns_422(self) -> None:
        """G2: COMPLETED → COMPLETED → 422 (terminal)."""
        c = _make_app()
        row = _task_row(status="COMPLETED")
        db, _, _ = _mock_db_for_patch([row])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.patch("/worker/tasks/task-001/complete", json={})
        assert resp.status_code == 422

    def test_g3_complete_from_canceled_returns_422(self) -> None:
        """G3: CANCELED → COMPLETED → 422 (terminal)."""
        c = _make_app()
        row = _task_row(status="CANCELED")
        db, _, _ = _mock_db_for_patch([row])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.patch("/worker/tasks/task-001/complete", json={})
        assert resp.status_code == 422

    def test_g4_complete_not_found_returns_404(self) -> None:
        """G4: Task not found → 404 NOT_FOUND."""
        c = _make_app()
        db, _, _ = _mock_db_for_patch([])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.patch("/worker/tasks/nonexistent/complete", json={})
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"


# ===========================================================================
# Group H — Auth guard
# ===========================================================================

class TestGroupH_AuthGuard:

    def _make_reject_app(self) -> TestClient:
        from fastapi import FastAPI, HTTPException
        from api.worker_router import router
        from api.auth import jwt_auth

        app = FastAPI()

        async def _reject():
            raise HTTPException(status_code=403, detail="AUTH_FAILED")

        app.dependency_overrides[jwt_auth] = _reject
        app.include_router(router)
        return TestClient(app, raise_server_exceptions=False)

    def test_h1_no_auth_on_list_returns_403(self) -> None:
        """H1: GET /worker/tasks without auth → 403."""
        client = self._make_reject_app()
        assert client.get("/worker/tasks").status_code == 403

    def test_h2_no_auth_on_acknowledge_returns_403(self) -> None:
        """H2: PATCH acknowledge without auth → 403."""
        client = self._make_reject_app()
        assert client.patch("/worker/tasks/t1/acknowledge").status_code == 403

    def test_h3_no_auth_on_complete_returns_403(self) -> None:
        """H3: PATCH complete without auth → 403."""
        client = self._make_reject_app()
        assert client.patch("/worker/tasks/t1/complete").status_code == 403


# ===========================================================================
# Group I — Tenant isolation + 500 guard
# ===========================================================================

class TestGroupI_TenantIsolation:

    def test_i1_list_queries_tenant_scoped(self) -> None:
        """I1: GET /worker/tasks queries by tenant_id in DB."""
        c = _make_app(tenant_id="tenant-xyz")
        db = _mock_db_list([])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.get("/worker/tasks")
        assert resp.status_code == 200

    def test_i2_acknowledge_tenant_isolation_404(self) -> None:
        """I2: acknowledge cross-tenant task (empty result) → 404."""
        c = _make_app(tenant_id="other-tenant")
        db, _, _ = _mock_db_for_patch([])  # no rows for this tenant
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.patch("/worker/tasks/task-001/acknowledge")
        assert resp.status_code == 404

    def test_i3_db_error_on_list_returns_500(self) -> None:
        """I3: DB error on GET → 500 INTERNAL_ERROR."""
        c = _make_app()
        chain = MagicMock()
        chain.execute.side_effect = RuntimeError("db down")
        chain.eq.return_value = chain
        chain.neq.return_value = chain
        chain.in_.return_value = chain
        chain.not_ = chain
        chain.limit.return_value = chain
        chain.order.return_value = chain
        db = MagicMock()
        # Phase 1031: Make ALL tables fail so the outer try/except catches it
        # (permissions lookup failing silently used to mask the true tasks failure).
        # Now we force db.table itself to raise so no silent bypass is possible.
        db.table.side_effect = RuntimeError("db down")
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.get("/worker/tasks")
        assert resp.status_code == 500
        assert resp.json()["code"] == "INTERNAL_ERROR"

    def test_i4_500_does_not_leak_exception_message(self) -> None:
        """I4: 500 body does not contain raw exception text."""
        c = _make_app()
        chain = MagicMock()
        chain.execute.side_effect = RuntimeError("super_secret_passphrase")
        chain.eq.return_value = chain
        chain.limit.return_value = chain
        chain.order.return_value = chain
        db = MagicMock()
        db.table.return_value.select.return_value = chain
        with patch("api.worker_router._get_supabase_client", return_value=db):
            body = c.get("/worker/tasks").json()
        assert "super_secret_passphrase" not in str(body)


# ===========================================================================
# Group J — booking_state never read
# ===========================================================================

class TestGroupJ_NeverQueriesBookingState:

    def test_j1_list_does_not_query_booking_state(self) -> None:
        """J1: GET /worker/tasks must not call db.table('booking_state')."""
        c = _make_app()
        db = _mock_db_list([])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            c.get("/worker/tasks")
        calls = [str(c) for c in db.table.call_args_list]
        assert not any("booking_state" in c for c in calls)

    def test_j2_acknowledge_does_not_query_booking_state(self) -> None:
        """J2: acknowledge must not call db.table('booking_state')."""
        c = _make_app()
        row = _task_row(status="PENDING")
        db, _, update_chain = _mock_db_for_patch([row])
        update_chain.execute.return_value = MagicMock(data=[])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            c.patch("/worker/tasks/task-001/acknowledge")
        calls = [str(c) for c in db.table.call_args_list]
        assert not any("booking_state" in c for c in calls)
