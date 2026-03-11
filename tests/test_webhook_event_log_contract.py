"""
Phase 261 — Webhook Event Log Contract Tests
=============================================

Tests: 20 across 5 groups.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app
import services.webhook_event_log as wlog

client = TestClient(app, raise_server_exceptions=False)
_AUTH = {"Authorization": "Bearer test-token"}


@pytest.fixture(autouse=True)
def clear_log():
    """Clear the log before every test."""
    wlog.clear_webhook_log()
    yield
    wlog.clear_webhook_log()


# ---------------------------------------------------------------------------
# Group A — Service: log_webhook_event
# ---------------------------------------------------------------------------

class TestGroupALogService:

    def test_a1_log_entry_created_with_correct_fields(self):
        entry = wlog.log_webhook_event(
            provider="airbnb",
            event_type="booking_created",
            payload={"booking_ref": "AB-123", "guest": "Alice"},
            outcome=wlog.OUTCOME_ACCEPTED,
            booking_ref="AB-123",
        )
        assert entry.provider == "airbnb"
        assert entry.event_type == "booking_created"
        assert entry.booking_ref == "AB-123"
        assert entry.outcome == wlog.OUTCOME_ACCEPTED
        assert "booking_ref" in entry.payload_keys
        assert "guest" in entry.payload_keys
        assert entry.received_at is not None
        assert entry.entry_id is not None

    def test_a2_payload_values_not_stored(self):
        entry = wlog.log_webhook_event(
            provider="agoda",
            event_type="booking_cancelled",
            payload={"secret_token": "s3kr3t", "amount": 9999},
        )
        # Keys stored, values not
        assert "secret_token" in entry.payload_keys
        assert "s3kr3t" not in str(entry)

    def test_a3_rejected_entry_stores_error(self):
        entry = wlog.log_webhook_event(
            provider="booking_com",
            event_type="booking_created",
            payload={"ref": "BK-1"},
            outcome=wlog.OUTCOME_REJECTED,
            error="Signature mismatch",
        )
        assert entry.outcome == wlog.OUTCOME_REJECTED
        assert entry.error == "Signature mismatch"

    def test_a4_multiple_entries_newest_first(self):
        wlog.log_webhook_event("p1", "e1", {})
        wlog.log_webhook_event("p2", "e2", {})
        wlog.log_webhook_event("p3", "e3", {})
        results = wlog.get_webhook_log()
        # newest first: p3, p2, p1
        assert results[0].provider == "p3"
        assert results[2].provider == "p1"


# ---------------------------------------------------------------------------
# Group B — Service: get_webhook_log (filters)
# ---------------------------------------------------------------------------

class TestGroupBQueryFilters:

    def test_b1_filter_by_provider(self):
        wlog.log_webhook_event("airbnb", "booking_created", {})
        wlog.log_webhook_event("agoda", "booking_created", {})
        results = wlog.get_webhook_log(provider="airbnb")
        assert all(r.provider == "airbnb" for r in results)
        assert len(results) == 1

    def test_b2_filter_by_event_type(self):
        wlog.log_webhook_event("airbnb", "booking_created", {})
        wlog.log_webhook_event("airbnb", "booking_cancelled", {})
        results = wlog.get_webhook_log(event_type="booking_cancelled")
        assert all(r.event_type == "booking_cancelled" for r in results)

    def test_b3_filter_by_outcome(self):
        wlog.log_webhook_event("p1", "e1", {}, outcome=wlog.OUTCOME_ACCEPTED)
        wlog.log_webhook_event("p1", "e1", {}, outcome=wlog.OUTCOME_REJECTED)
        accepted = wlog.get_webhook_log(outcome=wlog.OUTCOME_ACCEPTED)
        assert all(r.outcome == wlog.OUTCOME_ACCEPTED for r in accepted)

    def test_b4_limit_respected(self):
        for i in range(10):
            wlog.log_webhook_event(f"p{i}", "e", {})
        results = wlog.get_webhook_log(limit=3)
        assert len(results) == 3

    def test_b5_combined_filters(self):
        wlog.log_webhook_event("airbnb", "booking_created", {}, outcome=wlog.OUTCOME_ACCEPTED)
        wlog.log_webhook_event("airbnb", "booking_created", {}, outcome=wlog.OUTCOME_REJECTED)
        wlog.log_webhook_event("agoda",  "booking_created", {}, outcome=wlog.OUTCOME_ACCEPTED)
        results = wlog.get_webhook_log(provider="airbnb", outcome=wlog.OUTCOME_ACCEPTED)
        assert len(results) == 1
        assert results[0].provider == "airbnb"
        assert results[0].outcome == wlog.OUTCOME_ACCEPTED


# ---------------------------------------------------------------------------
# Group C — Service: get_webhook_log_stats
# ---------------------------------------------------------------------------

class TestGroupCStats:

    def test_c1_stats_total_correct(self):
        wlog.log_webhook_event("a", "e", {})
        wlog.log_webhook_event("b", "e", {})
        stats = wlog.get_webhook_log_stats()
        assert stats["total"] == 2

    def test_c2_stats_by_provider(self):
        wlog.log_webhook_event("airbnb", "e", {})
        wlog.log_webhook_event("airbnb", "e", {})
        wlog.log_webhook_event("agoda",  "e", {})
        stats = wlog.get_webhook_log_stats()
        assert stats["by_provider"]["airbnb"] == 2
        assert stats["by_provider"]["agoda"] == 1

    def test_c3_stats_by_outcome(self):
        wlog.log_webhook_event("p", "e", {}, outcome=wlog.OUTCOME_ACCEPTED)
        wlog.log_webhook_event("p", "e", {}, outcome=wlog.OUTCOME_REJECTED)
        wlog.log_webhook_event("p", "e", {}, outcome=wlog.OUTCOME_DUPLICATE)
        stats = wlog.get_webhook_log_stats()
        assert stats["by_outcome"][wlog.OUTCOME_ACCEPTED]  == 1
        assert stats["by_outcome"][wlog.OUTCOME_REJECTED]  == 1
        assert stats["by_outcome"][wlog.OUTCOME_DUPLICATE] == 1

    def test_c4_empty_log_stats(self):
        stats = wlog.get_webhook_log_stats()
        assert stats["total"] == 0
        assert stats["by_provider"] == {}


# ---------------------------------------------------------------------------
# Group D — HTTP: GET /admin/webhook-log
# ---------------------------------------------------------------------------

class TestGroupDHttpQuery:

    def test_d1_empty_log_returns_200(self):
        resp = client.get("/admin/webhook-log", headers=_AUTH)
        assert resp.status_code == 200
        assert resp.json()["entries"] == []
        assert resp.json()["total_returned"] == 0

    def test_d2_entries_appear_after_logging(self):
        wlog.log_webhook_event("airbnb", "booking_created", {"ref": "AB-1"})
        resp = client.get("/admin/webhook-log", headers=_AUTH)
        assert resp.status_code == 200
        assert resp.json()["total_returned"] == 1
        assert resp.json()["entries"][0]["provider"] == "airbnb"

    def test_d3_provider_filter_via_query_param(self):
        wlog.log_webhook_event("airbnb", "booking_created", {})
        wlog.log_webhook_event("agoda",  "booking_created", {})
        resp = client.get("/admin/webhook-log?provider=airbnb", headers=_AUTH)
        assert resp.status_code == 200
        assert all(e["provider"] == "airbnb" for e in resp.json()["entries"])


# ---------------------------------------------------------------------------
# Group E — HTTP: stats + test entry
# ---------------------------------------------------------------------------

class TestGroupEHttpStats:

    def test_e1_stats_endpoint_returns_200(self):
        resp = client.get("/admin/webhook-log/stats", headers=_AUTH)
        assert resp.status_code == 200
        body = resp.json()
        assert "total" in body
        assert "by_provider" in body
        assert "by_outcome" in body

    def test_e2_test_entry_creates_log_entry(self):
        resp = client.post(
            "/admin/webhook-log/test?provider=mytest&event_type=ping",
            headers=_AUTH,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["provider"] == "mytest"
        assert body["event_type"] == "ping"
        assert body["outcome"] == wlog.OUTCOME_ACCEPTED

    def test_e3_stats_reflect_test_entry(self):
        client.post("/admin/webhook-log/test?provider=mytest", headers=_AUTH)
        resp = client.get("/admin/webhook-log/stats", headers=_AUTH)
        assert resp.json()["by_provider"].get("mytest", 0) >= 1
