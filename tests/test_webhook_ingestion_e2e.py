"""
Phase 269 — E2E Webhook Ingestion Integration Test

HTTP-level end-to-end tests for POST /webhooks/{provider}.

Flow under test (from webhooks.py):
  1. jwt_auth       → dev mode: IHOUSE_JWT_SECRET unset → tenant_id = 'dev-tenant'
  2. sig verify     → dev mode: IHOUSE_WEBHOOK_SECRET_{PROVIDER} unset → skipped
  3. json.loads     → 400 on invalid JSON
  4. validate_ota_payload → 400 on structural errors
  5. ingest_provider_event → mocked → {'status': 'ACCEPTED', 'idempotency_key': ...}

Groups:
  A — Happy path (known providers with valid payloads)
  B — Signature bypass / unknown provider (403)
  C — Invalid JSON body (400)
  D — Payload validation failures (400)
  E — Response shape invariants

CI-safe: no live DB, no staging, IHOUSE_JWT_SECRET and IHOUSE_WEBHOOK_SECRET_* unset.
"""
from __future__ import annotations

import json
import os
import sys
from unittest.mock import MagicMock, patch

os.environ.setdefault("IHOUSE_ENV", "test")

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from main import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)

TENANT = "dev-tenant"


# ---------------------------------------------------------------------------
# Minimal valid payloads per provider
# ---------------------------------------------------------------------------

AIRBNB_PAYLOAD = {
    "reservation_id": "HM123456789",
    "type": "RESERVATION_CREATED",
    "status": "accepted",
    "guest_details": {"name": "Alice Test", "phone": "+1-555-0001"},
    "listing_id": "listing-99",
    "checkout_date": "2026-09-05",
    "checkin_date": "2026-09-01",
    "number_of_guests": 2,
    "occurred_at": "2026-03-11T12:00:00+00:00",
    "payout_price_breakdown": {
        "host_payout": {"amount": "850.00", "currency": "USD"},
        "accommodation_fare": {"amount": "1000.00", "currency": "USD"},
        "cleaning_fee": None,
        "service_fee": {"amount": "150.00", "currency": "USD"},
        "host_service_fee": None,
    },
}

BOOKINGCOM_PAYLOAD = {
    "event": "reservation.created",
    "reservation_id": "BDC-456789",
    "hotel_id": "hotel-01",
    "status": "CONFIRMED",
    "check_in": "2026-09-01",
    "check_out": "2026-09-05",
    "currency": "THB",
    "total_price": "8000.00",
    "commission": "1200.00",
    "occurred_at": "2026-03-11T12:00:00+00:00",
    "guest": {"first_name": "Bob", "last_name": "Test"},
    "created": "2026-03-11T12:00:00Z",
}

AGODA_PAYLOAD = {
    "event_type": "BOOKING_CREATED",
    "booking_id": "AGO-789012",
    "hotel_id": "agoda-hotel-01",
    "check_in_date": "2026-09-01",
    "check_out_date": "2026-09-05",
    "currency": "USD",
    "total_amount": "750.00",
    "net_amount": "637.50",
    "commission_amount": "112.50",
    "occurred_at": "2026-03-11T12:00:00+00:00",
    "guest_info": {"name": "Carol Test"},
    "created_at": "2026-03-11T10:00:00Z",
}


def _mock_envelope(provider: str = "airbnb", booking_id: str = "bk001"):
    env = MagicMock()
    env.idempotency_key = f"{provider}_{booking_id}_v1"
    return env


def _post_webhook(provider: str, payload: dict, extra_headers: dict | None = None):
    headers = {"Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    return client.post(
        f"/webhooks/{provider}",
        content=json.dumps(payload).encode(),
        headers=headers,
    )


# ---------------------------------------------------------------------------
# Group A — Happy path (valid payload → 200 ACCEPTED)
# ---------------------------------------------------------------------------

