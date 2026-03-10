"""
Phase 214 — Property Onboarding Wizard API Contract Tests

Tests for:
    POST /onboarding/start               — Step 1: property metadata
    POST /onboarding/{id}/channels       — Step 2: OTA channel mappings
    POST /onboarding/{id}/workers        — Step 3: worker notification channels
    GET  /onboarding/{id}/status         — Status query
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Test client + auth mock
# ---------------------------------------------------------------------------

import main

_TENANT = "tenant-onboard-test"

def _make_client() -> TestClient:
    return TestClient(main.app)

def _auth_header() -> dict:
    return {"Authorization": "Bearer mock-token"}


# ---------------------------------------------------------------------------
# DB mock factory
# ---------------------------------------------------------------------------

class _MockResult:
    def __init__(self, data=None, count=None):
        self.data = data or []
        self.count = count or 0


class _MockTable:
    """Minimal mock of supabase table query builder."""

    def __init__(self, rows=None):
        self._rows = rows or []
        self._result = _MockResult(data=self._rows)

    def select(self, *a, **kw):
        return self
    def eq(self, *a, **kw):
        return self
    def limit(self, *a):
        return self
    def order(self, *a, **kw):
        return self
    def insert(self, data):
        self._rows = [data]
        self._result = _MockResult(data=self._rows)
        return self
    def upsert(self, data, **kw):
        self._rows = [data]
        self._result = _MockResult(data=self._rows)
        return self
    def update(self, *a):
        return self
    def execute(self):
        return self._result


class _MockDB:
    def __init__(self, tables: dict):
        self._tables = tables

    def table(self, name: str):
        return self._tables.get(name, _MockTable())


def _mock_empty_db() -> _MockDB:
    """DB where all tables return empty rows."""
    return _MockDB({
        "properties":           _MockTable([]),
        "booking_state":        _MockTable([]),
        "channel_map":          _MockTable([]),
        "notification_channels": _MockTable([]),
    })


def _mock_existing_property_db() -> _MockDB:
    return _MockDB({
        "properties": _MockTable([{
            "property_id": "prop-existing",
            "display_name": "Existing Villa",
            "timezone": "Asia/Bangkok",
            "base_currency": "THB",
            "created_at": "2026-01-01T00:00:00",
        }]),
        "booking_state":         _MockTable([]),
        "channel_map":           _MockTable([{"provider": "airbnb", "external_channel_id": "AB-001"}]),
        "notification_channels": _MockTable([{"user_id": "w1", "channel_type": "line", "channel_id": "U1"}]),
    })


# ===========================================================================
# Step 1 — POST /onboarding/start
# ===========================================================================

class TestOnboardingStart:

    def test_creates_new_property(self):
        db = _empty_db_with_insert()
        with patch("api.onboarding_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.post(
                "/onboarding/start",
                json={"property_id": "prop-new", "display_name": "New Villa", "timezone": "UTC", "base_currency": "USD"},
                headers=_auth_header(),
            )
        assert resp.status_code == 201
        body = resp.json()
        assert body["property_id"] == "prop-new"
        assert body["already_exists"] is False
        assert "/channels" in body["next_step"]

    def test_returns_200_for_existing_property_no_bookings(self):
        db = _mock_existing_property_db()
        with patch("api.onboarding_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.post(
                "/onboarding/start",
                json={"property_id": "prop-existing"},
                headers=_auth_header(),
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["already_exists"] is True
        assert "/channels" in body["next_step"]

    def test_missing_property_id_returns_400(self):
        with patch("api.onboarding_router._get_supabase_client", return_value=_mock_empty_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.post(
                "/onboarding/start",
                json={"display_name": "No ID"},
                headers=_auth_header(),
            )
        assert resp.status_code == 400

    def test_invalid_currency_returns_400(self):
        with patch("api.onboarding_router._get_supabase_client", return_value=_mock_empty_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.post(
                "/onboarding/start",
                json={"property_id": "prop-bad-ccy", "base_currency": "FAKE"},
                headers=_auth_header(),
            )
        assert resp.status_code == 400

    def test_no_auth_uses_dev_tenant_in_test_mode(self):
        """In test env (no IHOUSE_JWT_SECRET) auth falls back to dev-tenant — not 401."""
        db = _empty_db_with_insert()
        with patch("api.onboarding_router._get_supabase_client", return_value=db):
            client = _make_client()
            # No Authorization header — dev-tenant is used, request proceeds
            resp = client.post("/onboarding/start", json={"property_id": "p1"})
        assert resp.status_code in (200, 201)


# ===========================================================================
# Step 2 — POST /onboarding/{property_id}/channels
# ===========================================================================

class TestOnboardingChannels:

    def test_registers_channels(self):
        with patch("api.onboarding_router._get_supabase_client", return_value=_mock_empty_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.post(
                "/onboarding/prop-abc/channels",
                json={"channels": [
                    {"provider": "airbnb", "external_channel_id": "AB-001"},
                    {"provider": "booking", "external_channel_id": "BDC-002"},
                ]},
                headers=_auth_header(),
            )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["registered"]) == 2
        assert body["errors"] == []

    def test_unknown_provider_goes_to_errors(self):
        with patch("api.onboarding_router._get_supabase_client", return_value=_mock_empty_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.post(
                "/onboarding/prop-abc/channels",
                json={"channels": [
                    {"provider": "unknown_ota", "external_channel_id": "X-001"},
                ]},
                headers=_auth_header(),
            )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["registered"]) == 0
        assert len(body["errors"]) == 1

    def test_missing_channels_returns_400(self):
        with patch("api.onboarding_router._get_supabase_client", return_value=_mock_empty_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.post(
                "/onboarding/prop-abc/channels",
                json={},
                headers=_auth_header(),
            )
        assert resp.status_code == 400

    def test_next_step_field_present(self):
        with patch("api.onboarding_router._get_supabase_client", return_value=_mock_empty_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.post(
                "/onboarding/prop-abc/channels",
                json={"channels": [{"provider": "airbnb", "external_channel_id": "AB-1"}]},
                headers=_auth_header(),
            )
        assert "/workers" in resp.json()["next_step"]

    def test_no_auth_uses_dev_tenant_in_test_mode(self):
        """In test env auth falls back to dev-tenant — not 401."""
        with patch("api.onboarding_router._get_supabase_client", return_value=_mock_empty_db()):
            client = _make_client()
            resp = client.post(
                "/onboarding/prop-abc/channels",
                json={"channels": [{"provider": "airbnb", "external_channel_id": "AB-1"}]},
            )
        assert resp.status_code == 200


# ===========================================================================
# Step 3 — POST /onboarding/{property_id}/workers
# ===========================================================================

class TestOnboardingWorkers:

    def test_registers_workers(self):
        with patch("api.onboarding_router._get_supabase_client", return_value=_mock_empty_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.post(
                "/onboarding/prop-abc/workers",
                json={"workers": [
                    {"user_id": "worker-01", "channel_type": "line", "channel_id": "Uabc123"},
                    {"user_id": "worker-02", "channel_type": "email", "channel_id": "w2@example.com"},
                ]},
                headers=_auth_header(),
            )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["registered"]) == 2
        assert body["errors"] == []

    def test_invalid_channel_type_goes_to_errors(self):
        with patch("api.onboarding_router._get_supabase_client", return_value=_mock_empty_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.post(
                "/onboarding/prop-abc/workers",
                json={"workers": [
                    {"user_id": "w1", "channel_type": "fax", "channel_id": "123"},
                ]},
                headers=_auth_header(),
            )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["registered"]) == 0
        assert len(body["errors"]) == 1

    def test_missing_workers_returns_400(self):
        with patch("api.onboarding_router._get_supabase_client", return_value=_mock_empty_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.post(
                "/onboarding/prop-abc/workers",
                json={},
                headers=_auth_header(),
            )
        assert resp.status_code == 400

    def test_next_step_field_present(self):
        with patch("api.onboarding_router._get_supabase_client", return_value=_mock_empty_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.post(
                "/onboarding/prop-abc/workers",
                json={"workers": [{"user_id": "w1", "channel_type": "line", "channel_id": "U1"}]},
                headers=_auth_header(),
            )
        assert "/status" in resp.json()["next_step"]

    def test_no_auth_uses_dev_tenant_in_test_mode(self):
        """In test env auth falls back to dev-tenant — not 401."""
        with patch("api.onboarding_router._get_supabase_client", return_value=_mock_empty_db()):
            client = _make_client()
            resp = client.post(
                "/onboarding/prop-abc/workers",
                json={"workers": [{"user_id": "w1", "channel_type": "line", "channel_id": "U1"}]},
            )
        assert resp.status_code == 200


# ===========================================================================
# Status — GET /onboarding/{property_id}/status
# ===========================================================================

class TestOnboardingStatus:

    def test_returns_200_always(self):
        with patch("api.onboarding_router._get_supabase_client", return_value=_mock_empty_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.get("/onboarding/prop-unknown/status", headers=_auth_header())
        assert resp.status_code == 200

    def test_zero_steps_on_fresh_property(self):
        with patch("api.onboarding_router._get_supabase_client", return_value=_mock_empty_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.get("/onboarding/prop-fresh/status", headers=_auth_header())
        body = resp.json()
        assert body["steps_complete"] == 0
        assert body["onboarding_done"] is False

    def test_three_steps_complete(self):
        db = _mock_existing_property_db()
        with patch("api.onboarding_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.get("/onboarding/prop-existing/status", headers=_auth_header())
        body = resp.json()
        assert body["steps_complete"] == 3
        assert body["onboarding_done"] is True

    def test_response_has_step_keys(self):
        with patch("api.onboarding_router._get_supabase_client", return_value=_mock_empty_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.get("/onboarding/prop-x/status", headers=_auth_header())
        body = resp.json()
        assert "step_1_property" in body["steps"]
        assert "step_2_channels" in body["steps"]
        assert "step_3_workers" in body["steps"]

    def test_no_auth_uses_dev_tenant_in_test_mode(self):
        """In test env auth falls back to dev-tenant — not 401."""
        with patch("api.onboarding_router._get_supabase_client", return_value=_mock_empty_db()):
            client = _make_client()
            resp = client.get("/onboarding/prop-x/status")
        assert resp.status_code == 200


# ===========================================================================
# Helper: DB with insert that returns data
# ===========================================================================

def _empty_db_with_insert() -> _MockDB:
    """DB where properties table returns the inserted row."""

    class _InsertableTable(_MockTable):
        def __init__(self):
            super().__init__([])
        def eq(self, *a, **kw):
            return self
        def insert(self, data):
            self._rows = [data]
            self._result = _MockResult(data=self._rows)
            return self
        def execute(self):
            return self._result

    class _DB:
        def table(self, name):
            return _InsertableTable()

    return _DB()
