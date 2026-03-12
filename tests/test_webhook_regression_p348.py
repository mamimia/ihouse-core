"""
Phase 348 — Webhook Ingestion Regression Suite
================================================

Regression tests for the OTA webhook ingestion pipeline.

Groups:
  A — All 14 OTA adapters normalize() contract (14 parametrized × 2 = 28 tests)
  B — All 14 OTA adapters to_canonical_envelope() (14 parametrized × 2 = 28 tests)
  C — LINE webhook endpoint regression (5 tests)
  D — Webhook event log regression (4 tests)
  E — Adapter edge cases + registry (5 tests)
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

os.environ.setdefault("IHOUSE_ENV", "test")
os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("SUPABASE_URL", "http://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("IHOUSE_GUEST_TOKEN_SECRET", "test-guest-secret-long-enough-32b")

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from main import app  # noqa: E402
from adapters.ota.registry import get_adapter, _ADAPTERS  # noqa: E402
from adapters.ota.schemas import (  # noqa: E402
    NormalizedBookingEvent,
    ClassifiedBookingEvent,
    CanonicalEnvelope,
)

client = TestClient(app, raise_server_exceptions=False)

TENANT = "test-tenant"

# ---------------------------------------------------------------------------
# Provider-correct minimal payloads (each adapter has unique field names)
# ---------------------------------------------------------------------------

_BASE = {
    "tenant_id": TENANT,
    "event_id": "evt-001",
    "occurred_at": "2026-06-01T10:00:00+00:00",
    "event_type": "reservation.created",
    "status": "confirmed",
    "check_in": "2026-06-01",
    "check_out": "2026-06-05",
    "guest_name": "Test Guest",
    "total_price": 500.0,
    "currency": "USD",
}

def _p(overrides: dict) -> dict:
    return {**_BASE, **overrides}

_PAYLOADS: dict[str, dict] = {
    "bookingcom": _p({"reservation_id": "BC-001", "property_id": "prop-001"}),
    "expedia":    _p({"reservation_id": "EX-001", "property_id": "prop-001"}),
    "airbnb":     _p({"reservation_id": "AB-001", "listing_id": "listing-001", "nights": 4}),
    "agoda":      _p({"booking_ref": "AG-001", "property_id": "prop-001"}),
    "tripcom":    _p({"booking_ref": "TC-001", "hotel_id": "hotel-001"}),
    "vrbo":       _p({"reservation_id": "VR-001", "unit_id": "unit-001"}),
    "gvr":        _p({"gvr_booking_id": "GVR-001", "property_id": "prop-001"}),
    "traveloka":  _p({"event_reference": "evt-tv-001", "booking_code": "TV-001", "property_code": "prop-001"}),
    "makemytrip": _p({"booking_id": "MMT-001", "hotel_id": "hotel-001"}),
    "klook":      _p({"booking_ref": "KL-001", "activity_id": "act-001"}),
    "despegar":   _p({"reservation_code": "DG-001", "hotel_id": "hotel-001"}),
    "hotelbeds":  _p({"voucher_ref": "HB-001", "hotel_code": "hcode-001"}),
    "rakuten":    _p({"booking_ref": "RAK-001", "hotel_code": "hcode-001"}),
    "hostelworld": _p({"reservation_id": "HW-001", "property_id": "prop-001"}),
}

ALL_PROVIDERS = sorted(_PAYLOADS.keys())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _query_chain(rows: list | None = None):
    q = MagicMock()
    for m in ("select", "eq", "gte", "lte", "lt", "neq", "in_", "is_",
              "limit", "order", "insert", "update", "upsert", "delete"):
        setattr(q, m, MagicMock(return_value=q))
    q.execute.return_value = MagicMock(data=rows if rows is not None else [])
    return q


# ---------------------------------------------------------------------------
# Group A — All 14 OTA Adapters normalize() Contract
# ---------------------------------------------------------------------------

class TestGroupAAdapterNormalize:

    @pytest.mark.parametrize("provider", ALL_PROVIDERS)
    def test_normalize_returns_correct_type(self, provider: str):
        adapter = get_adapter(provider)
        result = adapter.normalize(_PAYLOADS[provider])
        assert isinstance(result, NormalizedBookingEvent)

    @pytest.mark.parametrize("provider", ALL_PROVIDERS)
    def test_normalize_has_required_fields(self, provider: str):
        adapter = get_adapter(provider)
        n = adapter.normalize(_PAYLOADS[provider])
        assert n.tenant_id == TENANT
        assert n.provider == adapter.provider
        assert n.reservation_id  # non-empty
        assert n.property_id     # non-empty
        assert n.external_event_id  # non-empty
        assert isinstance(n.payload, dict)


# ---------------------------------------------------------------------------
# Group B — All 14 OTA Adapters to_canonical_envelope() Contract
# ---------------------------------------------------------------------------

class TestGroupBAdapterEnvelope:

    @pytest.mark.parametrize("provider", ALL_PROVIDERS)
    def test_envelope_returns_correct_type(self, provider: str):
        adapter = get_adapter(provider)
        normalized = adapter.normalize(_PAYLOADS[provider])
        classified = ClassifiedBookingEvent(normalized=normalized, semantic_kind="CREATE")
        envelope = adapter.to_canonical_envelope(classified)
        assert isinstance(envelope, CanonicalEnvelope)

    @pytest.mark.parametrize("provider", ALL_PROVIDERS)
    def test_envelope_has_required_fields(self, provider: str):
        adapter = get_adapter(provider)
        normalized = adapter.normalize(_PAYLOADS[provider])
        classified = ClassifiedBookingEvent(normalized=normalized, semantic_kind="CREATE")
        envelope = adapter.to_canonical_envelope(classified)
        assert envelope.tenant_id == TENANT
        assert envelope.type  # non-empty
        assert envelope.occurred_at is not None
        assert isinstance(envelope.payload, dict)
        assert envelope.idempotency_key  # non-empty


# ---------------------------------------------------------------------------
# Group C — LINE Webhook Endpoint Regression
# ---------------------------------------------------------------------------

class TestGroupCLineWebhook:

    def test_c1_pending_task_acknowledged(self):
        task_row = {"task_id": "T-L-001", "status": "PENDING", "updated_at": None}
        updated_row = {**task_row, "status": "ACKNOWLEDGED"}
        with patch("api.line_webhook_router._get_supabase_client") as mock:
            db = MagicMock()
            db.table.side_effect = [_query_chain([task_row]), _query_chain([updated_row])]
            mock.return_value = db
            r = client.post("/line/webhook", json={"task_id": "T-L-001"})
        assert r.status_code == 200
        assert r.json()["status"] == "ACKNOWLEDGED"

    def test_c2_already_acknowledged_idempotent(self):
        task_row = {"task_id": "T-L-002", "status": "ACKNOWLEDGED"}
        with patch("api.line_webhook_router._get_supabase_client") as mock:
            db = MagicMock()
            db.table.return_value = _query_chain([task_row])
            mock.return_value = db
            r = client.post("/line/webhook", json={"task_id": "T-L-002"})
        assert r.status_code == 200

    def test_c3_terminal_task_returns_409(self):
        task_row = {"task_id": "T-L-003", "status": "COMPLETED"}
        with patch("api.line_webhook_router._get_supabase_client") as mock:
            db = MagicMock()
            db.table.return_value = _query_chain([task_row])
            mock.return_value = db
            r = client.post("/line/webhook", json={"task_id": "T-L-003"})
        assert r.status_code == 409

    def test_c4_not_found_returns_404(self):
        with patch("api.line_webhook_router._get_supabase_client") as mock:
            db = MagicMock()
            db.table.return_value = _query_chain([])
            mock.return_value = db
            r = client.post("/line/webhook", json={"task_id": "T-NONE"})
        assert r.status_code == 404

    def test_c5_missing_task_id_returns_400(self):
        r = client.post("/line/webhook", json={"acked_by": "worker-1"})
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Group D — Webhook Event Log Regression
# ---------------------------------------------------------------------------

class TestGroupDWebhookEventLog:

    def test_d1_log_creates_entry(self):
        from services.webhook_event_log import log_webhook_event, get_webhook_log, clear_webhook_log
        clear_webhook_log()
        log_webhook_event(
            provider="bookingcom", event_type="reservation.created",
            payload={"reservation_id": "BC-TEST"}, outcome="accepted",
        )
        logs = get_webhook_log()
        assert len(logs) >= 1
        assert logs[0].provider == "bookingcom"
        clear_webhook_log()

    def test_d2_log_stats_returns_dict(self):
        from services.webhook_event_log import get_webhook_log_stats, clear_webhook_log
        clear_webhook_log()
        stats = get_webhook_log_stats()
        assert isinstance(stats, dict)
        assert "total" in stats
        assert stats["total"] == 0

    def test_d3_log_stores_rejected_events(self):
        from services.webhook_event_log import log_webhook_event, get_webhook_log, clear_webhook_log
        clear_webhook_log()
        log_webhook_event(
            provider="airbnb", event_type="reservation.error",
            payload={"error": "invalid"}, outcome="rejected",
        )
        logs = get_webhook_log(outcome="rejected")
        assert len(logs) >= 1
        assert logs[0].outcome == "rejected"
        clear_webhook_log()

    def test_d4_clear_log_empties(self):
        from services.webhook_event_log import log_webhook_event, get_webhook_log, clear_webhook_log
        log_webhook_event(provider="test", event_type="t", payload={}, outcome="accepted")
        clear_webhook_log()
        assert len(get_webhook_log()) == 0


# ---------------------------------------------------------------------------
# Group E — Adapter Edge Cases + Registry
# ---------------------------------------------------------------------------

class TestGroupEEdgeCases:

    def test_e1_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="unsupported_channel"):
            get_adapter("unknown_ota")

    def test_e2_ctrip_alias_uses_tripcom(self):
        assert type(get_adapter("ctrip")) is type(get_adapter("tripcom"))

    def test_e3_adapter_provider_matches_key(self):
        for name, adapter in _ADAPTERS.items():
            if name == "ctrip":
                continue
            assert adapter.provider == name

    def test_e4_all_implement_interface(self):
        from adapters.ota.base import OTAAdapter
        for name, adapter in _ADAPTERS.items():
            assert isinstance(adapter, OTAAdapter)

    def test_e5_normalize_preserves_tenant(self):
        for name, adapter in _ADAPTERS.items():
            base = name if name != "ctrip" else "tripcom"
            payload = {**_PAYLOADS[base], "tenant_id": "tenant-xyz"}
            result = adapter.normalize(payload)
            assert result.tenant_id == "tenant-xyz"
