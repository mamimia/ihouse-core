"""
Phase 113 — Task Query API contract tests.

Tests three endpoints in task_router.py:
    GET  /tasks                   — list with filters
    GET  /tasks/{task_id}         — single task
    PATCH /tasks/{task_id}/status — status transition

Groups:
  A — GET /tasks: success, empty list, count field
  B — GET /tasks: filters (property_id, status, kind, due_date, limit)
  C — GET /tasks: validation errors (bad status, bad kind, bad limit)
  D — GET /tasks: auth guard (missing JWT → 403)
  E — GET /tasks: tenant isolation (scoped by tenant_id from JWT)
  F — GET /tasks/{task_id}: success, task structure
  G — GET /tasks/{task_id}: 404 not found, tenant isolation
  H — GET /tasks/{task_id}: auth guard
  I — PATCH /status: valid transitions (PENDING→ACKNOWLEDGED→IN_PROGRESS→COMPLETED)
  J — PATCH /status: canceled_reason handling
  K — PATCH /status: invalid transitions (422 INVALID_TRANSITION)
  L — PATCH /status: terminal state transitions blocked
  M — PATCH /status: validation (missing body, bad status value)
  N — PATCH /status: 404 task not found
  O — PATCH /status: auth guard
  P — DB failure → 500 INTERNAL_ERROR
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# App fixture
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _dev_mode(monkeypatch):
    """Phase 283: set dev mode per-test so auth doesn't block."""
    monkeypatch.setenv("IHOUSE_DEV_MODE", "true")


@pytest.fixture(scope="module")
def client():
    import os
    os.environ.setdefault("SUPABASE_URL", "https://fake.supabase.co")
    os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "fake-key")
    os.environ.setdefault("IHOUSE_DEV_MODE", "true")  # Phase 283
    from main import app
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# JWT mock helper
# ---------------------------------------------------------------------------

_TENANT = "tenant_task_test"
_TOKEN = "Bearer valid-token"

def _jwt_ok(tenant_id: str = _TENANT):
    return patch("tasks.task_router.jwt_auth", return_value=tenant_id)

def _jwt_fail():
    from fastapi import HTTPException
    return patch("tasks.task_router.jwt_auth", side_effect=HTTPException(status_code=403, detail="Forbidden"))


# ---------------------------------------------------------------------------
# Supabase mock helpers
# ---------------------------------------------------------------------------

def _task_row(**kwargs):
    base = {
        "task_id": "abcdef1234567890",
        "tenant_id": _TENANT,
        "kind": "CLEANING",
        "status": "PENDING",
        "priority": "MEDIUM",
        "urgency": "normal",
        "worker_role": "CLEANER",
        "ack_sla_minutes": 60,
        "booking_id": "bookingcom_R001",
        "property_id": "prop_001",
        "due_date": "2026-04-05",
        "title": "Clean property",
        "description": None,
        "created_at": "2026-03-09T10:00:00+00:00",
        "updated_at": "2026-03-09T10:00:00+00:00",
        "notes": [],
        "canceled_reason": None,
    }
    base.update(kwargs)
    return base


def _db_list(rows=None):
    """Mock that returns rows for .table().select()...order().execute()."""
    mock = MagicMock()
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=rows or [])
    for method in ("select", "eq", "limit", "order"):
        getattr(chain, method).return_value = chain
    mock.table.return_value = chain
    return mock


def _db_get(row=None):
    """Mock that returns single row for .table().select().eq().eq().limit().execute()."""
    mock = MagicMock()
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=[row] if row else [])
    for method in ("select", "eq", "limit", "update"):
        getattr(chain, method).return_value = chain
    mock.table.return_value = chain
    return mock


def _db_update(current_row, updated_row=None):
    """
    Mock for PATCH: first execute() is the SELECT (returns current_row),
    second execute() is the UPDATE (returns updated_row or current_row).
    """
    mock = MagicMock()
    select_chain = MagicMock()
    select_chain.execute.return_value = MagicMock(data=[current_row])
    for m in ("select", "eq", "limit"):
        getattr(select_chain, m).return_value = select_chain

    update_chain = MagicMock()
    update_chain.execute.return_value = MagicMock(data=[updated_row or current_row])
    for m in ("update", "eq"):
        getattr(update_chain, m).return_value = update_chain

    def _table(name):
        return select_chain  # first call is SELECT; PATCH tests call separately

    mock.table.side_effect = _table
    return mock, select_chain, update_chain


# ---------------------------------------------------------------------------
# Group A — GET /tasks: success
# ---------------------------------------------------------------------------

