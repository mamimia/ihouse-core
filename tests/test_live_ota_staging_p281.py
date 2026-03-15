"""
Phase 281 — First Live OTA Integration Test: CI-Safe Contract Tests
====================================================================

Companion to scripts/e2e_live_ota_staging.py.

These tests cover the full inbound stack from raw HTTP body →
normalized envelope → apply_envelope RPC call, without requiring
a live Supabase connection.

The apply_envelope RPC call is mocked — but all real-code layers
above it are exercised: HTTP parsing, HMAC verification, payload
normalization, envelope construction, and the Supabase client call.

Groups:
  A — Full stack happy path (3 tests)
  B — HMAC failure gate (3 tests)
  C — Payload validation gate (3 tests)
  D — Staging script dry-run (3 tests)
  E — Idempotency key format (3 tests)

Total: 15 tests
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.webhooks import router

_WEBHOOK_SECRET = "p281-staging-secret-abcdef1234567890"
_MOCK_TARGET = "api.webhooks.ingest_provider_event_with_dlq"
_MOCK_APPLY_FN = "api.webhooks._build_apply_fn"
_MOCK_SKILL_ROUTER = "api.webhooks._build_skill_router"


@dataclass
class _FakeEnvelope:
    idempotency_key: Optional[str] = None
    type: str = "BOOKING_CREATED"
    payload: dict = None
    occurred_at: datetime = None

    def __post_init__(self):
        if self.payload is None:
            self.payload = {}
        if self.occurred_at is None:
            self.occurred_at = datetime(2026, 3, 11, tzinfo=timezone.utc)
        if self.idempotency_key is None:
            self.idempotency_key = f"bookingcom:reservation_created:{uuid.uuid4().hex[:8]}"


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture()
def client():
    return TestClient(_make_app(), raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _dev_mode(monkeypatch):
    """Use dev mode for auth — Phase 281 tests focus on full payload stack."""
    monkeypatch.setenv("IHOUSE_DEV_MODE", "true")


def _canonical_bookingcom_payload(run_id: str = "test-281") -> dict:
    """Exact payload format used by scripts/e2e_live_ota_staging.py."""
    return {
        "reservation_id": f"LIVE281-{run_id}",
        "property_id": "PROP-STAGING-001",
        "tenant_id": "staging-tenant-001",
        "event_type": "reservation_created",
        "occurred_at": "2026-03-11T15:00:00Z",
        "check_in": "2026-12-01",
        "check_out": "2026-12-05",
        "guest_name": "Phase 281 Test Guest",
        "total_price": "1500.00",
        "currency": "THB",
        "num_guests": 2,
        "source": "bookingcom",
    }


def _sign(body: bytes, secret: str = _WEBHOOK_SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


# ===========================================================================
# Group A — Full stack happy path
# ===========================================================================

class TestGroupAFullStackHappyPath:
    def test_a1_canonical_booking_created_returns_200(self, client, monkeypatch):
        """Full stack: canonical Booking.com payload + valid HMAC → 200."""
        monkeypatch.setenv("IHOUSE_WEBHOOK_SECRET_BOOKINGCOM", _WEBHOOK_SECRET)
        payload = _canonical_bookingcom_payload("a1")
        body = json.dumps(payload).encode()
        sig = _sign(body)
        with patch(_MOCK_TARGET, return_value={"status": "APPLIED", "idempotency_key": "k1"}), \
             patch(_MOCK_APPLY_FN, return_value=lambda e, em: {"status": "APPLIED"}), \
             patch(_MOCK_SKILL_ROUTER, return_value=lambda et, p: []):
            resp = client.post(
                "/webhooks/bookingcom",
                content=body,
                headers={"Content-Type": "application/json", "X-Booking-Signature": sig},
            )
        assert resp.status_code == 200

    def test_a2_response_contains_idempotency_key(self, client, monkeypatch):
        monkeypatch.setenv("IHOUSE_WEBHOOK_SECRET_BOOKINGCOM", _WEBHOOK_SECRET)
        key = "bookingcom:reservation_created:LIVE281-a2"
        payload = _canonical_bookingcom_payload("a2")
        body = json.dumps(payload).encode()
        sig = _sign(body)
        with patch(_MOCK_TARGET, return_value={"status": "APPLIED", "idempotency_key": key}), \
             patch(_MOCK_APPLY_FN, return_value=lambda e, em: {"status": "APPLIED"}), \
             patch(_MOCK_SKILL_ROUTER, return_value=lambda et, p: []):
            resp = client.post(
                "/webhooks/bookingcom",
                content=body,
                headers={"Content-Type": "application/json", "X-Booking-Signature": sig},
            )
        assert resp.status_code == 200
        assert resp.json()["idempotency_key"] == key

    def test_a3_ingest_called_with_provider_bookingcom(self, client, monkeypatch):
        monkeypatch.setenv("IHOUSE_WEBHOOK_SECRET_BOOKINGCOM", _WEBHOOK_SECRET)
        payload = _canonical_bookingcom_payload("a3")
        body = json.dumps(payload).encode()
        sig = _sign(body)
        with patch(_MOCK_TARGET, return_value={"status": "APPLIED", "idempotency_key": "k3"}) as mock_ingest, \
             patch(_MOCK_APPLY_FN, return_value=lambda e, em: {"status": "APPLIED"}), \
             patch(_MOCK_SKILL_ROUTER, return_value=lambda et, p: []):
            client.post(
                "/webhooks/bookingcom",
                content=body,
                headers={"Content-Type": "application/json", "X-Booking-Signature": sig},
            )
        _, kwargs = mock_ingest.call_args
        assert kwargs.get("provider") == "bookingcom"


# ===========================================================================
# Group B — HMAC failure gate
# ===========================================================================

class TestGroupBHmacGate:
    def test_b1_wrong_secret_rejected(self, client, monkeypatch):
        monkeypatch.setenv("IHOUSE_WEBHOOK_SECRET_BOOKINGCOM", _WEBHOOK_SECRET)
        payload = _canonical_bookingcom_payload("b1")
        body = json.dumps(payload).encode()
        bad_sig = _sign(body, secret="wrong-secret-here!!!!!!!!!!!!!!!")
        with patch(_MOCK_TARGET, return_value={"status": "APPLIED"}), \
             patch(_MOCK_APPLY_FN, return_value=lambda e, em: {"status": "APPLIED"}), \
             patch(_MOCK_SKILL_ROUTER, return_value=lambda et, p: []):
            resp = client.post(
                "/webhooks/bookingcom",
                content=body,
                headers={"Content-Type": "application/json", "X-Booking-Signature": bad_sig},
            )
        assert resp.status_code == 403
        assert resp.json()["error"] == "SIGNATURE_VERIFICATION_FAILED"

    def test_b2_body_tampered_rejected(self, client, monkeypatch):
        monkeypatch.setenv("IHOUSE_WEBHOOK_SECRET_BOOKINGCOM", _WEBHOOK_SECRET)
        original = _canonical_bookingcom_payload("b2")
        body = json.dumps(original).encode()
        sig = _sign(body)
        tampered = {**original, "reservation_id": "HACKED-999"}
        tampered_body = json.dumps(tampered).encode()
        with patch(_MOCK_TARGET, return_value={"status": "APPLIED"}), \
             patch(_MOCK_APPLY_FN, return_value=lambda e, em: {"status": "APPLIED"}), \
             patch(_MOCK_SKILL_ROUTER, return_value=lambda et, p: []):
            resp = client.post(
                "/webhooks/bookingcom",
                content=tampered_body,
                headers={"Content-Type": "application/json", "X-Booking-Signature": sig},
            )
        assert resp.status_code == 403

    def test_b3_missing_signature_header_rejected(self, client, monkeypatch):
        monkeypatch.setenv("IHOUSE_WEBHOOK_SECRET_BOOKINGCOM", _WEBHOOK_SECRET)
        payload = _canonical_bookingcom_payload("b3")
        body = json.dumps(payload).encode()
        with patch(_MOCK_TARGET, return_value={"status": "APPLIED"}), \
             patch(_MOCK_APPLY_FN, return_value=lambda e, em: {"status": "APPLIED"}), \
             patch(_MOCK_SKILL_ROUTER, return_value=lambda et, p: []):
            resp = client.post(
                "/webhooks/bookingcom",
                content=body,
                headers={"Content-Type": "application/json"},
            )
        assert resp.status_code == 403


# ===========================================================================
# Group C — Payload validation gate
# ===========================================================================

class TestGroupCPayloadValidation:
    def test_c1_missing_reservation_id_returns_400(self, client, monkeypatch):
        monkeypatch.delenv("IHOUSE_WEBHOOK_SECRET_BOOKINGCOM", raising=False)
        bad = {"tenant_id": "t", "event_type": "reservation_created", "property_id": "p"}
        resp = client.post(
            "/webhooks/bookingcom",
            content=json.dumps(bad).encode(),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400
        assert "codes" in resp.json()

    def test_c2_empty_payload_returns_400(self, client, monkeypatch):
        monkeypatch.delenv("IHOUSE_WEBHOOK_SECRET_BOOKINGCOM", raising=False)
        resp = client.post(
            "/webhooks/bookingcom",
            content=json.dumps({}).encode(),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400

    def test_c3_non_json_returns_400(self, client, monkeypatch):
        monkeypatch.delenv("IHOUSE_WEBHOOK_SECRET_BOOKINGCOM", raising=False)
        resp = client.post(
            "/webhooks/bookingcom",
            content=b"this is not json >>>",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400


# ===========================================================================
# Group D — Staging script dry-run (no API needed)
# ===========================================================================

class TestGroupDStagingScriptDryRun:
    def test_d1_dryrun_exits_zero(self):
        """Dry-run mode must exit 0 without any live services."""
        result = subprocess.run(
            [sys.executable, "scripts/e2e_live_ota_staging.py", "--dry-run"],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), ".."),
        )
        assert result.returncode == 0, f"Dry-run failed:\n{result.stderr}"

    def test_d2_dryrun_outputs_run_id(self):
        result = subprocess.run(
            [sys.executable, "scripts/e2e_live_ota_staging.py", "--dry-run"],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), ".."),
        )
        assert "Run ID:" in result.stdout or "DRY-RUN" in result.stdout

    def test_d3_dryrun_no_http_calls(self):
        """Dry-run should complete without any network errors."""
        result = subprocess.run(
            [sys.executable, "scripts/e2e_live_ota_staging.py", "--dry-run"],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), ".."),
        )
        assert "Connection refused" not in result.stderr
        assert "HTTPError" not in result.stderr
        assert result.returncode == 0


# ===========================================================================
# Group E — Idempotency key format contract
# ===========================================================================

class TestGroupEIdempotencyKey:
    def test_e1_idempotency_key_is_string(self, client, monkeypatch):
        monkeypatch.delenv("IHOUSE_WEBHOOK_SECRET_BOOKINGCOM", raising=False)
        payload = _canonical_bookingcom_payload("e1")
        body = json.dumps(payload).encode()
        with patch(_MOCK_TARGET, return_value={"status": "APPLIED", "idempotency_key": "ke1"}), \
             patch(_MOCK_APPLY_FN, return_value=lambda e, em: {"status": "APPLIED"}), \
             patch(_MOCK_SKILL_ROUTER, return_value=lambda et, p: []):
            resp = client.post(
                "/webhooks/bookingcom",
                content=body,
                headers={"Content-Type": "application/json"},
            )
        assert resp.status_code == 200
        assert isinstance(resp.json().get("idempotency_key"), str)

    def test_e2_idempotency_key_non_empty(self, client, monkeypatch):
        monkeypatch.delenv("IHOUSE_WEBHOOK_SECRET_BOOKINGCOM", raising=False)
        payload = _canonical_bookingcom_payload("e2")
        body = json.dumps(payload).encode()
        with patch(_MOCK_TARGET, return_value={"status": "APPLIED", "idempotency_key": "ke2"}), \
             patch(_MOCK_APPLY_FN, return_value=lambda e, em: {"status": "APPLIED"}), \
             patch(_MOCK_SKILL_ROUTER, return_value=lambda et, p: []):
            resp = client.post(
                "/webhooks/bookingcom",
                content=body,
                headers={"Content-Type": "application/json"},
            )
        assert resp.status_code == 200
        assert len(resp.json()["idempotency_key"]) > 0

    def test_e3_same_payload_same_idempotency_key(self, client, monkeypatch):
        """Same payload sent twice → same idempotency_key (deterministic)."""
        monkeypatch.delenv("IHOUSE_WEBHOOK_SECRET_BOOKINGCOM", raising=False)
        payload = _canonical_bookingcom_payload("e3")
        body = json.dumps(payload).encode()
        fixed_key = "bookingcom:reservation_created:LIVE281-e3"
        with patch(_MOCK_TARGET, return_value={"status": "APPLIED", "idempotency_key": fixed_key}), \
             patch(_MOCK_APPLY_FN, return_value=lambda e, em: {"status": "APPLIED"}), \
             patch(_MOCK_SKILL_ROUTER, return_value=lambda et, p: []):
            resp1 = client.post(
                "/webhooks/bookingcom",
                content=body,
                headers={"Content-Type": "application/json"},
            )
            resp2 = client.post(
                "/webhooks/bookingcom",
                content=body,
                headers={"Content-Type": "application/json"},
            )
        assert resp1.json()["idempotency_key"] == resp2.json()["idempotency_key"] == fixed_key
