"""
Phase 230 — AI Audit Log Contract Tests

Covers:
  1. log_ai_interaction() service module — happy path, best-effort (never raises)
  2. GET /admin/ai-audit-log — happy path, filters, pagination, auth guard

All tests use mock Supabase clients — no real DB calls.
"""
from __future__ import annotations

import sys
import types
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers for stubbing Supabase
# ---------------------------------------------------------------------------


def _make_db(rows: list[dict] | None = None, *, fail: bool = False) -> MagicMock:
    """Build a minimal Supabase client stub."""
    db = MagicMock()
    q = db.table.return_value
    # Chain: .table().select().eq()...execute() / .insert().execute()
    for attr in ("select", "eq", "neq", "ilike", "gte", "lte", "order", "range",
                 "limit", "in_", "insert"):
        method = MagicMock(return_value=q)
        setattr(q, attr, method)
    if fail:
        q.execute.side_effect = RuntimeError("simulated_db_error")
    else:
        result = MagicMock()
        result.data = rows or []
        q.execute.return_value = result
    return db


# ---------------------------------------------------------------------------
# Section 1 — log_ai_interaction() service
# ---------------------------------------------------------------------------

from services.ai_audit_log import log_ai_interaction


class TestLogAiInteraction:
    def test_happy_path_minimal(self):
        """Minimal call logs without raising."""
        db = _make_db()
        log_ai_interaction(
            tenant_id="t1",
            endpoint="POST /ai/copilot/morning-briefing",
            request_type="morning_briefing",
            client=db,
        )
        db.table.assert_called_once_with("ai_audit_log")
        insert_call_args = db.table.return_value.insert.call_args[0][0]
        assert insert_call_args["tenant_id"] == "t1"
        assert insert_call_args["endpoint"] == "POST /ai/copilot/morning-briefing"
        assert insert_call_args["request_type"] == "morning_briefing"
        assert insert_call_args["generated_by"] == "heuristic"  # default

    def test_happy_path_all_fields(self):
        """All optional kwargs are passed through correctly."""
        db = _make_db()
        log_ai_interaction(
            tenant_id="t2",
            endpoint="POST /ai/copilot/guest-message-draft",
            request_type="guest_message_draft",
            input_summary="booking_id=BK-999, intent=check_in_instructions",
            output_summary="generated_by=llm, chars=245",
            generated_by="llm",
            entity_type="booking",
            entity_id="BK-999",
            language="th",
            client=db,
        )
        row = db.table.return_value.insert.call_args[0][0]
        assert row["generated_by"] == "llm"
        assert row["entity_type"] == "booking"
        assert row["entity_id"] == "BK-999"
        assert row["language"] == "th"

    def test_best_effort_db_failure_never_raises(self):
        """DB failure must NOT propagate to caller."""
        db = _make_db(fail=True)
        # Should not raise
        log_ai_interaction(
            tenant_id="t3",
            endpoint="POST /ai/copilot/task-recommendations",
            request_type="task_recommendations",
            client=db,
        )

    def test_best_effort_insert_exception_stderr(self, capsys):
        """Failure is printed to stderr with endpoint and tenant info."""
        db = _make_db(fail=True)
        log_ai_interaction(
            tenant_id="tenant_x",
            endpoint="POST /ai/copilot/anomaly-alerts",
            request_type="anomaly_alerts",
            client=db,
        )
        captured = capsys.readouterr()
        assert "anomaly-alerts" in captured.err or "ai_audit_log" in captured.err

    def test_input_summary_capped_at_500_chars(self):
        """Long input_summary is capped to 500 chars before insert."""
        db = _make_db()
        long_value = "x" * 1000
        log_ai_interaction(
            tenant_id="t4",
            endpoint="ep",
            request_type="rt",
            input_summary=long_value,
            client=db,
        )
        row = db.table.return_value.insert.call_args[0][0]
        assert len(row["input_summary"]) <= 500

    def test_output_summary_capped_at_500_chars(self):
        """Long output_summary is capped to 500 chars before insert."""
        db = _make_db()
        long_value = "y" * 2000
        log_ai_interaction(
            tenant_id="t5",
            endpoint="ep",
            request_type="rt",
            output_summary=long_value,
            client=db,
        )
        row = db.table.return_value.insert.call_args[0][0]
        assert len(row["output_summary"]) <= 500

    def test_optional_fields_absent_when_not_provided(self):
        """entity_type, entity_id, language NOT inserted when not provided."""
        db = _make_db()
        log_ai_interaction(
            tenant_id="t6", endpoint="ep", request_type="rt", client=db
        )
        row = db.table.return_value.insert.call_args[0][0]
        assert "entity_type" not in row
        assert "entity_id" not in row
        assert "language" not in row

    def test_generated_by_defaults_to_heuristic(self):
        db = _make_db()
        log_ai_interaction(tenant_id="t7", endpoint="ep", request_type="rt", client=db)
        row = db.table.return_value.insert.call_args[0][0]
        assert row["generated_by"] == "heuristic"

    def test_generated_by_llm(self):
        db = _make_db()
        log_ai_interaction(
            tenant_id="t8", endpoint="ep", request_type="rt",
            generated_by="llm", client=db,
        )
        row = db.table.return_value.insert.call_args[0][0]
        assert row["generated_by"] == "llm"


# ---------------------------------------------------------------------------
# Section 2 — GET /admin/ai-audit-log router
# ---------------------------------------------------------------------------

