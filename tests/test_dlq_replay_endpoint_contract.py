"""
Phase 205 — DLQ Replay Endpoint — Contract Tests

Endpoint:
    POST /admin/dlq/{envelope_id}/replay

Groups:
    A — 404 for unknown envelope_id
    B — Happy path (pending row) → replay_result returned
    C — Already-applied row → 200 with already_replayed=true (idempotent)
    D — Replay engine error → 500 INTERNAL_ERROR
    E — Auth guard → 403
    F — DB lookup error → 500 INTERNAL_ERROR
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("fastapi")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db_lookup_empty() -> MagicMock:
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=[])
    chain.eq.return_value = chain
    chain.select.return_value = chain
    chain.limit.return_value = chain
    db = MagicMock()
    db.table.return_value.select.return_value = chain
    return db


def _make_db_lookup_row(
    row_id: int = 42,
    envelope_id: str = "env-001",
    replay_result: str | None = None,
) -> MagicMock:
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=[{
        "id": row_id,
        "envelope_id": envelope_id,
        "replay_result": replay_result,
    }])
    chain.eq.return_value = chain
    chain.select.return_value = chain
    chain.limit.return_value = chain
    db = MagicMock()
    db.table.return_value.select.return_value = chain
    return db


def _make_app(tenant_id: str = "tenant_test") -> TestClient:
    from fastapi import FastAPI
    from api.dlq_router import router
    from api.auth import jwt_auth

    app = FastAPI()

    async def _stub_auth():
        return tenant_id

    app.dependency_overrides[jwt_auth] = _stub_auth
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def _make_reject_app() -> TestClient:
    from fastapi import FastAPI, HTTPException
    from api.dlq_router import router
    from api.auth import jwt_auth

    app = FastAPI()

    async def _reject():
        raise HTTPException(status_code=403, detail="AUTH_FAILED")

    app.dependency_overrides[jwt_auth] = _reject
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def _fake_replay_success(row_id: int) -> dict:
    return {
        "row_id": row_id,
        "replay_result": "APPLIED",
        "replay_trace_id": f"dlq-replay-{row_id}-abc12345",
        "already_replayed": False,
        "apply_result": {"status": "APPLIED"},
    }


# ===========================================================================
# Group A — 404 for unknown envelope_id
# ===========================================================================

class TestGroupA_NotFound:

    def test_a1_unknown_envelope_returns_404(self) -> None:
        """A1: POST replay on unknown envelope_id → 404 NOT_FOUND."""
        c = _make_app()
        db = _make_db_lookup_empty()
        with patch("api.dlq_router._get_supabase_client", return_value=db):
            resp = c.post("/admin/dlq/no-such-id/replay")
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    def test_a2_404_message_includes_envelope_id(self) -> None:
        """A2: 404 message references the unknown envelope_id."""
        c = _make_app()
        db = _make_db_lookup_empty()
        with patch("api.dlq_router._get_supabase_client", return_value=db):
            body = c.post("/admin/dlq/mystery-env/replay").json()
        assert "mystery-env" in body["message"]


# ===========================================================================
# Group B — Happy path (pending row)
# ===========================================================================

class TestGroupB_HappyPath:

    def test_b1_pending_row_returns_200(self) -> None:
        """B1: Pending row → 200 with replay_result."""
        c = _make_app()
        db = _make_db_lookup_row(row_id=42, envelope_id="env-001", replay_result=None)
        with patch("api.dlq_router._get_supabase_client", return_value=db), \
             patch("api.dlq_router._get_replay_fn", return_value=_fake_replay_success):
            resp = c.post("/admin/dlq/env-001/replay")
        assert resp.status_code == 200

    def test_b2_response_has_envelope_id(self) -> None:
        """B2: Response contains the original envelope_id."""
        c = _make_app()
        db = _make_db_lookup_row(row_id=5, envelope_id="env-abc")
        with patch("api.dlq_router._get_supabase_client", return_value=db), \
             patch("api.dlq_router._get_replay_fn", return_value=_fake_replay_success):
            body = c.post("/admin/dlq/env-abc/replay").json()
        assert body["envelope_id"] == "env-abc"

    def test_b3_response_has_replay_result(self) -> None:
        """B3: Response contains replay_result field."""
        c = _make_app()
        db = _make_db_lookup_row(row_id=5, envelope_id="env-abc")
        with patch("api.dlq_router._get_supabase_client", return_value=db), \
             patch("api.dlq_router._get_replay_fn", return_value=_fake_replay_success):
            body = c.post("/admin/dlq/env-abc/replay").json()
        assert "replay_result" in body

    def test_b4_response_has_replay_trace_id(self) -> None:
        """B4: Response contains replay_trace_id."""
        c = _make_app()
        db = _make_db_lookup_row(row_id=5, envelope_id="env-abc")
        with patch("api.dlq_router._get_supabase_client", return_value=db), \
             patch("api.dlq_router._get_replay_fn", return_value=_fake_replay_success):
            body = c.post("/admin/dlq/env-abc/replay").json()
        assert "replay_trace_id" in body

    def test_b5_already_replayed_false_for_new_replay(self) -> None:
        """B5: already_replayed=False for a fresh replay."""
        c = _make_app()
        db = _make_db_lookup_row(row_id=5, envelope_id="env-abc")
        with patch("api.dlq_router._get_supabase_client", return_value=db), \
             patch("api.dlq_router._get_replay_fn", return_value=_fake_replay_success):
            body = c.post("/admin/dlq/env-abc/replay").json()
        assert body["already_replayed"] is False

    def test_b6_row_id_in_response(self) -> None:
        """B6: row_id (numeric) is present in response."""
        c = _make_app()
        db = _make_db_lookup_row(row_id=99, envelope_id="env-99")
        with patch("api.dlq_router._get_supabase_client", return_value=db), \
             patch("api.dlq_router._get_replay_fn", return_value=_fake_replay_success):
            body = c.post("/admin/dlq/env-99/replay").json()
        assert body["row_id"] == 99


# ===========================================================================
# Group C — Already-applied (idempotent)
# ===========================================================================

class TestGroupC_AlreadyApplied:

    @pytest.mark.parametrize("applied_status", ["APPLIED", "ALREADY_APPLIED", "ALREADY_EXISTS", "ALREADY_EXISTS_BUSINESS"])
    def test_c1_applied_statuses_return_already_replayed_true(self, applied_status: str) -> None:
        """C1: Already-applied row → 200 with already_replayed=True, no replay triggered."""
        c = _make_app()
        db = _make_db_lookup_row(envelope_id="env-done", replay_result=applied_status)
        with patch("api.dlq_router._get_supabase_client", return_value=db):
            body = c.post("/admin/dlq/env-done/replay").json()
        assert body["already_replayed"] is True

    def test_c2_already_applied_does_not_call_replay_fn(self) -> None:
        """C2: Already-applied row must NOT call replay_dlq_row."""
        c = _make_app()
        db = _make_db_lookup_row(envelope_id="env-done", replay_result="APPLIED")
        mock_replay = MagicMock()
        with patch("api.dlq_router._get_supabase_client", return_value=db), \
             patch("api.dlq_router._get_replay_fn", return_value=mock_replay):
            c.post("/admin/dlq/env-done/replay")
        mock_replay.assert_not_called()

    def test_c3_already_applied_returns_200(self) -> None:
        """C3: Already-applied row returns 200 (not 400 or 409)."""
        c = _make_app()
        db = _make_db_lookup_row(envelope_id="env-done", replay_result="ALREADY_EXISTS")
        with patch("api.dlq_router._get_supabase_client", return_value=db):
            assert c.post("/admin/dlq/env-done/replay").status_code == 200


# ===========================================================================
# Group D — Replay engine error → 500
# ===========================================================================

class TestGroupD_ReplayEngineError:

    def test_d1_replay_exception_returns_500(self) -> None:
        """D1: replay_dlq_row raises → 500 INTERNAL_ERROR."""
        def _bad_replay(row_id: int) -> dict:
            raise RuntimeError("apply_envelope rejected")

        c = _make_app()
        db = _make_db_lookup_row(envelope_id="env-fail")
        with patch("api.dlq_router._get_supabase_client", return_value=db), \
             patch("api.dlq_router._get_replay_fn", return_value=_bad_replay):
            resp = c.post("/admin/dlq/env-fail/replay")
        assert resp.status_code == 500
        assert resp.json()["code"] == "INTERNAL_ERROR"

    def test_d2_500_does_not_leak_exception(self) -> None:
        """D2: 500 body doesn't contain raw exception text."""
        def _bad_replay(row_id: int) -> dict:
            raise RuntimeError("super_secret_error_details")

        c = _make_app()
        db = _make_db_lookup_row(envelope_id="env-fail")
        with patch("api.dlq_router._get_supabase_client", return_value=db), \
             patch("api.dlq_router._get_replay_fn", return_value=_bad_replay):
            body = c.post("/admin/dlq/env-fail/replay").json()
        assert "super_secret_error_details" not in str(body)


# ===========================================================================
# Group E — Auth guard
# ===========================================================================

class TestGroupE_AuthGuard:

    def test_e1_no_auth_returns_403(self) -> None:
        """E1: POST replay without auth → 403."""
        assert _make_reject_app().post("/admin/dlq/env-001/replay").status_code == 403


# ===========================================================================
# Group F — DB lookup error → 500
# ===========================================================================

class TestGroupF_DbLookupError:

    def test_f1_db_lookup_exception_returns_500(self) -> None:
        """F1: DB error during envelope_id lookup → 500 INTERNAL_ERROR."""
        chain = MagicMock()
        chain.execute.side_effect = RuntimeError("db down")
        chain.eq.return_value = chain
        chain.select.return_value = chain
        chain.limit.return_value = chain
        db = MagicMock()
        db.table.return_value.select.return_value = chain

        c = _make_app()
        with patch("api.dlq_router._get_supabase_client", return_value=db):
            resp = c.post("/admin/dlq/env-001/replay")
        assert resp.status_code == 500
        assert resp.json()["code"] == "INTERNAL_ERROR"
