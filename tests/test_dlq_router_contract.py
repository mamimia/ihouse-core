"""
Phase 131 — DLQ Inspector — Contract Tests

Tests for:
  GET /admin/dlq              — list DLQ entries
  GET /admin/dlq/{envelope_id} — single entry with full payload

Groups:
    A — List endpoint: empty DLQ
    B — List endpoint: entry fields and shape
    C — Status derivation (pending/applied/error)
    D — Status filter
    E — Source filter
    F — Limit parameter
    G — Single entry: found
    H — Single entry: not found
    I — Payload handling (preview vs full)
    J — DB invariants: reads ota_dead_letter, never writes
    K — Error handling: DB failure → 500
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("fastapi")

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_FAKE_TENANT = "tenant_test"


def _make_app() -> TestClient:
    from fastapi import FastAPI
    from api.dlq_router import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def _mock_db(rows: List[Dict[str, Any]]) -> MagicMock:
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=rows)
    chain.eq.return_value = chain
    chain.select.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    db = MagicMock()
    db.table.return_value.select.return_value = chain
    return db


def _get_list(c: TestClient, db: MagicMock, path: str = "/admin/dlq") -> Any:
    with (
        patch("api.dlq_router._get_supabase_client", return_value=db),
        patch("api.auth.jwt_auth", return_value=_FAKE_TENANT),
    ):
        return c.get(path, headers={"Authorization": "Bearer fake.jwt"})


def _get_single(c: TestClient, db: MagicMock, envelope_id: str) -> Any:
    with (
        patch("api.dlq_router._get_supabase_client", return_value=db),
        patch("api.auth.jwt_auth", return_value=_FAKE_TENANT),
    ):
        return c.get(
            f"/admin/dlq/{envelope_id}",
            headers={"Authorization": "Bearer fake.jwt"},
        )


def _dlq_row(
    envelope_id: str = "env_001",
    source: str = "airbnb",
    replay_result: Optional[str] = None,
    error_reason: Optional[str] = None,
    raw_payload: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "id": f"id_{envelope_id}",
        "envelope_id": envelope_id,
        "source": source,
        "replay_result": replay_result,
        "error_reason": error_reason,
        "error": None,
        "raw_payload": raw_payload or '{"booking_id": "bk_1"}',
        "payload": None,
        "created_at": "2026-03-09T10:00:00Z",
        "replayed_at": None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# A — List: empty DLQ
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupA_EmptyDLQ:

    def test_a1_empty_returns_200(self) -> None:
        """A1: Empty DLQ → 200 OK."""
        c = _make_app()
        resp = _get_list(c, _mock_db([]))
        assert resp.status_code == 200

    def test_a2_empty_entries_list(self) -> None:
        """A2: Empty DLQ → entries=[]."""
        c = _make_app()
        body = _get_list(c, _mock_db([])).json()
        assert body["entries"] == []

    def test_a3_total_zero(self) -> None:
        """A3: Empty DLQ → total=0."""
        c = _make_app()
        body = _get_list(c, _mock_db([])).json()
        assert body["total"] == 0

    def test_a4_response_has_filter_fields(self) -> None:
        """A4: Response includes status_filter and source_filter."""
        c = _make_app()
        body = _get_list(c, _mock_db([])).json()
        assert "status_filter" in body
        assert "source_filter" in body


# ─────────────────────────────────────────────────────────────────────────────
# B — Entry fields and shape
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupB_EntryShape:

    def test_b1_entry_has_required_fields(self) -> None:
        """B1: Each entry has: envelope_id, source, replay_result, status,
        error_reason, created_at, replayed_at, payload_preview."""
        rows = [_dlq_row()]
        c = _make_app()
        body = _get_list(c, _mock_db(rows)).json()
        entry = body["entries"][0]
        required = {
            "envelope_id", "source", "replay_result", "status",
            "error_reason", "created_at", "replayed_at", "payload_preview",
        }
        assert required.issubset(entry.keys())

    def test_b2_list_entry_has_no_raw_payload(self) -> None:
        """B2: List entries do NOT include raw_payload (full payload)."""
        rows = [_dlq_row()]
        c = _make_app()
        body = _get_list(c, _mock_db(rows)).json()
        assert "raw_payload" not in body["entries"][0]

    def test_b3_envelope_id_correct(self) -> None:
        """B3: entry.envelope_id matches the row's envelope_id."""
        rows = [_dlq_row(envelope_id="env_XYZ")]
        c = _make_app()
        body = _get_list(c, _mock_db(rows)).json()
        assert body["entries"][0]["envelope_id"] == "env_XYZ"

    def test_b4_source_correct(self) -> None:
        """B4: entry.source matches the row's source."""
        rows = [_dlq_row(source="bookingcom")]
        c = _make_app()
        body = _get_list(c, _mock_db(rows)).json()
        assert body["entries"][0]["source"] == "bookingcom"


