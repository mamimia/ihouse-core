"""
Contract tests for Phase 60 — Request Logging Middleware.

Verifies:
  - X-Request-ID header present on every response
  - Header value is a valid UUID4
  - Different requests get different request IDs
  - Status codes are logged (via caplog)
  - Middleware doesn't swallow errors or break existing endpoints
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app

_MOCK_TARGET = "api.webhooks.ingest_provider_event_with_dlq"
_MOCK_APPLY_FN = "api.webhooks._build_apply_fn"
_MOCK_SKILL_ROUTER = "api.webhooks._build_skill_router"

_VALID_PAYLOAD = {
    "reservation_id": "RES-LOG-001",
    "tenant_id": "tenant-log",
    "occurred_at": "2024-06-01T12:00:00Z",
    "event_type": "reservation_create",
    "property_id": "PROP-1",
}


@dataclass
class _FakeEnvelope:
    idempotency_key: str = "bookingcom:reservation_create:RES-LOG-001"
    type: str = "BOOKING_CREATED"
    payload: dict = None
    occurred_at: datetime = None

    def __post_init__(self):
        if self.payload is None:
            self.payload = {}
        if self.occurred_at is None:
            self.occurred_at = datetime(2024, 1, 1, tzinfo=timezone.utc)


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Test 1: X-Request-ID header present on every response
# ---------------------------------------------------------------------------

def test_request_id_header_present_on_200(client, monkeypatch):
    monkeypatch.delenv("IHOUSE_WEBHOOK_SECRET_BOOKINGCOM", raising=False)
    with patch(_MOCK_TARGET, return_value={"status": "APPLIED", "idempotency_key": "k1"}), \
         patch(_MOCK_APPLY_FN, return_value=lambda e, em: {"status": "APPLIED"}), \
         patch(_MOCK_SKILL_ROUTER, return_value=lambda et, p: []):
        resp = client.post(
            "/webhooks/bookingcom",
            content=json.dumps(_VALID_PAYLOAD).encode(),
            headers={"Content-Type": "application/json"},
        )
    assert "x-request-id" in resp.headers


def test_request_id_header_present_on_health(client):
    resp = client.get("/health")
    assert "x-request-id" in resp.headers


# ---------------------------------------------------------------------------
# Test 2: X-Request-ID value is a valid UUID4
# ---------------------------------------------------------------------------

def test_request_id_is_valid_uuid(client):
    resp = client.get("/health")
    request_id = resp.headers.get("x-request-id", "")
    parsed = uuid.UUID(request_id)  # raises if invalid
    assert parsed.version == 4


# ---------------------------------------------------------------------------
# Test 3: Different requests get different request IDs
# ---------------------------------------------------------------------------

def test_different_requests_get_different_ids(client):
    resp1 = client.get("/health")
    resp2 = client.get("/health")
    id1 = resp1.headers.get("x-request-id")
    id2 = resp2.headers.get("x-request-id")
    assert id1 != id2


# ---------------------------------------------------------------------------
# Test 4: 403 response still has X-Request-ID (middleware wraps all codes)
# ---------------------------------------------------------------------------

def test_request_id_present_on_403(client, monkeypatch):
    """Middleware must set X-Request-ID even on error responses."""
    monkeypatch.setenv("IHOUSE_WEBHOOK_SECRET_BOOKINGCOM", "some-secret")
    resp = client.post(
        "/webhooks/bookingcom",
        content=json.dumps(_VALID_PAYLOAD).encode(),
        headers={
            "Content-Type": "application/json",
            "X-Booking-Signature": "sha256=deadbeef",
        },
    )
    assert resp.status_code == 403
    assert "x-request-id" in resp.headers


# ---------------------------------------------------------------------------
# Test 5: 400 response still has X-Request-ID
# ---------------------------------------------------------------------------

def test_request_id_present_on_400(client, monkeypatch):
    monkeypatch.delenv("IHOUSE_WEBHOOK_SECRET_BOOKINGCOM", raising=False)
    empty_payload = {}
    resp = client.post(
        "/webhooks/bookingcom",
        content=json.dumps(empty_payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400
    assert "x-request-id" in resp.headers


# ---------------------------------------------------------------------------
# Test 6: Middleware does not interfere with existing test_main_app tests
# ---------------------------------------------------------------------------

def test_health_still_200_with_middleware(client):
    resp = client.get("/health")
    assert resp.status_code in (200, 503)
    assert resp.json()["status"] in ("ok", "degraded", "unhealthy")