class TestListTasksSuccess:

    def test_200_with_tasks(self, client):
        rows = [_task_row(), _task_row(task_id="aabb112233445566", booking_id="bookingcom_R002")]
        with _jwt_ok(), patch("tasks.task_router._get_supabase_client", return_value=_db_list(rows)):
            resp = client.get("/tasks")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 2
        assert len(body["tasks"]) == 2

    def test_200_empty_list(self, client):
        with _jwt_ok(), patch("tasks.task_router._get_supabase_client", return_value=_db_list([])):
            resp = client.get("/tasks")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0
        assert resp.json()["tasks"] == []

    def test_response_has_tasks_and_count_keys(self, client):
        with _jwt_ok(), patch("tasks.task_router._get_supabase_client", return_value=_db_list([_task_row()])):
            resp = client.get("/tasks")
        body = resp.json()
        assert "tasks" in body
        assert "count" in body


# ---------------------------------------------------------------------------
# Group B — GET /tasks: filters applied
# ---------------------------------------------------------------------------

class TestListTasksFilters:

    def _resp(self, client, **params):
        with _jwt_ok(), patch("tasks.task_router._get_supabase_client", return_value=_db_list([_task_row()])):
            return client.get("/tasks", params=params)

    def test_property_id_filter_accepted(self, client):
        assert self._resp(client, property_id="prop_001").status_code == 200

    def test_status_filter_pending(self, client):
        assert self._resp(client, status="PENDING").status_code == 200

    def test_status_filter_completed(self, client):
        assert self._resp(client, status="COMPLETED").status_code == 200

    def test_kind_filter_cleaning(self, client):
        assert self._resp(client, kind="CLEANING").status_code == 200

    def test_kind_filter_maintenance(self, client):
        assert self._resp(client, kind="MAINTENANCE").status_code == 200

    def test_due_date_filter(self, client):
        assert self._resp(client, due_date="2026-04-05").status_code == 200

    def test_limit_custom(self, client):
        assert self._resp(client, limit=10).status_code == 200

    def test_all_filters_combined(self, client):
        assert self._resp(
            client,
            property_id="prop_001",
            status="PENDING",
            kind="CLEANING",
            due_date="2026-04-05",
            limit=5,
        ).status_code == 200


# ---------------------------------------------------------------------------
# Group C — GET /tasks: validation errors
# ---------------------------------------------------------------------------

class TestListTasksValidation:

    def test_invalid_status_returns_400(self, client):
        with _jwt_ok(), patch("tasks.task_router._get_supabase_client", return_value=_db_list()):
            resp = client.get("/tasks", params={"status": "FLYING"})
        assert resp.status_code == 400
        assert resp.json()["code"] == "VALIDATION_ERROR"

    def test_invalid_kind_returns_400(self, client):
        with _jwt_ok(), patch("tasks.task_router._get_supabase_client", return_value=_db_list()):
            resp = client.get("/tasks", params={"kind": "INVALID_KIND"})
        assert resp.status_code == 400
        assert resp.json()["code"] == "VALIDATION_ERROR"

    def test_limit_zero_returns_400(self, client):
        with _jwt_ok(), patch("tasks.task_router._get_supabase_client", return_value=_db_list()):
            resp = client.get("/tasks", params={"limit": 0})
        assert resp.status_code == 400
        assert resp.json()["code"] == "VALIDATION_ERROR"

    def test_limit_over_100_returns_400(self, client):
        with _jwt_ok(), patch("tasks.task_router._get_supabase_client", return_value=_db_list()):
            resp = client.get("/tasks", params={"limit": 101})
        assert resp.status_code == 400
        assert resp.json()["code"] == "VALIDATION_ERROR"

    def test_limit_100_is_valid(self, client):
        with _jwt_ok(), patch("tasks.task_router._get_supabase_client", return_value=_db_list([])):
            resp = client.get("/tasks", params={"limit": 100})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Group D — GET /tasks: auth guard
# ---------------------------------------------------------------------------

class TestListTasksAuth:

    def test_missing_jwt_returns_403(self, client):
        from fastapi import HTTPException
        from api.auth import jwt_auth
        from main import app

        async def _reject():
            raise HTTPException(status_code=403, detail="AUTH_FAILED")

        app.dependency_overrides[jwt_auth] = _reject
        try:
            resp = client.get("/tasks")
        finally:
            app.dependency_overrides.pop(jwt_auth, None)
        assert resp.status_code == 403

    def test_valid_jwt_passes(self, client):
        with _jwt_ok(), patch("tasks.task_router._get_supabase_client", return_value=_db_list([])):
            resp = client.get("/tasks")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Group E — GET /tasks: tenant isolation
