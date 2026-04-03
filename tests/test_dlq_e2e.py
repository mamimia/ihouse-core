"""
Phase 271 — E2E DLQ & Replay Integration Test

Direct async function call tests for:
  - list_dlq_entries  — GET /admin/dlq
  - get_dlq_entry     — GET /admin/dlq/{envelope_id}
  - replay_dlq_entry  — POST /admin/dlq/{envelope_id}/replay

All handlers support client= injection.
replay_dlq_entry also accepts _replay_fn= injection to avoid real Supabase replay.
CI-safe: no live DB, no staging required.
"""
from __future__ import annotations

import asyncio
import os
import sys
from typing import Any
from unittest.mock import MagicMock

os.environ.setdefault("IHOUSE_ENV", "test")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

TENANT = "dev-tenant"
ENVELOPE_ID = "env-abc123"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _q(rows: list):
    q = MagicMock()
    q.select.return_value = q
    q.eq.return_value = q
    q.neq.return_value = q
    q.in_.return_value = q
    q.gte.return_value = q
    q.lte.return_value = q
    q.limit.return_value = q
    q.order.return_value = q
    q.update.return_value = q
    q.insert.return_value = q
    q.execute.return_value = MagicMock(data=rows)
    return q


def _db(rows: list | None = None):
    db = MagicMock()
    rows = rows if rows is not None else [_dlq_row()]
    db.table.return_value = _q(rows)
    return db


def _run(coro):
    return asyncio.run(coro)


def _dlq_row(**overrides):
    base = {
        "id":            1,
        "envelope_id":   ENVELOPE_ID,
        "source":        "bookingcom",
        "replay_result": None,
        "error_reason":  "ADAPTER_NOT_FOUND",
        "error":         "No adapter for provider",
        "raw_payload":   b'{"event": "test"}',
        "payload":       {"event": "test"},
        "created_at":    "2026-03-11T00:00:00Z",
        "replayed_at":   None,
    }
    base.update(overrides)
    return base


def _replay_fn_success(row_id: int) -> dict:
    return {
        "replay_result":    "SUCCESS",
        "replay_trace_id":  f"trace-{row_id}",
        "already_replayed": False,
    }


def _replay_fn_fail(row_id: int) -> dict:
    return {
        "replay_result":    "FAILED",
        "replay_trace_id":  None,
        "already_replayed": False,
    }


# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

from api.dlq_router import (  # noqa: E402
    list_dlq_entries,
    get_dlq_entry,
    replay_dlq_entry,
)


# ---------------------------------------------------------------------------
# Group A — list_dlq_entries
# ---------------------------------------------------------------------------

class TestGroupAListDlq:

    def test_a1_returns_200_with_entries(self):
        import json
        db = _db()
        r = _run(list_dlq_entries(identity={"tenant_id": TENANT, "role": "admin"}, client=db))
        assert r.status_code == 200, f"Got {r.status_code}: {r.body}"
        body = json.loads(r.body)
        assert "entries" in body

    def test_a2_total_count_present(self):
        import json
        db = _db()
        r = _run(list_dlq_entries(identity={"tenant_id": TENANT, "role": "admin"}, client=db))
        assert "total" in json.loads(r.body)

    def test_a3_empty_db_returns_zero_total(self):
        import json
        db = _db([])
        r = _run(list_dlq_entries(identity={"tenant_id": TENANT, "role": "admin"}, client=db))
        assert json.loads(r.body)["total"] == 0

    def test_a4_invalid_status_returns_400(self):
        r = _run(list_dlq_entries(identity={"tenant_id": TENANT, "role": "admin"}, status="FLYING"))
        assert r.status_code == 400

    def test_a5_invalid_limit_returns_400(self):
        r = _run(list_dlq_entries(identity={"tenant_id": TENANT, "role": "admin"}, limit=0))
        assert r.status_code == 400

    def test_a6_status_filter_propagated_in_response(self):
        import json
        db = _db([])
        r = _run(list_dlq_entries(identity={"tenant_id": TENANT, "role": "admin"}, status="pending", client=db))
        body = json.loads(r.body)
        assert body["status_filter"] == "pending"

    def test_a7_source_filter_propagated_in_response(self):
        import json
        db = _db([])
        r = _run(list_dlq_entries(identity={"tenant_id": TENANT, "role": "admin"}, source="airbnb", client=db))
        body = json.loads(r.body)
        assert body["source_filter"] == "airbnb"


