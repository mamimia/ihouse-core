"""
Phase 217 — Integration Management UI: Contract Tests

Tests for:
    integration_management_router.py
        GET /admin/integrations
        GET /admin/integrations/summary
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import main

_TENANT = "tenant-integ-test"


def _make_client() -> TestClient:
    return TestClient(main.app)


# ---------------------------------------------------------------------------
# Minimal DB mocks
# ---------------------------------------------------------------------------

class _MockResult:
    def __init__(self, data=None):
        self.data = data or []


class _IntegDB:
    """Mock DB for integration management tests."""

    def __init__(self, channels=None, sync_rows=None):
        self._channels  = channels  or []
        self._sync_rows = sync_rows or []
        self._table     = None

    def table(self, name):
        self._table = name
        return self

    def select(self, *a, **kw):
        return self

    def eq(self, col, val):
        return self

    def order(self, *a, **kw):
        return self

    def limit(self, *a, **kw):
        return self

    def execute(self):
        if self._table == "property_channel_map":
            return _MockResult(self._channels)
        if self._table == "outbound_sync_log":
            return _MockResult(self._sync_rows)
        return _MockResult([])


def _chan(property_id="prop-001", provider="airbnb", external_id="AB-123",
          sync_mode="api_first", inventory_type="single_unit", enabled=True):
    return {
        "id": 1,
        "tenant_id": _TENANT,
        "property_id": property_id,
        "provider": provider,
        "external_id": external_id,
        "inventory_type": inventory_type,
        "sync_mode": sync_mode,
        "enabled": enabled,
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
    }


def _sync(property_id="prop-001", provider="airbnb",
          status="success", executed_at="2026-03-11T01:00:00", error_message=None):
    return {
        "property_id": property_id,
        "provider": provider,
        "status": status,
        "executed_at": executed_at,
        "error_message": error_message,
    }


# ===========================================================================
# GET /admin/integrations
# ===========================================================================

class TestListIntegrations:

    def test_happy_path_one_channel(self):
        db = _IntegDB(channels=[_chan()], sync_rows=[_sync()])
        with patch("api.integration_management_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/admin/integrations",
                headers={"Authorization": "Bearer mock"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_connections"] == 1
        assert body["property_count"] == 1

    def test_response_has_last_sync(self):
        db = _IntegDB(channels=[_chan()], sync_rows=[_sync()])
        with patch("api.integration_management_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/admin/integrations",
                headers={"Authorization": "Bearer mock"},
            )
        conn = resp.json()["properties"][0]["connections"][0]
        assert "last_sync" in conn
        assert conn["last_sync"]["status"] == "success"

    def test_no_sync_row_last_sync_nulls(self):
        db = _IntegDB(channels=[_chan()], sync_rows=[])
        with patch("api.integration_management_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/admin/integrations",
                headers={"Authorization": "Bearer mock"},
            )
        conn = resp.json()["properties"][0]["connections"][0]
        assert conn["last_sync"]["executed_at"] is None
        assert conn["last_sync"]["stale"] is None

    def test_empty_returns_zero(self):
        db = _IntegDB()
        with patch("api.integration_management_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/admin/integrations",
                headers={"Authorization": "Bearer mock"},
            )
        assert resp.json()["total_connections"] == 0
        assert resp.json()["property_count"] == 0

    def test_multiple_properties_grouped(self):
        db = _IntegDB(channels=[_chan("prop-001"), _chan("prop-002")])
        with patch("api.integration_management_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/admin/integrations",
                headers={"Authorization": "Bearer mock"},
            )
        assert resp.json()["property_count"] == 2

    def test_stale_flag_set_for_old_sync(self):
        db = _IntegDB(
            channels=[_chan()],
            sync_rows=[_sync(executed_at="2026-03-08T00:00:00")],
        )
        with patch("api.integration_management_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/admin/integrations",
                headers={"Authorization": "Bearer mock"},
            )
        conn = resp.json()["properties"][0]["connections"][0]
        assert conn["last_sync"]["stale"] is True

    def test_stale_count_in_summary_field(self):
        db = _IntegDB(
            channels=[_chan()],
            sync_rows=[_sync(executed_at="2026-03-08T00:00:00")],
        )
        with patch("api.integration_management_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/admin/integrations",
                headers={"Authorization": "Bearer mock"},
            )
        assert resp.json()["stale_count"] == 1

    def test_failed_count(self):
        db = _IntegDB(
            channels=[_chan()],
            sync_rows=[_sync(status="error", error_message="timeout")],
        )
        with patch("api.integration_management_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/admin/integrations",
                headers={"Authorization": "Bearer mock"},
            )
        assert resp.json()["failed_count"] == 1

    def test_enabled_first_sort_within_property(self):
        db = _IntegDB(channels=[
            _chan("prop-001", "vrbo",    enabled=False),
            _chan("prop-001", "airbnb",  enabled=True),
        ])
        with patch("api.integration_management_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/admin/integrations",
                headers={"Authorization": "Bearer mock"},
            )
        conns = resp.json()["properties"][0]["connections"]
        assert conns[0]["enabled"] is True
        assert conns[0]["provider"] == "airbnb"

    def test_has_generated_at(self):
        db = _IntegDB()
        with patch("api.integration_management_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/admin/integrations",
                headers={"Authorization": "Bearer mock"},
            )
        assert "generated_at" in resp.json()


# ===========================================================================
# GET /admin/integrations/summary
# ===========================================================================

class TestIntegrationsSummary:

    def test_happy_path(self):
        db = _IntegDB(
            channels=[_chan("p1", "airbnb"), _chan("p2", "booking", enabled=False)],
            sync_rows=[_sync("p1", "airbnb", status="success")],
        )
        with patch("api.integration_management_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/admin/integrations/summary",
                headers={"Authorization": "Bearer mock"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_connections"] == 2
        assert body["enabled_count"] == 1
        assert body["disabled_count"] == 1

    def test_provider_distribution(self):
        db = _IntegDB(channels=[
            _chan("p1", "airbnb"),
            _chan("p2", "airbnb"),
            _chan("p3", "vrbo"),
        ])
        with patch("api.integration_management_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/admin/integrations/summary",
                headers={"Authorization": "Bearer mock"},
            )
        providers = resp.json()["providers"]
        # airbnb should appear first (count=2)
        assert providers[0]["provider"] == "airbnb"
        assert providers[0]["count"] == 2

    def test_empty_summary(self):
        db = _IntegDB()
        with patch("api.integration_management_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/admin/integrations/summary",
                headers={"Authorization": "Bearer mock"},
            )
        assert resp.status_code == 200
        assert resp.json()["total_connections"] == 0
        assert resp.json()["providers"] == []

    def test_stale_counted_in_summary(self):
        db = _IntegDB(
            channels=[_chan()],
            sync_rows=[_sync(executed_at="2026-03-08T00:00:00")],
        )
        with patch("api.integration_management_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/admin/integrations/summary",
                headers={"Authorization": "Bearer mock"},
            )
        assert resp.json()["stale_count"] == 1

    def test_no_auth_uses_dev_tenant_in_test_mode(self):
        db = _IntegDB()
        with patch("api.integration_management_router._get_supabase_client", return_value=db):
            resp = _make_client().get("/admin/integrations/summary")
        assert resp.status_code == 200
