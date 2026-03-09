"""
Phase 124 — LINE Webhook Router — Contract Tests

Tests for POST /line/webhook endpoint.

Groups:
    A — Validation (missing body, missing task_id, invalid JSON)
    B — Dev mode (no LINE_WEBHOOK_SECRET) — happy path
    C — Task state transitions (PENDING→ACKNOWLEDGED, idempotent, terminal=409)
    D — Signature validation (when LINE_WEBHOOK_SECRET set)
    E — 404 task not found
    F — 500 / error guard
    G — booking_state never read invariant
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("fastapi")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _task_row(
    task_id: str = "task-001",
    status: str = "PENDING",
) -> dict:
    return {
        "task_id": task_id,
        "tenant_id": "tenant_test",
        "kind": "CLEANING",
        "status": status,
        "priority": "HIGH",
        "urgency": "urgent",
        "worker_role": "CLEANER",
        "ack_sla_minutes": 15,
        "booking_id": "bookingcom_R001",
        "property_id": "prop-1",
        "due_date": "2026-03-10",
        "title": "Clean property",
        "description": None,
        "created_at": "2026-03-09T10:00:00+00:00",
        "updated_at": "2026-03-09T10:00:00+00:00",
        "notes": [],
        "canceled_reason": None,
    }


def _mock_db_fetch(rows: list) -> MagicMock:
    """Mock fetch chain for the select path."""
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=rows)
    chain.eq.return_value = chain
    chain.limit.return_value = chain
    chain.select.return_value = chain
    db = MagicMock()
    db.table.return_value.select.return_value = chain
    return db


def _mock_db_for_webhook(
    fetch_rows: list,
    update_rows: list | None = None,
) -> tuple:
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
    db.table.return_value.select.return_value = fetch_chain
    db.table.return_value.update.return_value = update_chain
    return db, fetch_chain, update_chain


def _make_app() -> TestClient:
    from fastapi import FastAPI
    from api.line_webhook_router import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


# ===========================================================================
# Group A — Validation
# ===========================================================================

class TestGroupA_Validation:

    def test_a1_missing_task_id_returns_400(self) -> None:
        """A1: Body without task_id → 400 VALIDATION_ERROR."""
        c = _make_app()
        db = _mock_db_fetch([])
        with patch("api.line_webhook_router._get_supabase_client", return_value=db):
            resp = c.post("/line/webhook", json={"acked_by": "worker"})
        assert resp.status_code == 400
        assert resp.json()["code"] == "VALIDATION_ERROR"

    def test_a2_empty_task_id_returns_400(self) -> None:
        """A2: task_id='' → 400 VALIDATION_ERROR."""
        c = _make_app()
        db = _mock_db_fetch([])
        with patch("api.line_webhook_router._get_supabase_client", return_value=db):
            resp = c.post("/line/webhook", json={"task_id": ""})
        assert resp.status_code == 400
        assert resp.json()["code"] == "VALIDATION_ERROR"

    def test_a3_non_string_task_id_returns_400(self) -> None:
        """A3: task_id=123 (int) → 400 VALIDATION_ERROR."""
        c = _make_app()
        db = _mock_db_fetch([])
        with patch("api.line_webhook_router._get_supabase_client", return_value=db):
            resp = c.post("/line/webhook", json={"task_id": 123})
        assert resp.status_code == 400
        assert resp.json()["code"] == "VALIDATION_ERROR"

    def test_a4_valid_task_id_present_proceeds(self) -> None:
        """A4: Valid task_id → passes validation stage (not 400)."""
        c = _make_app()
        row = _task_row(status="PENDING")
        db, _, update_chain = _mock_db_for_webhook([row])
        update_chain.execute.return_value = MagicMock(data=[{**row, "status": "ACKNOWLEDGED"}])
        with patch("api.line_webhook_router._get_supabase_client", return_value=db):
            resp = c.post("/line/webhook", json={"task_id": "task-001"})
        assert resp.status_code != 400


# ===========================================================================
# Group B — Dev mode (no LINE_WEBHOOK_SECRET)
# ===========================================================================

class TestGroupB_DevMode:

    def test_b1_no_secret_skips_sig_check(self) -> None:
        """B1: LINE_WEBHOOK_SECRET unset → no signature validation, 200."""
        c = _make_app()
        row = _task_row(status="PENDING")
        db, _, update_chain = _mock_db_for_webhook([row])
        update_chain.execute.return_value = MagicMock(data=[])
        env = {k: v for k, v in os.environ.items() if k != "LINE_WEBHOOK_SECRET"}
        with patch.dict(os.environ, env, clear=True):
            with patch("api.line_webhook_router._get_supabase_client", return_value=db):
                resp = c.post("/line/webhook", json={"task_id": "task-001"})
        assert resp.status_code == 200

    def test_b2_response_has_task_id(self) -> None:
        """B2: Response body has task_id."""
        c = _make_app()
        row = _task_row(status="PENDING")
        db, _, update_chain = _mock_db_for_webhook([row])
        update_chain.execute.return_value = MagicMock(data=[])
        with patch("api.line_webhook_router._get_supabase_client", return_value=db):
            body = c.post("/line/webhook", json={"task_id": "task-001"}).json()
        assert "task_id" in body

    def test_b3_response_has_status(self) -> None:
        """B3: Response body has status."""
        c = _make_app()
        row = _task_row(status="PENDING")
        db, _, update_chain = _mock_db_for_webhook([row])
        update_chain.execute.return_value = MagicMock(data=[])
        with patch("api.line_webhook_router._get_supabase_client", return_value=db):
            body = c.post("/line/webhook", json={"task_id": "task-001"}).json()
        assert "status" in body

    def test_b4_acked_by_defaults_to_line(self) -> None:
        """B4: No acked_by in body → defaults to 'LINE'."""
        c = _make_app()
        row = _task_row(status="PENDING")
        db, _, update_chain = _mock_db_for_webhook([row])
        update_chain.execute.return_value = MagicMock(data=[])
        with patch("api.line_webhook_router._get_supabase_client", return_value=db):
            body = c.post("/line/webhook", json={"task_id": "task-001"}).json()
        assert body.get("acked_by") == "LINE"


# ===========================================================================
# Group C — State transitions
# ===========================================================================

class TestGroupC_StateTransitions:

    def test_c1_pending_task_becomes_acknowledged(self) -> None:
        """C1: PENDING → ACKNOWLEDGED on webhook call."""
        c = _make_app()
        row = _task_row(status="PENDING")
        db, _, update_chain = _mock_db_for_webhook([row])
        update_chain.execute.return_value = MagicMock(
            data=[{**row, "status": "ACKNOWLEDGED"}]
        )
        with patch("api.line_webhook_router._get_supabase_client", return_value=db):
            resp = c.post("/line/webhook", json={"task_id": "task-001"})
        assert resp.status_code == 200

    def test_c2_already_acknowledged_returns_200_idempotent(self) -> None:
        """C2: Already ACKNOWLEDGED → 200 idempotent (no re-update)."""
        c = _make_app()
        row = _task_row(status="ACKNOWLEDGED")
        db = _mock_db_fetch([row])
        with patch("api.line_webhook_router._get_supabase_client", return_value=db):
            resp = c.post("/line/webhook", json={"task_id": "task-001"})
        assert resp.status_code == 200
        body = resp.json()
        assert "Already acknowledged" in body.get("message", "")

    def test_c3_completed_returns_409(self) -> None:
        """C3: COMPLETED → 409 INVALID_TRANSITION."""
        c = _make_app()
        row = _task_row(status="COMPLETED")
        db = _mock_db_fetch([row])
        with patch("api.line_webhook_router._get_supabase_client", return_value=db):
            resp = c.post("/line/webhook", json={"task_id": "task-001"})
        assert resp.status_code == 409
        assert resp.json()["code"] == "INVALID_TRANSITION"

    def test_c4_canceled_returns_409(self) -> None:
        """C4: CANCELED → 409 INVALID_TRANSITION."""
        c = _make_app()
        row = _task_row(status="CANCELED")
        db = _mock_db_fetch([row])
        with patch("api.line_webhook_router._get_supabase_client", return_value=db):
            resp = c.post("/line/webhook", json={"task_id": "task-001"})
        assert resp.status_code == 409

    def test_c5_in_progress_returns_409(self) -> None:
        """C5: IN_PROGRESS → 409 (only PENDING→ACKNOWLEDGED via LINE)."""
        c = _make_app()
        row = _task_row(status="IN_PROGRESS")
        db = _mock_db_fetch([row])
        with patch("api.line_webhook_router._get_supabase_client", return_value=db):
            resp = c.post("/line/webhook", json={"task_id": "task-001"})
        assert resp.status_code == 409


# ===========================================================================
# Group D — Signature validation (production mode)
# ===========================================================================

class TestGroupD_SignatureValidation:

    def test_d1_valid_sig_returns_200(self) -> None:
        """D1: Valid HMAC-SHA256 signature → 200."""
        import base64
        import hashlib
        import hmac as _hmac
        secret = "test-secret"
        body = b'{"task_id":"task-001"}'
        mac = _hmac.new(secret.encode(), body, hashlib.sha256)
        sig = base64.b64encode(mac.digest()).decode()

        c = _make_app()
        row = _task_row(status="PENDING")
        db, _, update_chain = _mock_db_for_webhook([row])
        update_chain.execute.return_value = MagicMock(data=[])
        with patch.dict(os.environ, {"LINE_WEBHOOK_SECRET": secret}):
            with patch("api.line_webhook_router._get_supabase_client", return_value=db):
                resp = c.post(
                    "/line/webhook",
                    content=body,
                    headers={"Content-Type": "application/json", "X-Line-Signature": sig},
                )
        assert resp.status_code == 200

    def test_d2_invalid_sig_returns_401(self) -> None:
        """D2: Wrong signature → 401 AUTH_FAILED."""
        secret = "test-secret"
        c = _make_app()
        db = _mock_db_fetch([])
        with patch.dict(os.environ, {"LINE_WEBHOOK_SECRET": secret}):
            with patch("api.line_webhook_router._get_supabase_client", return_value=db):
                resp = c.post(
                    "/line/webhook",
                    json={"task_id": "task-001"},
                    headers={"X-Line-Signature": "invalid-sig"},
                )
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTH_FAILED"

    def test_d3_missing_sig_header_returns_401_in_prod(self) -> None:
        """D3: No X-Line-Signature header in prod mode → 401."""
        secret = "test-secret"
        c = _make_app()
        db = _mock_db_fetch([])
        with patch.dict(os.environ, {"LINE_WEBHOOK_SECRET": secret}):
            with patch("api.line_webhook_router._get_supabase_client", return_value=db):
                resp = c.post("/line/webhook", json={"task_id": "task-001"})
        assert resp.status_code == 401


# ===========================================================================
# Group E — 404 handling
# ===========================================================================

class TestGroupE_NotFound:

    def test_e1_task_not_found_returns_404(self) -> None:
        """E1: Unknown task_id → 404 NOT_FOUND."""
        c = _make_app()
        db = _mock_db_fetch([])
        with patch("api.line_webhook_router._get_supabase_client", return_value=db):
            resp = c.post("/line/webhook", json={"task_id": "nonexistent"})
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"


# ===========================================================================
# Group F — 500 error guard
# ===========================================================================

class TestGroupF_ErrorGuard:

    def test_f1_db_error_returns_500(self) -> None:
        """F1: DB exception → 500 INTERNAL_ERROR."""
        c = _make_app()
        chain = MagicMock()
        chain.execute.side_effect = RuntimeError("db exploded")
        chain.eq.return_value = chain
        chain.limit.return_value = chain
        chain.select.return_value = chain
        db = MagicMock()
        db.table.return_value.select.return_value = chain
        with patch("api.line_webhook_router._get_supabase_client", return_value=db):
            resp = c.post("/line/webhook", json={"task_id": "task-001"})
        assert resp.status_code == 500
        assert resp.json()["code"] == "INTERNAL_ERROR"

    def test_f2_500_does_not_leak_exception(self) -> None:
        """F2: 500 body does not contain raw exception text."""
        c = _make_app()
        chain = MagicMock()
        chain.execute.side_effect = RuntimeError("top_secret_db_password")
        chain.eq.return_value = chain
        chain.limit.return_value = chain
        chain.select.return_value = chain
        db = MagicMock()
        db.table.return_value.select.return_value = chain
        with patch("api.line_webhook_router._get_supabase_client", return_value=db):
            body = c.post("/line/webhook", json={"task_id": "task-001"}).json()
        assert "top_secret_db_password" not in str(body)


# ===========================================================================
# Group G — booking_state never read
# ===========================================================================

class TestGroupG_NeverQueriesBookingState:

    def test_g1_webhook_does_not_query_booking_state(self) -> None:
        """G1: /line/webhook must not query booking_state table."""
        c = _make_app()
        row = _task_row(status="PENDING")
        db, _, update_chain = _mock_db_for_webhook([row])
        update_chain.execute.return_value = MagicMock(data=[])
        with patch("api.line_webhook_router._get_supabase_client", return_value=db):
            c.post("/line/webhook", json={"task_id": "task-001"})
        calls = [str(c) for c in db.table.call_args_list]
        assert not any("booking_state" in c for c in calls)

    def test_g2_webhook_does_not_query_booking_financial_facts(self) -> None:
        """G2: /line/webhook must not query booking_financial_facts."""
        c = _make_app()
        row = _task_row(status="PENDING")
        db, _, update_chain = _mock_db_for_webhook([row])
        update_chain.execute.return_value = MagicMock(data=[])
        with patch("api.line_webhook_router._get_supabase_client", return_value=db):
            c.post("/line/webhook", json={"task_id": "task-001"})
        calls = [str(c) for c in db.table.call_args_list]
        assert not any("booking_financial_facts" in c for c in calls)