# ---------------------------------------------------------------------------
# Group B — get_dlq_entry
# ---------------------------------------------------------------------------

class TestGroupBGetDlqEntry:

    def test_b1_returns_200_when_found(self):
        db = _db()
        r = _run(get_dlq_entry(envelope_id=ENVELOPE_ID, identity={"tenant_id": TENANT, "role": "admin"}, client=db))
        assert r.status_code == 200, f"Got {r.status_code}: {r.body}"

    def test_b2_envelope_id_in_response(self):
        import json
        db = _db()
        r = _run(get_dlq_entry(envelope_id=ENVELOPE_ID, identity={"tenant_id": TENANT, "role": "admin"}, client=db))
        body = json.loads(r.body)
        assert "envelope_id" in body or "entry" in body

    def test_b3_returns_404_when_not_found(self):
        db = _db([])
        r = _run(get_dlq_entry(envelope_id="ghost-env", identity={"tenant_id": TENANT, "role": "admin"}, client=db))
        assert r.status_code == 404

    def test_b4_entry_has_source_field(self):
        import json
        db = _db()
        r = _run(get_dlq_entry(envelope_id=ENVELOPE_ID, identity={"tenant_id": TENANT, "role": "admin"}, client=db))
        body = json.loads(r.body)
        entry = body.get("entry", body)
        assert "source" in entry or "envelope_id" in body


# ---------------------------------------------------------------------------
# Group C — replay_dlq_entry
# ---------------------------------------------------------------------------

class TestGroupCReplayDlq:

    def test_c1_replay_success_returns_200(self):
        db = _db()
        r = _run(replay_dlq_entry(
            envelope_id=ENVELOPE_ID,
            identity={"tenant_id": TENANT, "role": "admin"},
            client=db,
            _replay_fn=_replay_fn_success,
        ))
        assert r.status_code == 200, f"Got {r.status_code}: {r.body}"

    def test_c2_replay_success_result_in_response(self):
        import json
        db = _db()
        r = _run(replay_dlq_entry(
            envelope_id=ENVELOPE_ID,
            identity={"tenant_id": TENANT, "role": "admin"},
            client=db,
            _replay_fn=_replay_fn_success,
        ))
        body = json.loads(r.body)
        assert body["replay_result"] == "SUCCESS"

    def test_c3_envelope_id_in_replay_response(self):
        import json
        db = _db()
        r = _run(replay_dlq_entry(
            envelope_id=ENVELOPE_ID,
            identity={"tenant_id": TENANT, "role": "admin"},
            client=db,
            _replay_fn=_replay_fn_success,
        ))
        body = json.loads(r.body)
        assert body["envelope_id"] == ENVELOPE_ID

    def test_c4_replay_trace_id_present(self):
        import json
        db = _db()
        r = _run(replay_dlq_entry(
            envelope_id=ENVELOPE_ID,
            identity={"tenant_id": TENANT, "role": "admin"},
            client=db,
            _replay_fn=_replay_fn_success,
        ))
        assert "replay_trace_id" in json.loads(r.body)

    def test_c5_not_found_returns_404(self):
        db = _db([])
        r = _run(replay_dlq_entry(
            envelope_id="ghost-env",
            identity={"tenant_id": TENANT, "role": "admin"},
            client=db,
            _replay_fn=_replay_fn_success,
        ))
        assert r.status_code == 404

    def test_c6_already_replayed_returns_200_with_flag(self):
        import json
        already_applied_row = _dlq_row(replay_result="APPLIED")
        db = _db([already_applied_row])
        r = _run(replay_dlq_entry(
            envelope_id=ENVELOPE_ID,
            identity={"tenant_id": TENANT, "role": "admin"},
            client=db,
            _replay_fn=_replay_fn_success,
        ))
        body = json.loads(r.body)
        assert r.status_code == 200
        assert body.get("already_replayed") is True

    def test_c7_replay_failed_returns_200_with_failed_result(self):
        import json
        db = _db()
        r = _run(replay_dlq_entry(
            envelope_id=ENVELOPE_ID,
            identity={"tenant_id": TENANT, "role": "admin"},
            client=db,
            _replay_fn=_replay_fn_fail,
        ))
        body = json.loads(r.body)
        assert r.status_code == 200
        assert body["replay_result"] == "FAILED"