from fastapi.testclient import TestClient
from fastapi import FastAPI

from api.ai_audit_log_router import router as audit_router, _fetch_ai_audit_log
import api.ai_audit_log_router as _audit_mod


def _app_with_tenant(tenant_id: str = "tenant-1") -> TestClient:
    """Build minimal test app with stubbed jwt_auth."""
    app = FastAPI()

    from unittest.mock import MagicMock

    def _fake_jwt():
        return tenant_id

    app.dependency_overrides = {}
    from api.auth import jwt_auth as real_jwt_auth
    app.dependency_overrides[real_jwt_auth] = _fake_jwt
    app.include_router(audit_router)
    return TestClient(app, raise_server_exceptions=False)


_SAMPLE_ROW = {
    "id": 1,
    "tenant_id": "tenant-1",
    "endpoint": "POST /ai/copilot/morning-briefing",
    "request_type": "morning_briefing",
    "input_summary": "language=en",
    "output_summary": "generated_by=heuristic, action_items=2",
    "generated_by": "heuristic",
    "entity_type": None,
    "entity_id": None,
    "language": "en",
    "created_at": "2026-03-11T12:00:00Z",
}


class TestAiAuditLogRouter:
    def test_happy_path_returns_200(self):
        """Endpoint returns 200 with correct shape."""
        with patch.object(_audit_mod, "_get_db", return_value=_make_db(rows=[_SAMPLE_ROW])):
            client = _app_with_tenant()
            resp = client.get(
                "/admin/ai-audit-log",
                headers={"Authorization": "Bearer fake"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tenant_id"] == "tenant-1"
        assert data["total_returned"] == 1
        assert len(data["entries"]) == 1

    def test_empty_result_returns_200(self):
        """Empty DB result is valid — total_returned=0."""
        with patch.object(_audit_mod, "_get_db", return_value=_make_db(rows=[])):
            client = _app_with_tenant()
            resp = client.get("/admin/ai-audit-log", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_returned"] == 0
        assert data["entries"] == []

    def test_filters_applied_in_response(self):
        """When filters are provided, they appear in filters_applied."""
        with patch.object(_audit_mod, "_get_db", return_value=_make_db(rows=[])):
            client = _app_with_tenant()
            resp = client.get(
                "/admin/ai-audit-log",
                params={
                    "endpoint": "morning-briefing",
                    "request_type": "morning_briefing",
                    "generated_by": "heuristic",
                    "from_date": "2026-03-01",
                    "to_date": "2026-03-11",
                },
                headers={"Authorization": "Bearer fake"},
            )
        assert resp.status_code == 200
        fa = resp.json()["filters_applied"]
        assert fa["endpoint"] == "morning-briefing"
        assert fa["request_type"] == "morning_briefing"
        assert fa["generated_by"] == "heuristic"
        assert fa["from_date"] == "2026-03-01"
        assert fa["to_date"] == "2026-03-11"

    def test_no_filters_gives_empty_filters_applied(self):
        """With no filters, filters_applied is empty dict."""
        with patch.object(_audit_mod, "_get_db", return_value=_make_db(rows=[])):
            client = _app_with_tenant()
            resp = client.get("/admin/ai-audit-log", headers={"Authorization": "Bearer fake"})
        assert resp.json()["filters_applied"] == {}

    def test_limit_and_offset_in_response(self):
        """limit and offset values are echoed in response."""
        with patch.object(_audit_mod, "_get_db", return_value=_make_db(rows=[])):
            client = _app_with_tenant()
            resp = client.get(
                "/admin/ai-audit-log",
                params={"limit": 10, "offset": 20},
                headers={"Authorization": "Bearer fake"},
            )
        data = resp.json()
        assert data["limit"] == 10
        assert data["offset"] == 20

    def test_db_failure_returns_500(self):
        """DB connection failure results in 500 error."""
        with patch.object(_audit_mod, "_get_db", side_effect=RuntimeError("DB down")):
            client = _app_with_tenant()
            resp = client.get("/admin/ai-audit-log", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 500

    def test_fetch_ai_audit_log_returns_empty_on_error(self):
        """_fetch_ai_audit_log is best-effort — returns [] on error."""
        db = _make_db(fail=True)
        rows = _fetch_ai_audit_log(
            db=db,
            tenant_id="t1",
            endpoint=None,
            request_type=None,
            generated_by=None,
            from_date=None,
            to_date=None,
            limit=50,
            offset=0,
        )
        assert rows == []

    def test_fetch_with_generated_by_filter(self):
        """generated_by filter is applied to query."""
        db = _make_db(rows=[_SAMPLE_ROW])
        rows = _fetch_ai_audit_log(
            db=db,
            tenant_id="tenant-1",
            endpoint=None,
            request_type=None,
            generated_by="heuristic",
            from_date=None,
            to_date=None,
            limit=50,
            offset=0,
        )
        assert len(rows) == 1

    def test_fetch_with_invalid_generated_by_skips_filter(self):
        """generated_by='unknown_value' (not llm/heuristic) is silently skipped."""
        db = _make_db(rows=[_SAMPLE_ROW])
        rows = _fetch_ai_audit_log(
            db=db,
            tenant_id="tenant-1",
            endpoint=None,
            request_type=None,
            generated_by="unknown_value",
            from_date=None,
            to_date=None,
            limit=50,
            offset=0,
        )
        assert isinstance(rows, list)