# ─────────────────────────────────────────────────────────────────────────────
# C — Status derivation
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupC_StatusDerivation:

    def test_c1_null_replay_result_is_pending(self) -> None:
        """C1: replay_result=null → status='pending'."""
        from api.dlq_router import _derive_status
        assert _derive_status(None) == "pending"

    def test_c2_applied_status_is_applied(self) -> None:
        """C2: replay_result='APPLIED' → status='applied'."""
        from api.dlq_router import _derive_status
        assert _derive_status("APPLIED") == "applied"

    def test_c3_already_exists_is_applied(self) -> None:
        """C3: replay_result='ALREADY_EXISTS' → status='applied'."""
        from api.dlq_router import _derive_status
        assert _derive_status("ALREADY_EXISTS") == "applied"

    def test_c4_already_applied_is_applied(self) -> None:
        """C4: replay_result='ALREADY_APPLIED' → status='applied'."""
        from api.dlq_router import _derive_status
        assert _derive_status("ALREADY_APPLIED") == "applied"

    def test_c5_error_status_is_error(self) -> None:
        """C5: replay_result='SCHEMA_ERROR' → status='error'."""
        from api.dlq_router import _derive_status
        assert _derive_status("SCHEMA_ERROR") == "error"

    def test_c6_unknown_result_is_error(self) -> None:
        """C6: replay_result='UNKNOWN_FAILURE' → status='error'."""
        from api.dlq_router import _derive_status
        assert _derive_status("UNKNOWN_FAILURE") == "error"

    def test_c7_status_visible_in_api_response(self) -> None:
        """C7: Derived status visible in list response."""
        rows = [_dlq_row(replay_result=None)]
        c = _make_app()
        body = _get_list(c, _mock_db(rows)).json()
        assert body["entries"][0]["status"] == "pending"

    def test_c8_applied_status_in_api_response(self) -> None:
        """C8: APPLIED replay_result → status='applied' in response."""
        rows = [_dlq_row(replay_result="APPLIED")]
        c = _make_app()
        body = _get_list(c, _mock_db(rows)).json()
        assert body["entries"][0]["status"] == "applied"


# ─────────────────────────────────────────────────────────────────────────────
# D — Status filter
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupD_StatusFilter:

    def test_d1_invalid_status_returns_400(self) -> None:
        """D1: ?status=bogus → 400."""
        c = _make_app()
        resp = _get_list(c, _mock_db([]), "/admin/dlq?status=bogus")
        assert resp.status_code == 400

    def test_d2_status_all_returns_200(self) -> None:
        """D2: ?status=all → 200 OK."""
        c = _make_app()
        resp = _get_list(c, _mock_db([]), "/admin/dlq?status=all")
        assert resp.status_code == 200

    def test_d3_status_pending_returns_200(self) -> None:
        """D3: ?status=pending → 200 OK."""
        c = _make_app()
        resp = _get_list(c, _mock_db([]), "/admin/dlq?status=pending")
        assert resp.status_code == 200

    def test_d4_status_applied_returns_200(self) -> None:
        """D4: ?status=applied → 200 OK."""
        c = _make_app()
        resp = _get_list(c, _mock_db([]), "/admin/dlq?status=applied")
        assert resp.status_code == 200

    def test_d5_status_error_returns_200(self) -> None:
        """D5: ?status=error → 200 OK."""
        c = _make_app()
        resp = _get_list(c, _mock_db([]), "/admin/dlq?status=error")
        assert resp.status_code == 200

    def test_d6_pending_filter_excludes_applied(self) -> None:
        """D6: ?status=pending filters out rows with replay_result set."""
        rows = [
            _dlq_row("env_1", replay_result=None),
            _dlq_row("env_2", replay_result="APPLIED"),
        ]
        c = _make_app()
        body = _get_list(c, _mock_db(rows), "/admin/dlq?status=pending").json()
        assert body["total"] == 1
        assert body["entries"][0]["envelope_id"] == "env_1"

    def test_d7_applied_filter_excludes_pending(self) -> None:
        """D7: ?status=applied → only APPLIED rows returned."""
        rows = [
            _dlq_row("env_1", replay_result=None),
            _dlq_row("env_2", replay_result="ALREADY_EXISTS"),
        ]
        c = _make_app()
        body = _get_list(c, _mock_db(rows), "/admin/dlq?status=applied").json()
        assert body["total"] == 1
        assert body["entries"][0]["envelope_id"] == "env_2"

    def test_d8_default_status_is_all(self) -> None:
        """D8: No status filter → status_filter='all' in response."""
        c = _make_app()
        body = _get_list(c, _mock_db([])).json()
        assert body["status_filter"] == "all"


