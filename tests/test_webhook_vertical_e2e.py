"""
Phase 319 — Vertical Webhook Integration Test
==============================================

Tests the REAL ingestion pipeline — no mocks on normalize/envelope.

Group A: Direct pipeline test — call ingest_provider_event() directly.
         Validates normalize + classify + to_canonical_envelope.
Group B: HTTP vertical test — POST /webhooks/{provider}.
         Full stack: HTTP → sig (dev-skip) → validate → pipeline → 200.

Uses adapter-correct payloads that include ALL required fields
(event_id, tenant_id injected by pipeline, Airbnb-specific fields etc.).

CI-safe: no live DB, dev mode, no secrets needed.
"""
from __future__ import annotations

import json
import os
import sys
from copy import deepcopy

import pytest

os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("IHOUSE_ENV", "test")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from fastapi.testclient import TestClient
from main import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _dev_mode(monkeypatch):
    monkeypatch.setenv("IHOUSE_DEV_MODE", "true")


# ---------------------------------------------------------------------------
# Adapter-correct payloads (include event_id + all required fields)
# ---------------------------------------------------------------------------

AIRBNB_PAYLOAD = {
    "event_id": "airbnb_vert_001",
    "reservation_id": "HM-VERT-001",
    "type": "RESERVATION_CREATED",
    "status": "accepted",
    "guest_details": {"name": "Vertical Test", "phone": "+1-555-0099"},
    "listing_id": "listing-vert",
    "checkin_date": "2026-10-01",
    "checkout_date": "2026-10-05",
    "number_of_guests": 3,
    "occurred_at": "2026-03-12T12:00:00+00:00",
    "payout_price_breakdown": {
        "host_payout": {"amount": "500.00", "currency": "USD"},
        "accommodation_fare": {"amount": "600.00", "currency": "USD"},
        "cleaning_fee": None,
        "service_fee": {"amount": "100.00", "currency": "USD"},
        "host_service_fee": None,
    },
}

BOOKINGCOM_PAYLOAD = {
    "event_id": "bdc_vert_001",
    "event_type": "reservation_create",
    "reservation_id": "BDC-VERT-001",
    "property_id": "prop-vert-bdc",
    "occurred_at": "2026-03-12T12:00:00+00:00",
}

AGODA_PAYLOAD = {
    "event_id": "agoda_vert_001",
    "event_type": "booking.created",
    "booking_ref": "AGO-VERT-001",
    "property_id": "prop-vert-agoda",
    "occurred_at": "2026-03-12T12:00:00+00:00",
}

PIPELINE_PROVIDERS = {
    "airbnb": AIRBNB_PAYLOAD,
    "bookingcom": BOOKINGCOM_PAYLOAD,
    "agoda": AGODA_PAYLOAD,
}


def _post(provider: str, payload: dict):
    return client.post(
        f"/webhooks/{provider}",
        content=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )


# ---------------------------------------------------------------------------
# Group A — Direct pipeline tests (bypass HTTP, test real normalize)
# ---------------------------------------------------------------------------

class TestDirectPipeline:
    """Call ingest_provider_event → validates normalize + classify + envelope."""

    @pytest.mark.parametrize("provider,payload", PIPELINE_PROVIDERS.items())
    def test_ingest_returns_envelope(self, provider, payload):
        from adapters.ota.service import ingest_provider_event
        envelope = ingest_provider_event(provider, payload, "vert-tenant")
        assert envelope is not None

    @pytest.mark.parametrize("provider,payload", PIPELINE_PROVIDERS.items())
    def test_envelope_type_is_booking_created(self, provider, payload):
        from adapters.ota.service import ingest_provider_event
        envelope = ingest_provider_event(provider, payload, "vert-tenant")
        assert envelope.type == "BOOKING_CREATED"

    @pytest.mark.parametrize("provider,payload", PIPELINE_PROVIDERS.items())
    def test_envelope_has_idempotency_key(self, provider, payload):
        from adapters.ota.service import ingest_provider_event
        envelope = ingest_provider_event(provider, payload, "vert-tenant")
        assert envelope.idempotency_key and len(envelope.idempotency_key) > 0

    @pytest.mark.parametrize("provider,payload", PIPELINE_PROVIDERS.items())
    def test_envelope_has_occurred_at(self, provider, payload):
        from adapters.ota.service import ingest_provider_event
        envelope = ingest_provider_event(provider, payload, "vert-tenant")
        assert envelope.occurred_at is not None

    @pytest.mark.parametrize("provider,payload", PIPELINE_PROVIDERS.items())
    def test_envelope_payload_is_dict(self, provider, payload):
        from adapters.ota.service import ingest_provider_event
        envelope = ingest_provider_event(provider, payload, "vert-tenant")
        assert isinstance(envelope.payload, dict)

    @pytest.mark.parametrize("provider,payload", PIPELINE_PROVIDERS.items())
    def test_envelope_tenant_id_matches(self, provider, payload):
        from adapters.ota.service import ingest_provider_event
        envelope = ingest_provider_event(provider, payload, "vert-tenant")
        assert envelope.tenant_id == "vert-tenant"

    @pytest.mark.parametrize("provider,payload", PIPELINE_PROVIDERS.items())
    def test_envelope_idempotency_key_contains_provider(self, provider, payload):
        from adapters.ota.service import ingest_provider_event
        envelope = ingest_provider_event(provider, payload, "vert-tenant")
        assert provider in envelope.idempotency_key


# ---------------------------------------------------------------------------
# Group B — HTTP vertical (full stack, registered providers)
# ---------------------------------------------------------------------------

class TestHTTPVertical:
    """POST /webhooks/{provider} → real pipeline → 200 ACCEPTED."""

    @pytest.mark.parametrize("provider,payload", PIPELINE_PROVIDERS.items())
    def test_full_pipeline_returns_200(self, provider, payload):
        r = _post(provider, payload)
        assert r.status_code == 200, f"{provider}: {r.status_code} {r.text}"

    @pytest.mark.parametrize("provider,payload", PIPELINE_PROVIDERS.items())
    def test_response_status_accepted(self, provider, payload):
        r = _post(provider, payload)
        assert r.json()["status"] == "ACCEPTED"

    @pytest.mark.parametrize("provider,payload", PIPELINE_PROVIDERS.items())
    def test_response_idempotency_key_present(self, provider, payload):
        r = _post(provider, payload)
        key = r.json().get("idempotency_key", "")
        assert isinstance(key, str) and len(key) > 0

    @pytest.mark.parametrize("provider,payload", PIPELINE_PROVIDERS.items())
    def test_response_idempotency_key_contains_provider(self, provider, payload):
        r = _post(provider, payload)
        key = r.json()["idempotency_key"]
        assert provider in key