class TestGroupAHappyPath:

    def test_a1_airbnb_valid_payload_returns_200(self):
        with patch("api.webhooks.ingest_provider_event", return_value=_mock_envelope("airbnb")):
            r = _post_webhook("airbnb", AIRBNB_PAYLOAD)
        assert r.status_code == 200, f"Got {r.status_code}: {r.text}"

    def test_a2_airbnb_response_status_accepted(self):
        with patch("api.webhooks.ingest_provider_event", return_value=_mock_envelope("airbnb")):
            r = _post_webhook("airbnb", AIRBNB_PAYLOAD)
        assert r.json()["status"] == "ACCEPTED"

    def test_a3_airbnb_response_has_idempotency_key(self):
        with patch("api.webhooks.ingest_provider_event", return_value=_mock_envelope("airbnb")):
            r = _post_webhook("airbnb", AIRBNB_PAYLOAD)
        assert "idempotency_key" in r.json()

    def test_a4_bookingcom_valid_payload_returns_200(self):
        with patch("api.webhooks.ingest_provider_event", return_value=_mock_envelope("bookingcom")):
            r = _post_webhook("bookingcom", BOOKINGCOM_PAYLOAD)
        assert r.status_code == 200, f"Got {r.status_code}: {r.text}"

    def test_a5_agoda_valid_payload_returns_200(self):
        with patch("api.webhooks.ingest_provider_event", return_value=_mock_envelope("agoda")):
            r = _post_webhook("agoda", AGODA_PAYLOAD)
        assert r.status_code == 200, f"Got {r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# Group B — Unknown provider (403 via sig verification)
# ---------------------------------------------------------------------------

class TestGroupBUnknownProvider:

    def test_b1_unknown_provider_returns_403(self):
        r = _post_webhook("noprovider_xyz", {"any": "payload"})
        assert r.status_code == 403, f"Got {r.status_code}: {r.text}"

    def test_b2_unknown_provider_error_field_present(self):
        r = _post_webhook("noprovider_xyz", {"any": "payload"})
        body = r.json()
        assert "error" in body

    def test_b3_provider_with_sig_secret_set_checks_sig(self):
        """When a sig secret IS set, missing header should fail with 403."""
        with patch.dict(os.environ, {"IHOUSE_WEBHOOK_SECRET_AIRBNB": "test-secret"}):
            r = _post_webhook("airbnb", AIRBNB_PAYLOAD)
        # Should be 403 (signature header missing/wrong)
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# Group C — Invalid JSON body (400)
# ---------------------------------------------------------------------------

class TestGroupCInvalidJson:

    def test_c1_empty_body_returns_400(self):
        r = client.post(
            "/webhooks/airbnb",
            content=b"",
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 400, f"Got {r.status_code}: {r.text}"

    def test_c2_malformed_json_returns_400(self):
        r = client.post(
            "/webhooks/airbnb",
            content=b"{not valid json",
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 400

    def test_c3_error_code_payload_validation_failed(self):
        r = client.post(
            "/webhooks/airbnb",
            content=b"not-json-at-all",
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 400
        assert r.json().get("error") == "PAYLOAD_VALIDATION_FAILED"


# ---------------------------------------------------------------------------
# Group D — Payload validation failures (400)
# ---------------------------------------------------------------------------

class TestGroupDPayloadValidation:

    def test_d1_empty_dict_payload_returns_400(self):
        r = _post_webhook("airbnb", {})
        assert r.status_code == 400, f"Got {r.status_code}: {r.text}"

    def test_d2_missing_required_fields_returns_400(self):
        r = _post_webhook("bookingcom", {"only_key": "value"})
        assert r.status_code == 400

    def test_d3_error_codes_list_present_on_validation_fail(self):
        r = _post_webhook("airbnb", {})
        body = r.json()
        assert "codes" in body or "error" in body

    def test_d4_agoda_missing_booking_id_returns_400(self):
        bad = {k: v for k, v in AGODA_PAYLOAD.items() if k != "booking_id"}
        r = _post_webhook("agoda", bad)
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Group E — Response shape invariants
# ---------------------------------------------------------------------------

class TestGroupEResponseShape:

    def test_e1_200_body_is_json(self):
        with patch("api.webhooks.ingest_provider_event", return_value=_mock_envelope("airbnb")):
            r = _post_webhook("airbnb", AIRBNB_PAYLOAD)
        assert r.headers["content-type"].startswith("application/json")

    def test_e2_403_body_has_error_key(self):
        r = _post_webhook("badprovider", {})
        assert "error" in r.json()

    def test_e3_400_body_has_error_key(self):
        r = _post_webhook("airbnb", {})
        assert "error" in r.json()

    def test_e4_idempotency_key_is_string(self):
        with patch("api.webhooks.ingest_provider_event", return_value=_mock_envelope("airbnb", "res001")):
            r = _post_webhook("airbnb", AIRBNB_PAYLOAD)
        assert isinstance(r.json()["idempotency_key"], str)

    def test_e5_content_type_400_is_json(self):
        r = _post_webhook("airbnb", {})
        assert r.headers["content-type"].startswith("application/json")