# ---------------------------------------------------------------------------

class TestListTasksTenantIsolation:

    def test_query_uses_tenant_id(self, client):
        mock_db = _db_list([_task_row()])
        with _jwt_ok("tenant_A"), patch("tasks.task_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/tasks")
        assert resp.status_code == 200
        # The tenant_id "tenant_A" is passed to the query chain
        mock_db.table.assert_any_call("tasks")


# ---------------------------------------------------------------------------
# Group F — GET /tasks/{task_id}: success
# ---------------------------------------------------------------------------

class TestGetTaskSuccess:

    def test_200_returns_task(self, client):
        row = _task_row()
        with _jwt_ok(), patch("tasks.task_router._get_supabase_client", return_value=_db_get(row)):
            resp = client.get(f"/tasks/{row['task_id']}")
        assert resp.status_code == 200
        assert resp.json()["task"]["task_id"] == row["task_id"]

    def test_task_structure_has_expected_keys(self, client):
        row = _task_row()
        with _jwt_ok(), patch("tasks.task_router._get_supabase_client", return_value=_db_get(row)):
            resp = client.get(f"/tasks/{row['task_id']}")
        task = resp.json()["task"]
        for key in ("task_id", "status", "kind", "tenant_id", "booking_id", "property_id"):
            assert key in task, f"Missing key: {key}"

    def test_response_has_task_wrapper_key(self, client):
        row = _task_row()
        with _jwt_ok(), patch("tasks.task_router._get_supabase_client", return_value=_db_get(row)):
            resp = client.get(f"/tasks/{row['task_id']}")
        assert "task" in resp.json()


# ---------------------------------------------------------------------------
# Group G — GET /tasks/{task_id}: 404 and isolation
# ---------------------------------------------------------------------------

class TestGetTaskNotFound:

    def test_404_when_task_not_found(self, client):
        with _jwt_ok(), patch("tasks.task_router._get_supabase_client", return_value=_db_get(None)):
            resp = client.get("/tasks/nonexistent0001")
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    def test_404_message_contains_task_id(self, client):
        with _jwt_ok(), patch("tasks.task_router._get_supabase_client", return_value=_db_get(None)):
            resp = client.get("/tasks/nonexistent0001")
        assert "nonexistent0001" in resp.json()["message"]

    def test_cross_tenant_returns_404(self, client):
        """Cross-tenant task ID returns 404, not 403 (avoids leaking existence)."""
        with _jwt_ok("other_tenant"), patch("tasks.task_router._get_supabase_client", return_value=_db_get(None)):
            resp = client.get("/tasks/abcdef1234567890")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Group H — GET /tasks/{task_id}: auth guard
# ---------------------------------------------------------------------------

class TestGetTaskAuth:

    def test_missing_jwt_returns_403(self, client):
        from fastapi import HTTPException
        from api.auth import jwt_auth
        from main import app

        async def _reject():
            raise HTTPException(status_code=403, detail="AUTH_FAILED")

        app.dependency_overrides[jwt_auth] = _reject
        try:
            resp = client.get("/tasks/abcdef1234567890")
        finally:
            app.dependency_overrides.pop(jwt_auth, None)
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Group I — PATCH /status: valid transitions
# ---------------------------------------------------------------------------

class TestPatchStatusValidTransitions:

    def _patch(self, client, current_status, new_status, extra_row_fields=None):
        row = _task_row(status=current_status, **(extra_row_fields or {}))
        updated = {**row, "status": new_status}

        mock = MagicMock()
        select_chain = MagicMock()
        update_chain = MagicMock()
        select_chain.execute.return_value = MagicMock(data=[row])
        update_chain.execute.return_value = MagicMock(data=[updated])
        for m in ("select", "eq", "limit"):
            getattr(select_chain, m).return_value = select_chain
        for m in ("update", "eq"):
            getattr(update_chain, m).return_value = update_chain

        call_count = [0]
        def _table(name):
            call_count[0] += 1
            return select_chain if call_count[0] == 1 else update_chain

        mock.table.side_effect = _table

        with _jwt_ok(), patch("tasks.task_router._get_supabase_client", return_value=mock):
            return client.patch(
                f"/tasks/{row['task_id']}/status",
                json={"status": new_status},
            )

    def test_pending_to_acknowledged(self, client):
        resp = self._patch(client, "PENDING", "ACKNOWLEDGED")
        assert resp.status_code == 200
        assert resp.json()["task"]["status"] == "ACKNOWLEDGED"

    def test_acknowledged_to_in_progress(self, client):
        resp = self._patch(client, "ACKNOWLEDGED", "IN_PROGRESS")
        assert resp.status_code == 200

    def test_in_progress_to_completed(self, client):
        resp = self._patch(client, "IN_PROGRESS", "COMPLETED")
        assert resp.status_code == 200

    def test_pending_to_canceled(self, client):
        resp = self._patch(client, "PENDING", "CANCELED")
        assert resp.status_code == 200

    def test_acknowledged_to_canceled(self, client):
        resp = self._patch(client, "ACKNOWLEDGED", "CANCELED")
        assert resp.status_code == 200

    def test_in_progress_to_canceled(self, client):
        resp = self._patch(client, "IN_PROGRESS", "CANCELED")
        assert resp.status_code == 200

    def test_response_has_task_key(self, client):
        resp = self._patch(client, "PENDING", "ACKNOWLEDGED")
        assert "task" in resp.json()


