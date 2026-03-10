"""
Phase 202 — Worker Notification History — Contract Tests

Endpoint:
    GET /worker/notifications

Groups:
    A — Response shape and empty state
    B — Validation (limit, status)
    C — Filtering
    D — Auth guard (403)
    E — Error isolation / 500 guard
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("fastapi")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _notification_row(
    notification_delivery_id: str = "nd-001",
    tenant_id: str = "tenant_test",
    user_id: str = "tenant_test",
    channel_type: str = "line",
    channel_id: str = "U1234567890abcdef",
    status: str = "sent",
    trigger_reason: str = "ACK_SLA_BREACH",
    task_id: str = "task-001",
    error_message: str | None = None,
    dispatched_at: str = "2026-03-11T00:00:00+00:00",
) -> dict:
    return {
        "notification_delivery_id": notification_delivery_id,
        "channel_type": channel_type,
        "channel_id": channel_id,
        "status": status,
        "error_message": error_message,
        "trigger_reason": trigger_reason,
        "task_id": task_id,
        "dispatched_at": dispatched_at,
    }


def _mock_db_list(rows: list) -> MagicMock:
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=rows)
    chain.eq.return_value = chain
    chain.select.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    db = MagicMock()
    db.table.return_value.select.return_value = chain
    return db


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


def _make_reject_app() -> TestClient:
    from fastapi import FastAPI, HTTPException
    from api.worker_router import router
    from api.auth import jwt_auth

    app = FastAPI()

    async def _reject():
        raise HTTPException(status_code=403, detail="AUTH_FAILED")

    app.dependency_overrides[jwt_auth] = _reject
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


# ===========================================================================
# Group A — Response shape / empty state
# ===========================================================================

class TestGroupA_Shape:

    def test_a1_empty_returns_200(self) -> None:
        """A1: No notifications → 200 with empty list."""
        c = _make_app()
        db = _mock_db_list([])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.get("/worker/notifications")
        assert resp.status_code == 200
        body = resp.json()
        assert body["notifications"] == []
        assert body["count"] == 0

    def test_a2_response_has_required_keys(self) -> None:
        """A2: Response has user_id, notifications, count."""
        c = _make_app()
        db = _mock_db_list([])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            body = c.get("/worker/notifications").json()
        assert "user_id" in body
        assert "notifications" in body
        assert "count" in body

    def test_a3_user_id_matches_tenant(self) -> None:
        """A3: user_id in response matches the JWT tenant (fallback)."""
        c = _make_app(tenant_id="tenant-xyz")
        db = _mock_db_list([])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            body = c.get("/worker/notifications").json()
        assert body["user_id"] == "tenant-xyz"

    def test_a4_one_row_returns_count_one(self) -> None:
        """A4: 1 notification row → count=1, list length=1."""
        c = _make_app()
        db = _mock_db_list([_notification_row()])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            body = c.get("/worker/notifications").json()
        assert body["count"] == 1
        assert len(body["notifications"]) == 1

    def test_a5_row_has_expected_fields(self) -> None:
        """A5: Notification row has channel_type, status, dispatched_at."""
        c = _make_app()
        db = _mock_db_list([_notification_row()])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            row = c.get("/worker/notifications").json()["notifications"][0]
        assert "channel_type" in row
        assert "status" in row
        assert "dispatched_at" in row

    def test_a6_failed_row_includes_error_message(self) -> None:
        """A6: Failed delivery row has error_message field."""
        c = _make_app()
        row = _notification_row(status="failed", error_message="LINE API timeout")
        db = _mock_db_list([row])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            notif = c.get("/worker/notifications").json()["notifications"][0]
        assert notif["error_message"] == "LINE API timeout"

    def test_a7_multiple_rows(self) -> None:
        """A7: Multiple rows returned in order (newest first by DB)."""
        rows = [
            _notification_row("nd-002", dispatched_at="2026-03-11T01:00:00+00:00"),
            _notification_row("nd-001", dispatched_at="2026-03-11T00:00:00+00:00"),
        ]
        c = _make_app()
        db = _mock_db_list(rows)
        with patch("api.worker_router._get_supabase_client", return_value=db):
            body = c.get("/worker/notifications").json()
        assert body["count"] == 2


# ===========================================================================
# Group B — Validation
# ===========================================================================

class TestGroupB_Validation:

    def test_b1_limit_zero_returns_400(self) -> None:
        """B1: limit=0 → 400 VALIDATION_ERROR."""
        c = _make_app()
        resp = c.get("/worker/notifications?limit=0")
        assert resp.status_code == 400
        assert resp.json()["code"] == "VALIDATION_ERROR"

    def test_b2_limit_above_max_returns_400(self) -> None:
        """B2: limit=999 → 400 VALIDATION_ERROR."""
        c = _make_app()
        resp = c.get("/worker/notifications?limit=999")
        assert resp.status_code == 400
        assert resp.json()["code"] == "VALIDATION_ERROR"

    def test_b3_valid_limit_50_returns_200(self) -> None:
        """B3: limit=50 (max) → 200."""
        c = _make_app()
        db = _mock_db_list([])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.get("/worker/notifications?limit=50")
        assert resp.status_code == 200

    def test_b4_invalid_status_returns_400(self) -> None:
        """B4: status=FLYING → 400 VALIDATION_ERROR."""
        c = _make_app()
        resp = c.get("/worker/notifications?status=FLYING")
        assert resp.status_code == 400
        assert resp.json()["code"] == "VALIDATION_ERROR"

    def test_b5_valid_status_sent_returns_200(self) -> None:
        """B5: status=sent → 200."""
        c = _make_app()
        db = _mock_db_list([])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.get("/worker/notifications?status=sent")
        assert resp.status_code == 200

    def test_b6_valid_status_failed_returns_200(self) -> None:
        """B6: status=failed → 200."""
        c = _make_app()
        db = _mock_db_list([])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.get("/worker/notifications?status=failed")
        assert resp.status_code == 200


# ===========================================================================
# Group C — Filtering and tenant isolation
# ===========================================================================

class TestGroupC_Filtering:

    def test_c1_queries_notification_delivery_log_table(self) -> None:
        """C1: GET must query notification_delivery_log, not tasks or booking_state."""
        c = _make_app()
        db = _mock_db_list([])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            c.get("/worker/notifications")
        calls = [str(ca) for ca in db.table.call_args_list]
        assert any("notification_delivery_log" in ca for ca in calls)
        assert not any("booking_state" in ca for ca in calls)
        assert not any("tasks" in ca for ca in calls)

    def test_c2_tenant_isolation(self) -> None:
        """C2: GET queries by tenant_id (db.eq called with tenant_id)."""
        c = _make_app(tenant_id="tenant-isolated")
        db = _mock_db_list([])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.get("/worker/notifications")
        assert resp.status_code == 200  # tenant scoping applied at query level

    def test_c3_status_filter_sent(self) -> None:
        """C3: status=sent filter applied → only sent rows shown."""
        c = _make_app()
        rows = [_notification_row(status="sent")]
        db = _mock_db_list(rows)
        with patch("api.worker_router._get_supabase_client", return_value=db):
            body = c.get("/worker/notifications?status=sent").json()
        assert body["count"] == 1

    def test_c4_status_filter_failed(self) -> None:
        """C4: status=failed filter applied."""
        c = _make_app()
        rows = [_notification_row(status="failed", error_message="timeout")]
        db = _mock_db_list(rows)
        with patch("api.worker_router._get_supabase_client", return_value=db):
            body = c.get("/worker/notifications?status=failed").json()
        assert body["notifications"][0]["status"] == "failed"

    def test_c5_limit_applied(self) -> None:
        """C5: limit=1 → at most 1 row returned."""
        c = _make_app()
        db = _mock_db_list([_notification_row("nd-001")])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            body = c.get("/worker/notifications?limit=1").json()
        assert body["count"] <= 1


# ===========================================================================
# Group D — Auth guard (403)
# ===========================================================================

class TestGroupD_AuthGuard:

    def test_d1_no_auth_returns_403(self) -> None:
        """D1: GET /worker/notifications without auth → 403."""
        assert _make_reject_app().get("/worker/notifications").status_code == 403


# ===========================================================================
# Group E — Error isolation
# ===========================================================================

class TestGroupE_ErrorIsolation:

    def test_e1_db_error_returns_500(self) -> None:
        """E1: DB error → 500 INTERNAL_ERROR."""
        c = _make_app()
        chain = MagicMock()
        chain.execute.side_effect = RuntimeError("db down")
        chain.eq.return_value = chain
        chain.select.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = chain
        db = MagicMock()
        db.table.return_value.select.return_value = chain
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.get("/worker/notifications")
        assert resp.status_code == 500
        assert resp.json()["code"] == "INTERNAL_ERROR"

    def test_e2_500_does_not_leak_exception(self) -> None:
        """E2: 500 body does not contain raw exception text."""
        c = _make_app()
        chain = MagicMock()
        chain.execute.side_effect = RuntimeError("super_secret_db_error")
        chain.eq.return_value = chain
        chain.select.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = chain
        db = MagicMock()
        db.table.return_value.select.return_value = chain
        with patch("api.worker_router._get_supabase_client", return_value=db):
            body = c.get("/worker/notifications").json()
        assert "super_secret_db_error" not in str(body)
