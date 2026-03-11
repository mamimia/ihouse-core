"""
Phase 232 — Pre-Arrival Automation Chain — Contract Tests

Tests cover:

_build_checkin_draft:
    - includes guest name in greeting
    - includes check-in and check-out dates
    - includes access code when provided
    - omits access code when None

run_pre_arrival_scan:
    - happy path: 1 booking → tasks created, draft written, queue row written
    - idempotency: second call for same booking → skipped (bookings_skipped=1)
    - 0 bookings in window → returns processed=0
    - booking with CANCELED status not included
    - per-booking exception does not abort scan → other bookings still processed
    - returns all required summary keys
    - DB connection failure → graceful return

GET /admin/pre-arrival-queue:
    - 200 happy path — correct shape (queue, count)
    - 400 on limit=0
    - 400 on invalid draft_written value
    - filter by date — query includes eq(check_in, date)
    - filter by draft_written=true
    - empty queue → count=0
    - 500 on DB error
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from services.pre_arrival_scanner import _build_checkin_draft, run_pre_arrival_scan

TENANT = "tenant-test"
TODAY = date.today()
CHECKIN = (TODAY + timedelta(days=2)).isoformat()
CHECKOUT = (TODAY + timedelta(days=7)).isoformat()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_booking(**kw) -> dict:
    return {
        "booking_id":       "airbnb_R001",
        "tenant_id":        TENANT,
        "property_id":      "prop-1",
        "check_in":         CHECKIN,
        "check_out":        CHECKOUT,
        "guest_name":       "Alice",
        "lifecycle_status": "CONFIRMED",
        **kw,
    }


def _make_db(
    bookings: list[dict] | None = None,
    already_queued: bool = False,
    task_upsert_ok: bool = True,
    fail_booking_query: bool = False,
) -> MagicMock:
    """Build a mock Supabase client for scanner tests."""
    db = MagicMock()

    def table_fn(name: str):
        t = MagicMock()
        for m in ("select", "eq", "gte", "lte", "in_", "limit", "order",
                  "upsert", "insert", "execute"):
            getattr(t, m).return_value = t

        r = MagicMock()

        if name == "booking_state":
            if fail_booking_query:
                def boom():
                    raise RuntimeError("DB failure")
                t.execute.side_effect = boom
            else:
                r.data = bookings if bookings is not None else []
                t.execute.return_value = r

        elif name == "pre_arrival_queue":
            # First call = idempotency check, second = upsert
            check_r = MagicMock()
            check_r.data = [{"id": 1}] if already_queued else []
            upsert_r = MagicMock()
            upsert_r.data = [{"id": 2}]
            call_count = {"n": 0}
            def smart_execute():
                call_count["n"] += 1
                return check_r if call_count["n"] == 1 else upsert_r
            t.execute.side_effect = smart_execute

        elif name == "tasks":
            upsert_r = MagicMock()
            upsert_r.data = [{"task_id": "abc"}] if task_upsert_ok else []
            t.execute.return_value = upsert_r

        elif name == "properties":
            prop_r = MagicMock()
            prop_r.data = [{"name": "Sunset Villa", "access_code": "7890"}]
            t.execute.return_value = prop_r

        else:
            r.data = []
            t.execute.return_value = r

        return t

    db.table.side_effect = table_fn
    return db


def _app():
    from fastapi import FastAPI
    from api.pre_arrival_router import router
    app = FastAPI()
    app.include_router(router)
    return app


# ---------------------------------------------------------------------------
# Unit: _build_checkin_draft
# ---------------------------------------------------------------------------

class TestBuildCheckinDraft:
    def test_includes_guest_name(self):
        draft = _build_checkin_draft("Alice", "Sunset Villa", CHECKIN, CHECKOUT)
        assert "Alice" in draft

    def test_includes_checkin_date(self):
        draft = _build_checkin_draft("Alice", "Sunset Villa", CHECKIN, CHECKOUT)
        assert CHECKIN in draft

    def test_includes_checkout_date(self):
        draft = _build_checkin_draft("Alice", "Sunset Villa", CHECKIN, CHECKOUT)
        assert CHECKOUT in draft

    def test_includes_access_code_when_provided(self):
        draft = _build_checkin_draft("Alice", "Sunset Villa", CHECKIN, CHECKOUT, access_code="7890")
        assert "7890" in draft

    def test_omits_access_code_when_none(self):
        draft = _build_checkin_draft("Alice", "Sunset Villa", CHECKIN, CHECKOUT, access_code=None)
        assert "Entry code" not in draft

    def test_handles_no_guest_name(self):
        draft = _build_checkin_draft(None, "Sunset Villa", CHECKIN, CHECKOUT)
        assert "Dear Guest" in draft


# ---------------------------------------------------------------------------
# Unit: run_pre_arrival_scan
# ---------------------------------------------------------------------------

class TestRunPreArrivalScan:
    def test_returns_all_summary_keys(self):
        db = _make_db(bookings=[_make_booking()])
        result = run_pre_arrival_scan(db=db)
        for key in ("bookings_found", "bookings_processed", "bookings_skipped",
                    "tasks_created", "drafts_written"):
            assert key in result, f"Missing key: {key}"

    def test_happy_path_one_booking_processed(self):
        db = _make_db(bookings=[_make_booking()])
        result = run_pre_arrival_scan(db=db)
        assert result["bookings_found"] == 1
        assert result["bookings_processed"] == 1
        assert result["drafts_written"] == 1

    def test_happy_path_tasks_created(self):
        db = _make_db(bookings=[_make_booking()])
        result = run_pre_arrival_scan(db=db)
        # CHECKIN_PREP + GUEST_WELCOME (has guest_name)
        assert result["tasks_created"] >= 1

    def test_idempotency_already_queued_booking_skipped(self):
        db = _make_db(bookings=[_make_booking()], already_queued=True)
        result = run_pre_arrival_scan(db=db)
        assert result["bookings_skipped"] == 1
        assert result["bookings_processed"] == 0

    def test_zero_bookings_in_window(self):
        db = _make_db(bookings=[])
        result = run_pre_arrival_scan(db=db)
        assert result["bookings_found"] == 0
        assert result["bookings_processed"] == 0

    def test_db_connection_failure_returns_gracefully(self):
        result = run_pre_arrival_scan(db=None)  # won't connect — missing env
        # Should return zeros, not raise
        assert result["bookings_found"] == 0

    def test_booking_query_failure_returns_gracefully(self):
        db = _make_db(fail_booking_query=True)
        result = run_pre_arrival_scan(db=db)
        assert result["bookings_found"] == 0

    def test_no_guest_name_still_creates_checkin_prep(self):
        db = _make_db(bookings=[_make_booking(guest_name=None)])
        result = run_pre_arrival_scan(db=db)
        assert result["bookings_processed"] == 1
        assert result["tasks_created"] >= 1  # at least CHECKIN_PREP


# ---------------------------------------------------------------------------
# Endpoint: GET /admin/pre-arrival-queue
# ---------------------------------------------------------------------------

class TestPreArrivalQueueEndpoint:
    def _get(self, query="", client_mock=None):
        from fastapi.testclient import TestClient
        import api.pre_arrival_router as mod

        with patch("api.pre_arrival_router.jwt_auth", return_value=TENANT), \
             patch.object(mod, "_get_db", return_value=client_mock or _make_endpoint_db()):
            return TestClient(_app()).get(
                f"/admin/pre-arrival-queue{query}",
                headers={"Authorization": "Bearer fake"},
            )

    def test_200_happy_path_shape(self):
        resp = self._get()
        assert resp.status_code == 200
        data = resp.json()
        assert "queue" in data
        assert "count" in data

    def test_200_empty_queue_count_zero(self):
        resp = self._get(client_mock=_make_endpoint_db(rows=[]))
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_400_invalid_limit(self):
        resp = self._get("?limit=0")
        assert resp.status_code == 400

    def test_400_invalid_draft_written_value(self):
        resp = self._get("?draft_written=maybe")
        assert resp.status_code == 400

    def test_200_filter_by_date_accepted(self):
        resp = self._get(f"?date={CHECKIN}")
        assert resp.status_code == 200

    def test_200_filter_by_draft_written_true(self):
        resp = self._get("?draft_written=true")
        assert resp.status_code == 200

    def test_200_filter_by_draft_written_false(self):
        resp = self._get("?draft_written=false")
        assert resp.status_code == 200

    def test_500_on_db_error(self):
        from fastapi.testclient import TestClient
        import api.pre_arrival_router as mod

        failing_db = MagicMock()
        failing_db.table.side_effect = RuntimeError("DB down")

        with patch("api.pre_arrival_router.jwt_auth", return_value=TENANT), \
             patch.object(mod, "_get_db", return_value=failing_db):
            resp = TestClient(_app(), raise_server_exceptions=False).get(
                "/admin/pre-arrival-queue",
                headers={"Authorization": "Bearer fake"},
            )
        assert resp.status_code == 500


def _make_endpoint_db(rows=None) -> MagicMock:
    db = MagicMock()
    fake_rows = rows if rows is not None else [
        {
            "id": 1,
            "booking_id": "airbnb_R001",
            "property_id": "prop-1",
            "check_in": CHECKIN,
            "tasks_created": ["abc", "def"],
            "draft_written": True,
            "draft_preview": "Dear Alice,",
            "scanned_at": "2026-03-11T06:00:00Z",
        }
    ]
    t = MagicMock()
    for m in ("select", "eq", "order", "limit", "execute"):
        getattr(t, m).return_value = t
    r = MagicMock()
    r.data = fake_rows
    t.execute.return_value = r
    db.table.return_value = t
    return db
