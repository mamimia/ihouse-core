"""
Contract tests for POST /webhooks/{provider} — FastAPI TestClient (no live server, CI-safe).

Strategy:
- `ingest_provider_event` is monkeypatched to return a fake CanonicalEnvelope.
- Signature secrets are controlled via environment variables.
- No Supabase, no network, no live OTA data.

Coverage:
    1.  Dev mode (no secret set): valid payload → 200 + idempotency_key
    2.  Correct signature set + correct header → 200
    3.  Correct signature secret set + WRONG header → 403
    4.  Secret set, missing header → 403
    5.  Invalid payload (missing required fields) → 400 + codes list
    6.  Non-JSON body → 400
    7.  Unknown provider → 403 (ValueError from signature layer)
    8.  ingest_provider_event raises unexpectedly → 500
    9.  tenant_id from JWT (dev-mode 'dev-tenant') propagated correctly
    10. Response 200 contains correct idempotency_key value
    11. Response 400 body contains "codes" list
    12. All 5 providers accepted in path → 200 (parametrized)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.webhooks import router


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture()
def client():
    return TestClient(_make_app(), raise_server_exceptions=False)


@dataclass
class _FakeEnvelope:
    """Minimal stand-in for CanonicalEnvelope returned by ingest_provider_event."""
    idempotency_key: Optional[str] = "bookingcom:reservation_created:abc123"
    type: str = "BOOKING_CREATED"
    payload: dict = None
    occurred_at: datetime = None

    def __post_init__(self):
        if self.payload is None:
            self.payload = {}
        if self.occurred_at is None:
            self.occurred_at = datetime(2024, 1, 1, tzinfo=timezone.utc)


_VALID_PAYLOAD = {
    "reservation_id": "RES-001",
    "tenant_id": "tenant-abc",
    "occurred_at": "2024-01-15T10:00:00Z",
    "event_type": "reservation_create",
    "property_id": "PROP-1",
}

_MOCK_TARGET = "api.webhooks.ingest_provider_event"


def _compute_sig(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


# ---------------------------------------------------------------------------
# Test 1: Dev mode (no env secret) + valid payload → 200
# ---------------------------------------------------------------------------

def test_valid_payload_dev_mode_no_secret(client, monkeypatch):
    """When no secret is configured, signature check is skipped → 200."""
    monkeypatch.delenv("IHOUSE_WEBHOOK_SECRET_BOOKINGCOM", raising=False)
    with patch(_MOCK_TARGET, return_value=_FakeEnvelope()) as mock_ingest:
        resp = client.post(
            "/webhooks/bookingcom",
            content=json.dumps(_VALID_PAYLOAD).encode(),
            headers={"Content-Type": "application/json"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ACCEPTED"
    mock_ingest.assert_called_once()


# ---------------------------------------------------------------------------
# Test 2: Correct secret + correct signature → 200
# ---------------------------------------------------------------------------

def test_valid_signature_accepted(client, monkeypatch):
    secret = "test-secret-123"
    monkeypatch.setenv("IHOUSE_WEBHOOK_SECRET_BOOKINGCOM", secret)
    raw = json.dumps(_VALID_PAYLOAD).encode()
    sig = _compute_sig(secret, raw)
    with patch(_MOCK_TARGET, return_value=_FakeEnvelope()):
        resp = client.post(
            "/webhooks/bookingcom",
            content=raw,
            headers={"Content-Type": "application/json", "X-Booking-Signature": sig},
        )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Test 3: Correct secret + WRONG signature → 403
# ---------------------------------------------------------------------------

def test_wrong_signature_rejected(client, monkeypatch):
    monkeypatch.setenv("IHOUSE_WEBHOOK_SECRET_BOOKINGCOM", "real-secret")
    raw = json.dumps(_VALID_PAYLOAD).encode()
    with patch(_MOCK_TARGET, return_value=_FakeEnvelope()):
        resp = client.post(
            "/webhooks/bookingcom",
            content=raw,
            headers={
                "Content-Type": "application/json",
                "X-Booking-Signature": "sha256=deadbeefdeadbeef",
            },
        )
    assert resp.status_code == 403
    assert resp.json()["error"] == "SIGNATURE_VERIFICATION_FAILED"


# ---------------------------------------------------------------------------
# Test 4: Secret set, missing signature header → 403
# ---------------------------------------------------------------------------

def test_missing_signature_header_rejected(client, monkeypatch):
    monkeypatch.setenv("IHOUSE_WEBHOOK_SECRET_BOOKINGCOM", "real-secret")
    raw = json.dumps(_VALID_PAYLOAD).encode()
    with patch(_MOCK_TARGET, return_value=_FakeEnvelope()):
        resp = client.post(
            "/webhooks/bookingcom",
            content=raw,
            headers={"Content-Type": "application/json"},
            # No X-Booking-Signature header
        )
    assert resp.status_code == 403
    assert resp.json()["error"] == "SIGNATURE_VERIFICATION_FAILED"


# ---------------------------------------------------------------------------
# Test 5: Invalid payload (missing required fields) → 400 + codes
# ---------------------------------------------------------------------------

def test_invalid_payload_returns_400_with_codes(client, monkeypatch):
    monkeypatch.delenv("IHOUSE_WEBHOOK_SECRET_BOOKINGCOM", raising=False)
    bad_payload = {"some_field": "no required fields here"}
    resp = client.post(
        "/webhooks/bookingcom",
        content=json.dumps(bad_payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"] == "PAYLOAD_VALIDATION_FAILED"
    assert isinstance(body["codes"], list)
    assert len(body["codes"]) > 0


# ---------------------------------------------------------------------------
# Test 6: Non-JSON body → 400
# ---------------------------------------------------------------------------

def test_non_json_body_returns_400(client, monkeypatch):
    monkeypatch.delenv("IHOUSE_WEBHOOK_SECRET_BOOKINGCOM", raising=False)
    resp = client.post(
        "/webhooks/bookingcom",
        content=b"this is not json {{{{",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "PAYLOAD_VALIDATION_FAILED"


# ---------------------------------------------------------------------------
# Test 7: Unknown provider → 403
# ---------------------------------------------------------------------------

def test_unknown_provider_returns_403(client, monkeypatch):
    resp = client.post(
        "/webhooks/unknownproviderxyz",
        content=json.dumps(_VALID_PAYLOAD).encode(),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"] == "SIGNATURE_VERIFICATION_FAILED"


# ---------------------------------------------------------------------------
# Test 8: ingest_provider_event raises unexpectedly → 500
# ---------------------------------------------------------------------------

def test_ingest_error_returns_500(client, monkeypatch):
    monkeypatch.delenv("IHOUSE_WEBHOOK_SECRET_BOOKINGCOM", raising=False)
    with patch(_MOCK_TARGET, side_effect=RuntimeError("db is down")):
        resp = client.post(
            "/webhooks/bookingcom",
            content=json.dumps(_VALID_PAYLOAD).encode(),
            headers={"Content-Type": "application/json"},
        )
    assert resp.status_code == 500
    assert resp.json()["error"] == "INTERNAL_ERROR"


# ---------------------------------------------------------------------------
# Test 9: tenant_id propagated correctly to ingest_provider_event
# ---------------------------------------------------------------------------

def test_tenant_id_propagated(client, monkeypatch):
    """Phase 61: tenant_id comes from JWT (dev-mode returns 'dev-tenant')."""
    monkeypatch.delenv("IHOUSE_WEBHOOK_SECRET_BOOKINGCOM", raising=False)
    monkeypatch.delenv("IHOUSE_JWT_SECRET", raising=False)  # dev-mode
    with patch(_MOCK_TARGET, return_value=_FakeEnvelope()) as mock_ingest:
        client.post(
            "/webhooks/bookingcom",
            content=json.dumps(_VALID_PAYLOAD).encode(),
            headers={"Content-Type": "application/json"},
        )
    _args, kwargs = mock_ingest.call_args
    # In dev-mode (no JWT secret), jwt_auth returns "dev-tenant"
    assert kwargs.get("tenant_id") == "dev-tenant"


# ---------------------------------------------------------------------------
# Test 10: Response 200 contains the correct idempotency_key value
# ---------------------------------------------------------------------------

def test_200_response_contains_idempotency_key(client, monkeypatch):
    monkeypatch.delenv("IHOUSE_WEBHOOK_SECRET_BOOKINGCOM", raising=False)
    expected_key = "bookingcom:reservation_create:RES-001"
    fake = _FakeEnvelope(idempotency_key=expected_key)
    with patch(_MOCK_TARGET, return_value=fake):
        resp = client.post(
            "/webhooks/bookingcom",
            content=json.dumps(_VALID_PAYLOAD).encode(),
            headers={"Content-Type": "application/json"},
        )
    assert resp.status_code == 200
    assert resp.json()["idempotency_key"] == expected_key


# ---------------------------------------------------------------------------
# Test 11: Response 400 body contains "codes" list (structural guard)
# ---------------------------------------------------------------------------

def test_400_response_has_codes_list(client, monkeypatch):
    monkeypatch.delenv("IHOUSE_WEBHOOK_SECRET_BOOKINGCOM", raising=False)
    empty_payload = {}
    resp = client.post(
        "/webhooks/bookingcom",
        content=json.dumps(empty_payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert "codes" in body
    assert isinstance(body["codes"], list)


# ---------------------------------------------------------------------------
# Test 12: All 5 providers accepted in path → 200 (parametrized)
# ---------------------------------------------------------------------------

_PROVIDER_PAYLOADS = {
    "bookingcom": _VALID_PAYLOAD,
    "expedia":    _VALID_PAYLOAD,
    "airbnb":     {**_VALID_PAYLOAD, "reservation_id": "airbnb-res-001"},
    "agoda":      {
        "booking_ref": "AGA-001",
        "tenant_id": "tenant-abc",
        "occurred_at": "2024-01-15T10:00:00Z",
        "event_type": "booking.created",
        "property_id": "PROP-1",
    },
    "tripcom":    {
        "order_id": "TRIP-001",
        "tenant_id": "tenant-abc",
        "occurred_at": "2024-01-15T10:00:00Z",
        "event_type": "order_created",
        "hotel_id": "HOTEL-1",
    },
}


@pytest.mark.parametrize("provider", list(_PROVIDER_PAYLOADS.keys()))
def test_all_providers_accepted(provider, client, monkeypatch):
    """Each of the 5 OTA providers must be accepted as a valid route."""
    env_key = f"IHOUSE_WEBHOOK_SECRET_{provider.upper()}"
    monkeypatch.delenv(env_key, raising=False)
    payload = _PROVIDER_PAYLOADS[provider]
    with patch(_MOCK_TARGET, return_value=_FakeEnvelope()):
        resp = client.post(
            f"/webhooks/{provider}",
            content=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
    assert resp.status_code == 200, f"[{provider}] Expected 200, got {resp.status_code}: {resp.text}"
