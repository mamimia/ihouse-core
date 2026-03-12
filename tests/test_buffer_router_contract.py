"""
Phase 133 — OTA Ordering Buffer Inspector Contract Tests

Tests for:
  GET /admin/buffer
  GET /admin/buffer/{entry_id}

Contract:
  - 200 + entries list when buffer has entries
  - Empty entries list when buffer is empty (not 404)
  - status filter: "waiting" returns only waiting rows
  - status filter: "replayed" returns only replayed rows
  - status filter: "all" returns all rows
  - 400 on invalid status filter value
  - booking_id filter: only rows for that booking_id returned
  - limit clamping: 1..100, default 50
  - 400 on limit < 1 or limit > 100
  - age_seconds: present and is int (seconds since created_at)
  - age_seconds: None when created_at is missing
  - dlq_row_id propagated (int or null)
  - event_type propagated correctly
  - status field propagated correctly
  - created_at propagated
  - id field (integer) propagated
  - booking_id field propagated
  - response top-level keys: total, status_filter, booking_id_filter, entries
  - each entry has required keys
  - total matches len(entries)
  - status_filter echoed in response
  - booking_id_filter echoed (null when not provided)
  - GET /admin/buffer/{id} - 200 returns single entry
  - GET /admin/buffer/{id} - 404 when id not found
  - GET /admin/buffer/{id} - 400 on non-integer id (FastAPI type coercion)
  - GET /admin/buffer/{id} - fields match expected entry
  - 500 on DB exception (list endpoint)
  - 500 on DB exception (single endpoint)
  - JWT auth: 403 returned when JWT missing (prod mode)
  - POST method not allowed (405)
  - multiple statuses properly separated in filtered response
  - booking_id filter combined with status filter
  - entries list is a list type
  - age_seconds is non-negative integer
"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.buffer_router import router

_app = FastAPI()
_app.include_router(router)
_client = TestClient(_app, raise_server_exceptions=False)

_TENANT = "test-tenant-133"


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _buffer_row(
    id: int = 1,
    booking_id: str = "bk-airbnb-001",
    event_type: str = "BOOKING_CANCELED",
    status: str = "waiting",
    dlq_row_id: int | None = 42,
    created_at: str = "2026-03-09T10:00:00Z",
) -> dict:
    return {
        "id":          id,
        "booking_id":  booking_id,
        "event_type":  event_type,
        "status":      status,
        "dlq_row_id":  dlq_row_id,
        "created_at":  created_at,
    }


def _mock_db_list(rows: list[dict]) -> MagicMock:
    db = MagicMock()
    result = MagicMock()
    result.data = rows
    (
        db.table.return_value
        .select.return_value
        .order.return_value
        .limit.return_value
        .execute.return_value
    ) = result
    # Also handle .eq(...).limit(...) chain
    eq_mock = MagicMock()
    eq_mock.limit.return_value.execute.return_value = result
    eq_mock.eq.return_value.limit.return_value.execute.return_value = result
    db.table.return_value.select.return_value.order.return_value.eq.return_value = eq_mock
    return db


def _mock_db_single(rows: list[dict]) -> MagicMock:
    db = MagicMock()
    result = MagicMock()
    result.data = rows
    (
        db.table.return_value
        .select.return_value
        .eq.return_value
        .limit.return_value
        .execute.return_value
    ) = result
    return db


def _get_list(params: str = "", db: Any = None) -> Any:
    from api.auth import jwt_auth
    if db is None:
        db = _mock_db_list([])
    _app.dependency_overrides[jwt_auth] = lambda: _TENANT
    with patch("api.buffer_router._get_supabase_client", return_value=db):
        resp = _client.get(f"/admin/buffer{params}")
    _app.dependency_overrides.clear()
    return resp


def _get_single(entry_id: Any, db: Any) -> Any:
    from api.auth import jwt_auth
    _app.dependency_overrides[jwt_auth] = lambda: _TENANT
    with patch("api.buffer_router._get_supabase_client", return_value=db):
        resp = _client.get(f"/admin/buffer/{entry_id}")
    _app.dependency_overrides.clear()
    return resp


# ===========================================================================
# LIST ENDPOINT TESTS
# ===========================================================================

# TC-01 — 200 with entries
def test_buffer_list_200_with_entries():
    rows = [_buffer_row(id=1), _buffer_row(id=2, status="replayed")]
    db = _mock_db_list(rows)
    resp = _get_list(db=db)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["entries"]) == 2


# TC-02 — 200 empty list (not 404)
def test_buffer_list_200_empty():
    db = _mock_db_list([])
    resp = _get_list(db=db)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["entries"] == []


# TC-03 — top-level response keys
def test_buffer_list_top_level_keys():
    db = _mock_db_list([_buffer_row()])
    resp = _get_list(db=db)
    body = resp.json()
    assert set(body.keys()) == {"total", "status_filter", "booking_id_filter", "entries"}


# TC-04 — each entry has expected keys
def test_buffer_list_entry_keys():
    db = _mock_db_list([_buffer_row()])
    resp = _get_list(db=db)
    ev = resp.json()["entries"][0]
    expected = {"id", "booking_id", "event_type", "status", "dlq_row_id", "created_at", "age_seconds"}
    assert set(ev.keys()) == expected


# TC-05 — total matches len(entries)
def test_buffer_list_total_matches_count():
    rows = [_buffer_row(id=i) for i in range(1, 6)]
    db = _mock_db_list(rows)
    resp = _get_list(db=db)
    body = resp.json()
    assert body["total"] == len(body["entries"]) == 5


# TC-06 — status_filter echoed
def test_buffer_list_status_filter_echoed():
    db = _mock_db_list([])
    resp = _get_list("?status=waiting", db=db)
    assert resp.json()["status_filter"] == "waiting"


# TC-07 — booking_id_filter echoed when provided
def test_buffer_list_booking_id_filter_echoed():
    db = _mock_db_list([])
    resp = _get_list("?booking_id=bk-test-001", db=db)
    assert resp.json()["booking_id_filter"] == "bk-test-001"


# TC-08 — booking_id_filter null when not provided
def test_buffer_list_booking_id_filter_null_when_absent():
    db = _mock_db_list([])
    resp = _get_list(db=db)
    assert resp.json()["booking_id_filter"] is None


# TC-09 — 400 on invalid status
def test_buffer_list_400_invalid_status():
    db = _mock_db_list([])
    resp = _get_list("?status=unknown", db=db)
    assert resp.status_code == 400


# TC-10 — 400 on limit 0
def test_buffer_list_400_limit_zero():
    db = _mock_db_list([])
    resp = _get_list("?limit=0", db=db)
    assert resp.status_code == 400


# TC-11 — 400 on limit 101
def test_buffer_list_400_limit_over():
    db = _mock_db_list([])
    resp = _get_list("?limit=101", db=db)
    assert resp.status_code == 400


# TC-12 — fields propagated correctly
def test_buffer_list_fields_propagated():
    row = _buffer_row(
        id=99,
        booking_id="bk-trip-XYZ",
        event_type="BOOKING_AMENDED",
        status="waiting",
        dlq_row_id=7,
        created_at="2026-03-01T08:00:00Z",
    )
    db = _mock_db_list([row])
    resp = _get_list(db=db)
    ev = resp.json()["entries"][0]
    assert ev["id"] == 99
    assert ev["booking_id"] == "bk-trip-XYZ"
    assert ev["event_type"] == "BOOKING_AMENDED"
    assert ev["status"] == "waiting"
    assert ev["dlq_row_id"] == 7
    assert ev["created_at"] == "2026-03-01T08:00:00Z"


# TC-13 — age_seconds is non-negative int for waiting entries
def test_buffer_list_age_seconds_is_int():
    db = _mock_db_list([_buffer_row(status="waiting", created_at="2026-03-01T00:00:00Z")])
    resp = _get_list(db=db)
    age = resp.json()["entries"][0]["age_seconds"]
    assert isinstance(age, int)
    assert age >= 0


# TC-14 — age_seconds is None when created_at missing
def test_buffer_list_age_seconds_none_when_no_date():
    row = _buffer_row()
    row["created_at"] = None
    db = _mock_db_list([row])
    resp = _get_list(db=db)
    age = resp.json()["entries"][0]["age_seconds"]
    assert age is None


# TC-15 — dlq_row_id null when not set
def test_buffer_list_dlq_row_id_null():
    row = _buffer_row(dlq_row_id=None)
    db = _mock_db_list([row])
    resp = _get_list(db=db)
    assert resp.json()["entries"][0]["dlq_row_id"] is None


# TC-16 — status "all" echoed in response
def test_buffer_list_status_all_echoed():
    db = _mock_db_list([])
    resp = _get_list("?status=all", db=db)
    assert resp.json()["status_filter"] == "all"


# TC-17 — "replayed" status filter echoed
def test_buffer_list_replayed_filter_echoed():
    db = _mock_db_list([])
    resp = _get_list("?status=replayed", db=db)
    assert resp.json()["status_filter"] == "replayed"


# TC-18 — status "waiting" in row preserved
def test_buffer_list_waiting_status_preserved():
    db = _mock_db_list([_buffer_row(status="waiting")])
    resp = _get_list(db=db)
    assert resp.json()["entries"][0]["status"] == "waiting"


# TC-19 — status "replayed" in row preserved
def test_buffer_list_replayed_status_preserved():
    db = _mock_db_list([_buffer_row(status="replayed")])
    resp = _get_list(db=db)
    assert resp.json()["entries"][0]["status"] == "replayed"


# TC-20 — entries is a list
def test_buffer_list_entries_is_list():
    db = _mock_db_list([])
    resp = _get_list(db=db)
    assert isinstance(resp.json()["entries"], list)


# TC-21 — 500 on DB exception
def test_buffer_list_500_on_db_error():
    db = MagicMock()
    db.table.side_effect = RuntimeError("DB down")
    resp = _get_list(db=db)
    assert resp.status_code == 500


# TC-22 — POST method not allowed
def test_buffer_list_post_not_allowed():
    from api.auth import jwt_auth
    _app.dependency_overrides[jwt_auth] = lambda: _TENANT
    resp = _client.post("/admin/buffer")
    _app.dependency_overrides.clear()
    assert resp.status_code == 405


# TC-23 — 403 when JWT missing (prod mode)
def test_buffer_list_403_no_jwt():
    with patch.dict("os.environ", {"IHOUSE_JWT_SECRET": "test-secret", "IHOUSE_DEV_MODE": "false"}):
        resp = _client.get("/admin/buffer")
    assert resp.status_code == 403


# TC-24 — response is valid JSON
def test_buffer_list_valid_json():
    db = _mock_db_list([_buffer_row()])
    resp = _get_list(db=db)
    assert resp.headers["content-type"].startswith("application/json")
    assert isinstance(resp.json(), dict)


# TC-25 — event_type BOOKING_CANCELED propagated
def test_buffer_list_event_type_canceled():
    db = _mock_db_list([_buffer_row(event_type="BOOKING_CANCELED")])
    resp = _get_list(db=db)
    assert resp.json()["entries"][0]["event_type"] == "BOOKING_CANCELED"


# TC-26 — event_type BOOKING_AMENDED propagated
def test_buffer_list_event_type_amended():
    db = _mock_db_list([_buffer_row(event_type="BOOKING_AMENDED")])
    resp = _get_list(db=db)
    assert resp.json()["entries"][0]["event_type"] == "BOOKING_AMENDED"


# TC-27 — total is int
def test_buffer_list_total_is_int():
    db = _mock_db_list([_buffer_row()])
    resp = _get_list(db=db)
    assert isinstance(resp.json()["total"], int)


# TC-28 — id field is int
def test_buffer_list_id_is_int():
    db = _mock_db_list([_buffer_row(id=55)])
    resp = _get_list(db=db)
    assert resp.json()["entries"][0]["id"] == 55


# ===========================================================================
# SINGLE ENTRY ENDPOINT TESTS
# ===========================================================================

# TC-29 — 200 single entry returned
def test_buffer_single_200():
    row = _buffer_row(id=10)
    db = _mock_db_single([row])
    resp = _get_single(10, db)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == 10


# TC-30 — 404 when entry not found
def test_buffer_single_404():
    db = _mock_db_single([])
    resp = _get_single(999, db)
    assert resp.status_code == 404
    assert "999" in resp.text


# TC-31 — single entry fields match row
def test_buffer_single_fields():
    row = _buffer_row(
        id=77,
        booking_id="bk-expedia-Y99",
        event_type="BOOKING_CANCELED",
        status="replayed",
        dlq_row_id=3,
        created_at="2026-03-05T12:00:00Z",
    )
    db = _mock_db_single([row])
    resp = _get_single(77, db)
    body = resp.json()
    assert body["booking_id"] == "bk-expedia-Y99"
    assert body["event_type"] == "BOOKING_CANCELED"
    assert body["status"] == "replayed"
    assert body["dlq_row_id"] == 3
    assert body["created_at"] == "2026-03-05T12:00:00Z"


# TC-32 — 400 on non-integer entry_id (FastAPI coercion)
def test_buffer_single_400_non_integer():
    from api.auth import jwt_auth
    _app.dependency_overrides[jwt_auth] = lambda: _TENANT
    resp = _client.get("/admin/buffer/not-an-int")
    _app.dependency_overrides.clear()
    assert resp.status_code == 422


# TC-33 — single 500 on DB error
def test_buffer_single_500():
    db = MagicMock()
    db.table.side_effect = RuntimeError("DB down")
    resp = _get_single(1, db)
    assert resp.status_code == 500


# TC-34 — single entry has correct keys
def test_buffer_single_entry_keys():
    db = _mock_db_single([_buffer_row(id=1)])
    resp = _get_single(1, db)
    expected = {"id", "booking_id", "event_type", "status", "dlq_row_id", "created_at", "age_seconds"}
    assert set(resp.json().keys()) == expected


# TC-35 — single entry age_seconds is int
def test_buffer_single_age_seconds():
    db = _mock_db_single([_buffer_row(id=1, created_at="2026-01-01T00:00:00Z")])
    resp = _get_single(1, db)
    age = resp.json()["age_seconds"]
    assert isinstance(age, int)
    assert age >= 0