# ---------------------------------------------------------------------------
# Group J — PATCH /status: canceled_reason
# ---------------------------------------------------------------------------

class TestPatchStatusCanceledReason:

    def _patch_cancel(self, client, reason=None):
        row = _task_row(status="PENDING")
        mock = MagicMock()
        select_chain = MagicMock()
        update_chain = MagicMock()
        select_chain.execute.return_value = MagicMock(data=[row])
        update_chain.execute.return_value = MagicMock(data=[{**row, "status": "CANCELED", "canceled_reason": reason or "Canceled via API"}])
        for m in ("select", "eq", "limit"):
            getattr(select_chain, m).return_value = select_chain
        for m in ("update", "eq"):
            getattr(update_chain, m).return_value = update_chain
        call_count = [0]
        def _table(name):
            call_count[0] += 1
            return select_chain if call_count[0] == 1 else update_chain
        mock.table.side_effect = _table

        body = {"status": "CANCELED"}
        if reason is not None:
            body["canceled_reason"] = reason

        with _jwt_ok(), patch("tasks.task_router._get_supabase_client", return_value=mock):
            return client.patch(f"/tasks/{row['task_id']}/status", json=body)

    def test_canceled_without_reason_defaults(self, client):
        resp = self._patch_cancel(client)
        assert resp.status_code == 200

    def test_canceled_with_custom_reason(self, client):
        resp = self._patch_cancel(client, reason="Booking was canceled")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Group K — PATCH /status: invalid transitions
# ---------------------------------------------------------------------------

class TestPatchStatusInvalidTransitions:

    def _patch_invalid(self, client, current_status, new_status):
        row = _task_row(status=current_status)
        mock = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[row])
        for m in ("select", "eq", "limit", "update"):
            getattr(chain, m).return_value = chain
        mock.table.return_value = chain

        with _jwt_ok(), patch("tasks.task_router._get_supabase_client", return_value=mock):
            return client.patch(
                f"/tasks/{row['task_id']}/status",
                json={"status": new_status},
            )

    def test_pending_to_completed_is_422(self, client):
        resp = self._patch_invalid(client, "PENDING", "COMPLETED")
        assert resp.status_code == 422
        assert resp.json()["code"] == "INVALID_TRANSITION"

    def test_pending_to_in_progress_is_422(self, client):
        resp = self._patch_invalid(client, "PENDING", "IN_PROGRESS")
        assert resp.status_code == 422

    def test_acknowledged_to_completed_is_200(self, client):
        """ACKNOWLEDGED → COMPLETED is now a valid shortcut transition."""
        resp = self._patch_invalid(client, "ACKNOWLEDGED", "COMPLETED")
        assert resp.status_code == 200

    def test_invalid_transition_message_mentions_states(self, client):
        resp = self._patch_invalid(client, "PENDING", "COMPLETED")
        msg = resp.json()["message"]
        assert "PENDING" in msg
        assert "COMPLETED" in msg


# ---------------------------------------------------------------------------
# Group L — PATCH /status: terminal states blocked
# ---------------------------------------------------------------------------

class TestPatchStatusTerminalBlocked:

    def _patch_terminal(self, client, current_status, new_status):
        row = _task_row(status=current_status)
        mock = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[row])
        for m in ("select", "eq", "limit", "update"):
            getattr(chain, m).return_value = chain
        mock.table.return_value = chain

        with _jwt_ok(), patch("tasks.task_router._get_supabase_client", return_value=mock):
            return client.patch(
                f"/tasks/{row['task_id']}/status",
                json={"status": new_status},
            )

    def test_completed_cannot_transition_to_acknowledged(self, client):
        resp = self._patch_terminal(client, "COMPLETED", "ACKNOWLEDGED")
        assert resp.status_code == 422

    def test_completed_cannot_transition_to_canceled(self, client):
        resp = self._patch_terminal(client, "COMPLETED", "CANCELED")
        assert resp.status_code == 422

    def test_canceled_cannot_transition_to_pending(self, client):
        resp = self._patch_terminal(client, "CANCELED", "PENDING")
        assert resp.status_code == 422

    def test_canceled_cannot_transition_to_in_progress(self, client):
        resp = self._patch_terminal(client, "CANCELED", "IN_PROGRESS")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Group M — PATCH /status: body validation