# ─────────────────────────────────────────────────────────────────────────────
# E — Source filter
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupE_SourceFilter:

    def test_e1_source_forwarded_to_db(self) -> None:
        """E1: ?source=airbnb → .eq('source', 'airbnb') called."""
        db = _mock_db([])
        c = _make_app()
        _get_list(c, db, "/admin/dlq?source=airbnb")
        eq_calls = [str(call) for call in db.table.return_value.select.return_value.eq.call_args_list]
        assert any("airbnb" in call for call in eq_calls)

    def test_e2_source_filter_in_response(self) -> None:
        """E2: ?source=airbnb → source_filter='airbnb' in response."""
        c = _make_app()
        body = _get_list(c, _mock_db([]), "/admin/dlq?source=airbnb").json()
        assert body["source_filter"] == "airbnb"

    def test_e3_no_source_filter_is_none_in_response(self) -> None:
        """E3: No source filter → source_filter=null in response."""
        c = _make_app()
        body = _get_list(c, _mock_db([])).json()
        assert body["source_filter"] is None


# ─────────────────────────────────────────────────────────────────────────────
# F — Limit parameter
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupF_Limit:

    def test_f1_limit_zero_returns_400(self) -> None:
        """F1: limit=0 → 400."""
        c = _make_app()
        resp = _get_list(c, _mock_db([]), "/admin/dlq?limit=0")
        assert resp.status_code == 400

    def test_f2_limit_over_100_returns_400(self) -> None:
        """F2: limit=101 → 400 (max is 100)."""
        c = _make_app()
        resp = _get_list(c, _mock_db([]), "/admin/dlq?limit=101")
        assert resp.status_code == 400

    def test_f3_valid_limit_returns_200(self) -> None:
        """F3: limit=10 → 200 OK."""
        c = _make_app()
        resp = _get_list(c, _mock_db([]), "/admin/dlq?limit=10")
        assert resp.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# G — Single entry: found
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupG_SingleEntry:

    def test_g1_single_entry_returns_200(self) -> None:
        """G1: Found envelope_id → 200 OK."""
        rows = [_dlq_row(envelope_id="env_001")]
        c = _make_app()
        resp = _get_single(c, _mock_db(rows), "env_001")
        assert resp.status_code == 200

    def test_g2_single_entry_has_envelope_id(self) -> None:
        """G2: Single entry response has envelope_id field."""
        rows = [_dlq_row(envelope_id="env_001")]
        c = _make_app()
        body = _get_single(c, _mock_db(rows), "env_001").json()
        assert body["envelope_id"] == "env_001"

    def test_g3_single_entry_has_raw_payload(self) -> None:
        """G3: Single entry response includes raw_payload (full payload)."""
        rows = [_dlq_row(raw_payload='{"booking_id":"bk_full"}')]
        c = _make_app()
        body = _get_single(c, _mock_db(rows), "env_001").json()
        assert "raw_payload" in body
        assert body["raw_payload"] == '{"booking_id":"bk_full"}'


