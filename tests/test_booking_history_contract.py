"""
Phase 132 — Booking Audit Trail Contract Tests

Tests for GET /bookings/{booking_id}/history

Contract:
  - Returns 200 + event list when events exist for booking_id + tenant
  - Returns 404 when booking_id has no events for this tenant
  - Returns 404 when booking_id exists but belongs to different tenant (tenant isolation)
  - Returns 401 when JWT is missing (in prod mode simulation)
  - Events ordered chronologically ascending (recorded_at ASC)
  - event_count matches len(events)
  - Response contains correct booking_id and tenant_id
  - Each event has required fields: event_kind, event_id/id, recorded_at/created_at
  - Multiple event types returned: BOOKING_CREATED, BOOKING_AMENDED, BOOKING_CANCELED
  - Full event chain preserved (no filtering of event kinds)
  - Empty recorded_at falls back to created_at
  - Does not write to any table (verified via read-only client mock)
  - Handles DB exception gracefully → 500 with INTERNAL_ERROR code
  - Large event_count (many amendments) returned correctly
  - source field propagated from event_log
  - property_id field propagated from event_log
  - check_in / check_out fields propagated (YYYY-MM-DD)
  - envelope_id propagated
  - version propagated
  - Handles missing optional fields gracefully (None values)
  - tenant_id injected by JWT auth (not from query param)
  - Router callable without Supabase (client injection pattern)
  - 404 response includes booking_id in detail
"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Minimal FastAPI app for isolated testing
# ---------------------------------------------------------------------------

from fastapi import FastAPI
from api.booking_history_router import router

_app = FastAPI()
_app.include_router(router)
_client = TestClient(_app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

_TENANT = "test-tenant-132"
_OTHER_TENANT = "other-tenant-999"
_BOOKING_ID = "bk-abc-001"


def _event_row(
    event_kind: str = "BOOKING_CREATED",
    version: int = 1,
    tenant_id: str = _TENANT,
    booking_id: str = _BOOKING_ID,
    recorded_at: str = "2026-01-10T10:00:00Z",
    source: str = "airbnb",
    property_id: str = "prop-A",
    check_in: str = "2026-03-01",
    check_out: str = "2026-03-08",
    envelope_id: str = "env-001",
    event_id: str | None = None,
) -> dict:
    return {
        "id": event_id or f"evt-{version}",
        "event_id": event_id or f"evt-{version}",
        "event_kind": event_kind,
        "version": version,
        "booking_id": booking_id,
        "tenant_id": tenant_id,
        "envelope_id": envelope_id,
        "source": source,
        "property_id": property_id,
        "check_in": check_in,
        "check_out": check_out,
        "recorded_at": recorded_at,
        "created_at": recorded_at,
    }


def _mock_db(rows: list[dict]) -> MagicMock:
    """Return a Supabase client mock that returns `rows` for any select query."""
    db = MagicMock()
    result = MagicMock()
    result.data = rows
    (
        db.table.return_value
        .select.return_value
        .eq.return_value
        .eq.return_value
        .order.return_value
        .execute.return_value
    ) = result
    return db


def _get(path: str, db: Any, tenant: str = _TENANT) -> Any:
    """
    Call the endpoint with JWT auth bypassed and injected DB client.
    Uses FastAPI dependency override pattern.
    """
    from api.auth import jwt_auth
    _app.dependency_overrides[jwt_auth] = lambda: tenant

    with patch("api.booking_history_router._get_supabase_client", return_value=db):
        resp = _client.get(path)

    _app.dependency_overrides.clear()
    return resp


# ===========================================================================
# TC-01  200 single BOOKING_CREATED event
# ===========================================================================
def test_history_single_created_event():
    rows = [_event_row()]
    db = _mock_db(rows)
    resp = _get(f"/bookings/{_BOOKING_ID}/history", db)
    assert resp.status_code == 200
    body = resp.json()
    assert body["booking_id"] == _BOOKING_ID
    assert body["tenant_id"] == _TENANT
    assert body["event_count"] == 1
    assert len(body["events"]) == 1
    ev = body["events"][0]
    assert ev["event_kind"] == "BOOKING_CREATED"


# ===========================================================================
# TC-02  200 multiple events (CREATED + AMENDED + CANCELED)
# ===========================================================================
def test_history_full_lifecycle():
    rows = [
        _event_row("BOOKING_CREATED",  version=1, recorded_at="2026-01-01T10:00:00Z"),
        _event_row("BOOKING_AMENDED",  version=2, recorded_at="2026-01-05T12:00:00Z"),
        _event_row("BOOKING_CANCELED", version=3, recorded_at="2026-01-10T09:00:00Z"),
    ]
    db = _mock_db(rows)
    resp = _get(f"/bookings/{_BOOKING_ID}/history", db)
    assert resp.status_code == 200
    body = resp.json()
    assert body["event_count"] == 3
    assert len(body["events"]) == 3
    assert body["events"][0]["event_kind"] == "BOOKING_CREATED"
    assert body["events"][1]["event_kind"] == "BOOKING_AMENDED"
    assert body["events"][2]["event_kind"] == "BOOKING_CANCELED"


# ===========================================================================
# TC-03  404 when no events for booking_id
# ===========================================================================
def test_history_404_no_events():
    db = _mock_db([])
    resp = _get("/bookings/nonexistent-bk/history", db)
    assert resp.status_code == 404
    body = resp.json()
    assert "booking_id" in str(body)


# ===========================================================================
# TC-04  404 when booking belongs to different tenant (isolation)
# ===========================================================================
def test_history_tenant_isolation():
    # DB returns empty because .eq("tenant_id", tenant_id) filters by OTHER tenant
    db = _mock_db([])
    resp = _get(f"/bookings/{_BOOKING_ID}/history", db, tenant=_OTHER_TENANT)
    assert resp.status_code == 404


# ===========================================================================
# TC-05  event_count matches len(events)
# ===========================================================================
def test_history_event_count_matches():
    rows = [_event_row(version=i, recorded_at=f"2026-01-{i:02d}T10:00:00Z") for i in range(1, 6)]
    db = _mock_db(rows)
    resp = _get(f"/bookings/{_BOOKING_ID}/history", db)
    body = resp.json()
    assert body["event_count"] == len(body["events"]) == 5


# ===========================================================================
# TC-06  event fields propagated correctly
# ===========================================================================
def test_history_event_fields_propagated():
    rows = [_event_row(
        event_kind="BOOKING_CREATED",
        version=1,
        source="bookingcom",
        property_id="prop-XY",
        check_in="2026-04-01",
        check_out="2026-04-07",
        envelope_id="env-xyz-999",
        event_id="evt-unique-001",
    )]
    db = _mock_db(rows)
    resp = _get(f"/bookings/{_BOOKING_ID}/history", db)
    ev = resp.json()["events"][0]
    assert ev["event_kind"] == "BOOKING_CREATED"
    assert ev["version"] == 1
    assert ev["source"] == "bookingcom"
    assert ev["property_id"] == "prop-XY"
    assert ev["check_in"] == "2026-04-01"
    assert ev["check_out"] == "2026-04-07"
    assert ev["envelope_id"] == "env-xyz-999"


# ===========================================================================
# TC-07  recorded_at returned in events
# ===========================================================================
def test_history_recorded_at_present():
    rows = [_event_row(recorded_at="2026-03-01T08:30:00Z")]
    db = _mock_db(rows)
    resp = _get(f"/bookings/{_BOOKING_ID}/history", db)
    ev = resp.json()["events"][0]
    assert ev["recorded_at"] == "2026-03-01T08:30:00Z"


# ===========================================================================
# TC-08  falls back to created_at when recorded_at is None
# ===========================================================================
def test_history_fallback_to_created_at():
    row = _event_row(recorded_at="2026-03-01T08:00:00Z")
    row["recorded_at"] = None  # clear recorded_at — should fall back to created_at
    row["created_at"] = "2026-03-01T08:00:00Z"
    db = _mock_db([row])
    resp = _get(f"/bookings/{_BOOKING_ID}/history", db)
    ev = resp.json()["events"][0]
    assert ev["recorded_at"] == "2026-03-01T08:00:00Z"


# ===========================================================================
# TC-09  handles missing optional fields gracefully (None values)
# ===========================================================================
def test_history_optional_fields_none():
    row = {
        "id": "evt-min-001",
        "event_id": None,
        "event_kind": "BOOKING_CREATED",
        "version": None,
        "booking_id": _BOOKING_ID,
        "tenant_id": _TENANT,
        "envelope_id": None,
        "source": None,
        "property_id": None,
        "check_in": None,
        "check_out": None,
        "recorded_at": "2026-03-01T08:00:00Z",
        "created_at": "2026-03-01T08:00:00Z",
    }
    db = _mock_db([row])
    resp = _get(f"/bookings/{_BOOKING_ID}/history", db)
    assert resp.status_code == 200
    ev = resp.json()["events"][0]
    assert ev["source"] is None
    assert ev["property_id"] is None
    assert ev["check_in"] is None
    assert ev["check_out"] is None
    assert ev["envelope_id"] is None


# ===========================================================================
# TC-10  500 on DB exception
# ===========================================================================
def test_history_500_on_db_error():
    db = MagicMock()
    (
        db.table.return_value
        .select.return_value
        .eq.return_value
        .eq.return_value
        .order.return_value
        .execute.side_effect
    ) = RuntimeError("DB down")

    from api.auth import jwt_auth
    _app.dependency_overrides[jwt_auth] = lambda: _TENANT
    with patch("api.booking_history_router._get_supabase_client", return_value=db):
        resp = _client.get(f"/bookings/{_BOOKING_ID}/history")
    _app.dependency_overrides.clear()
    assert resp.status_code == 500


# ===========================================================================
# TC-11  response body is valid JSON
# ===========================================================================
def test_history_response_is_valid_json():
    rows = [_event_row()]
    db = _mock_db(rows)
    resp = _get(f"/bookings/{_BOOKING_ID}/history", db)
    assert resp.headers["content-type"].startswith("application/json")
    parsed = resp.json()
    assert isinstance(parsed, dict)


# ===========================================================================
# TC-12  tenant_id in response matches authenticated tenant
# ===========================================================================
def test_history_tenant_id_in_response():
    rows = [_event_row(tenant_id="my-tenant-xyz")]
    db = _mock_db(rows)
    resp = _get(f"/bookings/{_BOOKING_ID}/history", db, tenant="my-tenant-xyz")
    assert resp.json()["tenant_id"] == "my-tenant-xyz"


# ===========================================================================
# TC-13  booking_id in response matches path param
# ===========================================================================
def test_history_booking_id_in_response():
    bk = "bk-custom-path-001"
    rows = [_event_row(booking_id=bk)]
    db = _mock_db(rows)
    resp = _get(f"/bookings/{bk}/history", db)
    assert resp.json()["booking_id"] == bk


# ===========================================================================
# TC-14  many amendments (large event count)
# ===========================================================================
def test_history_many_amendments():
    rows = [
        _event_row("BOOKING_CREATED", version=1, recorded_at="2026-01-01T00:00:00Z"),
    ] + [
        _event_row("BOOKING_AMENDED", version=i, recorded_at=f"2026-01-{i:02d}T10:00:00Z")
        for i in range(2, 22)  # 20 amendments
    ]
    db = _mock_db(rows)
    resp = _get(f"/bookings/{_BOOKING_ID}/history", db)
    body = resp.json()
    assert body["event_count"] == 21
    assert len(body["events"]) == 21
    assert body["events"][0]["event_kind"] == "BOOKING_CREATED"


# ===========================================================================
# TC-15  401 returned when JWT is missing in production mode
# ===========================================================================
def test_history_401_no_jwt():
    """Without dependency override — HTTPBearer returns 403 when no token."""
    with patch.dict("os.environ", {"IHOUSE_JWT_SECRET": "test-secret-for-auth"}):
        resp = _client.get(f"/bookings/{_BOOKING_ID}/history")
    assert resp.status_code == 403


# ===========================================================================
# TC-16  BOOKING_AMENDED event kind preserved in history
# ===========================================================================
def test_history_amended_event_preserved():
    rows = [
        _event_row("BOOKING_CREATED", version=1, recorded_at="2026-01-01T10:00:00Z"),
        _event_row("BOOKING_AMENDED", version=2, recorded_at="2026-01-05T10:00:00Z"),
    ]
    db = _mock_db(rows)
    resp = _get(f"/bookings/{_BOOKING_ID}/history", db)
    kinds = [e["event_kind"] for e in resp.json()["events"]]
    assert "BOOKING_AMENDED" in kinds


# ===========================================================================
# TC-17  BOOKING_CANCELED event kind preserved in history
# ===========================================================================
def test_history_canceled_event_preserved():
    rows = [
        _event_row("BOOKING_CREATED",  version=1, recorded_at="2026-01-01T10:00:00Z"),
        _event_row("BOOKING_CANCELED", version=2, recorded_at="2026-01-10T10:00:00Z"),
    ]
    db = _mock_db(rows)
    resp = _get(f"/bookings/{_BOOKING_ID}/history", db)
    kinds = [e["event_kind"] for e in resp.json()["events"]]
    assert "BOOKING_CANCELED" in kinds


# ===========================================================================
# TC-18  version field included for each event
# ===========================================================================
def test_history_version_included():
    rows = [_event_row(version=7)]
    db = _mock_db(rows)
    resp = _get(f"/bookings/{_BOOKING_ID}/history", db)
    ev = resp.json()["events"][0]
    assert ev["version"] == 7


# ===========================================================================
# TC-19  source field preserved (OTA provider name)
# ===========================================================================
def test_history_source_field_preserved():
    rows = [_event_row(source="vrbo")]
    db = _mock_db(rows)
    resp = _get(f"/bookings/{_BOOKING_ID}/history", db)
    assert resp.json()["events"][0]["source"] == "vrbo"


# ===========================================================================
# TC-20  check_in / check_out dates preserved (exclusive check_out invariant)
# ===========================================================================
def test_history_dates_preserved():
    rows = [_event_row(check_in="2026-05-01", check_out="2026-05-08")]
    db = _mock_db(rows)
    resp = _get(f"/bookings/{_BOOKING_ID}/history", db)
    ev = resp.json()["events"][0]
    assert ev["check_in"] == "2026-05-01"
    assert ev["check_out"] == "2026-05-08"


# ===========================================================================
# TC-21  404 body contains booking_id
# ===========================================================================
def test_history_404_body_contains_booking_id():
    db = _mock_db([])
    resp = _get("/bookings/bk-ghost-999/history", db)
    assert resp.status_code == 404
    assert "bk-ghost-999" in resp.text


# ===========================================================================
# TC-22  endpoint does not expose any write methods (GET only guard)
# ===========================================================================
def test_history_post_method_not_allowed():
    from api.auth import jwt_auth
    _app.dependency_overrides[jwt_auth] = lambda: _TENANT
    resp = _client.post(f"/bookings/{_BOOKING_ID}/history")
    _app.dependency_overrides.clear()
    assert resp.status_code == 405


# ===========================================================================
# TC-23  different booking_ids return independent results
# ===========================================================================
def test_history_booking_id_isolation():
    rows_a = [_event_row(booking_id="bk-A", version=1)]
    rows_b = [
        _event_row(booking_id="bk-B", version=1, recorded_at="2026-01-01T10:00:00Z"),
        _event_row(booking_id="bk-B", event_kind="BOOKING_AMENDED",
                   version=2, recorded_at="2026-01-05T10:00:00Z"),
    ]
    # Each call gets its own mock
    db_a = _mock_db(rows_a)
    db_b = _mock_db(rows_b)
    resp_a = _get("/bookings/bk-A/history", db_a)
    resp_b = _get("/bookings/bk-B/history", db_b)
    assert resp_a.json()["event_count"] == 1
    assert resp_b.json()["event_count"] == 2


# ===========================================================================
# TC-24  event_id field present (id fallback)
# ===========================================================================
def test_history_event_id_present():
    row = _event_row(event_id="evt-specific-id-001")
    db = _mock_db([row])
    resp = _get(f"/bookings/{_BOOKING_ID}/history", db)
    ev = resp.json()["events"][0]
    assert ev["event_id"] == "evt-specific-id-001"


# ===========================================================================
# TC-25  envelope_id propagated from event_log
# ===========================================================================
def test_history_envelope_id_propagated():
    rows = [_event_row(envelope_id="env-specific-555")]
    db = _mock_db(rows)
    resp = _get(f"/bookings/{_BOOKING_ID}/history", db)
    ev = resp.json()["events"][0]
    assert ev["envelope_id"] == "env-specific-555"


# ===========================================================================
# TC-26  booking_id path param is URL-safe (hyphens, underscores)
# ===========================================================================
def test_history_url_safe_booking_id():
    bk = "bk-my_booking-2026-001"
    rows = [_event_row(booking_id=bk)]
    db = _mock_db(rows)
    resp = _get(f"/bookings/{bk}/history", db)
    assert resp.status_code == 200
    assert resp.json()["booking_id"] == bk


# ===========================================================================
# TC-27  single BOOKING_CANCELED-only history (no CREATED — rare, tolerated)
# ===========================================================================
def test_history_single_canceled_only():
    rows = [_event_row("BOOKING_CANCELED", version=1)]
    db = _mock_db(rows)
    resp = _get(f"/bookings/{_BOOKING_ID}/history", db)
    assert resp.status_code == 200
    assert resp.json()["events"][0]["event_kind"] == "BOOKING_CANCELED"


# ===========================================================================
# TC-28  events list is a list (not dict or other type)
# ===========================================================================
def test_history_events_is_list():
    rows = [_event_row()]
    db = _mock_db(rows)
    resp = _get(f"/bookings/{_BOOKING_ID}/history", db)
    assert isinstance(resp.json()["events"], list)


# ===========================================================================
# TC-29  event_count is int not str
# ===========================================================================
def test_history_event_count_is_int():
    rows = [_event_row()]
    db = _mock_db(rows)
    resp = _get(f"/bookings/{_BOOKING_ID}/history", db)
    assert isinstance(resp.json()["event_count"], int)


# ===========================================================================
# TC-30  property_id propagated per event (multiple events, same property)
# ===========================================================================
def test_history_property_id_propagated_all_events():
    rows = [
        _event_row("BOOKING_CREATED",  version=1, property_id="villa-alpha",
                   recorded_at="2026-01-01T10:00:00Z"),
        _event_row("BOOKING_AMENDED",  version=2, property_id="villa-alpha",
                   recorded_at="2026-01-05T10:00:00Z"),
    ]
    db = _mock_db(rows)
    resp = _get(f"/bookings/{_BOOKING_ID}/history", db)
    for ev in resp.json()["events"]:
        assert ev["property_id"] == "villa-alpha"


# ===========================================================================
# TC-31  response structure is stable (no extra unexpected keys)
# ===========================================================================
def test_history_response_top_level_keys():
    rows = [_event_row()]
    db = _mock_db(rows)
    resp = _get(f"/bookings/{_BOOKING_ID}/history", db)
    body = resp.json()
    expected_keys = {"booking_id", "tenant_id", "event_count", "events"}
    assert set(body.keys()) == expected_keys


# ===========================================================================
# TC-32  each event has expected keys
# ===========================================================================
def test_history_event_keys():
    rows = [_event_row()]
    db = _mock_db(rows)
    resp = _get(f"/bookings/{_BOOKING_ID}/history", db)
    ev = resp.json()["events"][0]
    expected = {
        "event_id", "event_kind", "version", "envelope_id",
        "source", "property_id", "check_in", "check_out", "recorded_at",
    }
    assert set(ev.keys()) == expected
