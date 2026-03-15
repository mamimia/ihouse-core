"""
Contract tests for src/main.py — the assembled FastAPI application.

Uses FastAPI TestClient (no live server, CI-safe).
ingest_provider_event is mocked — no Supabase required.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# Import the assembled app
from main import app

_MOCK_TARGET = "api.webhooks.ingest_provider_event_with_dlq"
_MOCK_APPLY_FN = "api.webhooks._build_apply_fn"
_MOCK_SKILL_ROUTER = "api.webhooks._build_skill_router"

_VALID_PAYLOAD = {
    "reservation_id": "RES-100",
    "tenant_id": "tenant-xyz",
    "occurred_at": "2024-06-01T12:00:00Z",
    "event_type": "reservation_create",
    "property_id": "PROP-1",
}


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Test 1: GET /health → 200 with expected body
# ---------------------------------------------------------------------------

def test_health_returns_200(client):
    resp = client.get("/health")
    # 200 when Supabase reachable or URL not set (skipped),
    # 503 when Supabase URL set but unreachable.
    assert resp.status_code in (200, 503)
    body = resp.json()
    assert body["status"] in ("ok", "degraded", "unhealthy")
    assert "version" in body
    assert "env" in body


# ---------------------------------------------------------------------------
# Test 2: POST /webhooks/bookingcom → routed correctly (dev mode)
# ---------------------------------------------------------------------------

def test_webhook_route_routed_through_app(client, monkeypatch):
    """Webhook endpoint is accessible from the assembled app."""
    monkeypatch.delenv("IHOUSE_WEBHOOK_SECRET_BOOKINGCOM", raising=False)

    with patch(_MOCK_TARGET, return_value={"status": "APPLIED", "idempotency_key": "bookingcom:reservation_create:RES-100"}), \
         patch(_MOCK_APPLY_FN, return_value=lambda e, em: {"status": "APPLIED"}), \
         patch(_MOCK_SKILL_ROUTER, return_value=lambda et, p: []):
        resp = client.post(
            "/webhooks/bookingcom",
            content=json.dumps(_VALID_PAYLOAD).encode(),
            headers={"Content-Type": "application/json"},
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ACCEPTED"


# ---------------------------------------------------------------------------
# Test 3: GET /nonexistent → 404 (not 500)
# ---------------------------------------------------------------------------

def test_unknown_route_returns_404_not_500(client):
    resp = client.get("/this-route-does-not-exist")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test 4: /health requires no auth
# ---------------------------------------------------------------------------

def test_health_requires_no_auth(client):
    """Health check is always accessible — no API key or JWT needed."""
    resp = client.get("/health")
    assert resp.status_code in (200, 503)  # must not be 401 / 403


# ---------------------------------------------------------------------------
# Test 5: App metadata
# ---------------------------------------------------------------------------

def test_app_title():
    assert app.title == "iHouse Core"


def test_app_version():
    assert app.version == "0.1.0"