# ─────────────────────────────────────────────────────────────────────────────
# H — Single entry: not found
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupH_NotFound:

    def test_h1_missing_entry_returns_404(self) -> None:
        """H1: No row for envelope_id → 404."""
        c = _make_app()
        resp = _get_single(c, _mock_db([]), "env_not_exist")
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# I — Payload handling
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupI_Payload:

    def test_i1_payload_preview_truncated_to_200(self) -> None:
        """I1: List endpoint payload_preview ≤ 200 chars."""
        long_payload = "X" * 500
        rows = [_dlq_row(raw_payload=long_payload)]
        c = _make_app()
        body = _get_list(c, _mock_db(rows)).json()
        preview = body["entries"][0]["payload_preview"]
        assert len(preview) == 200

    def test_i2_short_payload_preview_not_truncated(self) -> None:
        """I2: Short payload → preview = full payload."""
        short = '{"x": 1}'
        rows = [_dlq_row(raw_payload=short)]
        c = _make_app()
        body = _get_list(c, _mock_db(rows)).json()
        assert body["entries"][0]["payload_preview"] == short

    def test_i3_null_payload_gives_null_preview(self) -> None:
        """I3: null raw_payload → payload_preview=null."""
        row = {
            "id": "id_1",
            "envelope_id": "env_1",
            "source": "airbnb",
            "replay_result": None,
            "error_reason": None,
            "error": None,
            "raw_payload": None,
            "payload": None,
            "created_at": "2026-03-01T00:00:00Z",
            "replayed_at": None,
        }
        c = _make_app()
        body = _get_list(c, _mock_db([row])).json()
        assert body["entries"][0]["payload_preview"] is None


# ─────────────────────────────────────────────────────────────────────────────
# J — DB invariants
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupJ_DBInvariants:

    def test_j1_reads_ota_dead_letter(self) -> None:
        """J1: Reads from ota_dead_letter table."""
        db = _mock_db([])
        c = _make_app()
        _get_list(c, db)
        tables = [str(call.args[0]) for call in db.table.call_args_list]
        assert any("ota_dead_letter" in t for t in tables)

    def test_j2_never_writes_insert(self) -> None:
        """J2: Never calls .insert()."""
        db = _mock_db([])
        c = _make_app()
        _get_list(c, db)
        assert db.table.return_value.insert.call_count == 0

    def test_j3_never_writes_update(self) -> None:
        """J3: Never calls .update()."""
        db = _mock_db([])
        c = _make_app()
        _get_list(c, db)
        assert db.table.return_value.update.call_count == 0

    def test_j4_never_reads_booking_state(self) -> None:
        """J4: Never reads booking_state (DLQ is global, not booking-scoped)."""
        db = _mock_db([])
        c = _make_app()
        _get_list(c, db)
        tables = [str(call.args[0]) for call in db.table.call_args_list]
        assert not any("booking_state" in t for t in tables)


# ─────────────────────────────────────────────────────────────────────────────
# K — Error handling
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupK_ErrorHandling:

    def test_k1_db_error_list_returns_500(self) -> None:
        """K1: DB throws on list → 500."""
        chain = MagicMock()
        chain.execute.side_effect = RuntimeError("db down")
        chain.eq.return_value = chain
        chain.select.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = chain
        db = MagicMock()
        db.table.return_value.select.return_value = chain
        c = _make_app()
        resp = _get_list(c, db)
        assert resp.status_code == 500

    def test_k2_db_error_single_returns_500(self) -> None:
        """K2: DB throws on single entry → 500."""
        chain = MagicMock()
        chain.execute.side_effect = RuntimeError("db down")
        chain.eq.return_value = chain
        chain.select.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = chain
        db = MagicMock()
        db.table.return_value.select.return_value = chain
        c = _make_app()
        resp = _get_single(c, db, "env_001")
        assert resp.status_code == 500

    def test_k3_500_body_no_sensitive_leak(self) -> None:
        """K3: 500 response does not expose internal exception message."""
        chain = MagicMock()
        chain.execute.side_effect = RuntimeError("internal_secret_xyz")
        chain.eq.return_value = chain
        chain.select.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = chain
        db = MagicMock()
        db.table.return_value.select.return_value = chain
        c = _make_app()
        resp = _get_list(c, db)
        assert "internal_secret_xyz" not in resp.text