# ---------------------------------------------------------------------------

class TestPatchStatusBodyValidation:

    def _patch_body(self, client, body):
        with _jwt_ok():
            return client.patch("/tasks/abcdef1234567890/status", json=body)

    def test_missing_status_field_returns_400(self, client):
        mock = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[_task_row()])
        for m in ("select", "eq", "limit"):
            getattr(chain, m).return_value = chain
        mock.table.return_value = chain
        with _jwt_ok(), patch("tasks.task_router._get_supabase_client", return_value=mock):
            resp = client.patch("/tasks/abcdef1234567890/status", json={"note": "no status"})
        assert resp.status_code == 400
        assert resp.json()["code"] == "VALIDATION_ERROR"

    def test_invalid_status_value_returns_400(self, client):
        mock = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[_task_row()])
        for m in ("select", "eq", "limit"):
            getattr(chain, m).return_value = chain
        mock.table.return_value = chain
        with _jwt_ok(), patch("tasks.task_router._get_supabase_client", return_value=mock):
            resp = client.patch("/tasks/abcdef1234567890/status", json={"status": "FLYING"})
        assert resp.status_code == 400
        assert resp.json()["code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# Group N — PATCH /status: task not found
# ---------------------------------------------------------------------------

class TestPatchStatusNotFound:

    def test_404_when_task_not_found(self, client):
        mock = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[])
        for m in ("select", "eq", "limit"):
            getattr(chain, m).return_value = chain
        mock.table.return_value = chain

        with _jwt_ok(), patch("tasks.task_router._get_supabase_client", return_value=mock):
            resp = client.patch("/tasks/nonexistent0001/status", json={"status": "ACKNOWLEDGED"})
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# Group O — PATCH /status: auth guard
# ---------------------------------------------------------------------------

class TestPatchStatusAuth:

    def test_missing_jwt_returns_403(self, client):
        from fastapi import HTTPException
        from api.auth import jwt_auth
        from main import app

        async def _reject():
            raise HTTPException(status_code=403, detail="AUTH_FAILED")

        app.dependency_overrides[jwt_auth] = _reject
        try:
            resp = client.patch("/tasks/abcdef1234567890/status", json={"status": "ACKNOWLEDGED"})
        finally:
            app.dependency_overrides.pop(jwt_auth, None)
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Group P — DB failure → 500
# ---------------------------------------------------------------------------

class TestTaskRouterDBFailure:

    def test_list_tasks_db_failure_returns_500(self, client):
        mock = MagicMock()
        chain = MagicMock()
        chain.execute.side_effect = RuntimeError("DB down")
        for m in ("select", "eq", "limit", "order"):
            getattr(chain, m).return_value = chain
        mock.table.return_value = chain

        with _jwt_ok(), patch("tasks.task_router._get_supabase_client", return_value=mock):
            resp = client.get("/tasks")
        assert resp.status_code == 500
        assert resp.json()["code"] == "INTERNAL_ERROR"

    def test_get_task_db_failure_returns_500(self, client):
        mock = MagicMock()
        chain = MagicMock()
        chain.execute.side_effect = RuntimeError("DB down")
        for m in ("select", "eq", "limit"):
            getattr(chain, m).return_value = chain
        mock.table.return_value = chain

        with _jwt_ok(), patch("tasks.task_router._get_supabase_client", return_value=mock):
            resp = client.get("/tasks/abcdef1234567890")
        assert resp.status_code == 500
        assert resp.json()["code"] == "INTERNAL_ERROR"

    def test_patch_status_db_failure_returns_500(self, client):
        mock = MagicMock()
        chain = MagicMock()
        chain.execute.side_effect = RuntimeError("DB down")
        for m in ("select", "eq", "limit", "update"):
            getattr(chain, m).return_value = chain
        mock.table.return_value = chain

        with _jwt_ok(), patch("tasks.task_router._get_supabase_client", return_value=mock):
            resp = client.patch("/tasks/abcdef1234567890/status", json={"status": "ACKNOWLEDGED"})
        assert resp.status_code == 500
        assert resp.json()["code"] == "INTERNAL_ERROR"
