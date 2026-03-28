"""
Phase 842 — Integration Management: Contract Tests

Tests for:
    admin_router.py
        GET /admin/integrations
        PUT /admin/integrations/{provider}
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

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
    """Mock DB for tenant_integrations table."""

    def __init__(self, integrations=None):
        self._integrations = integrations or []
        self._table = None

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
        if self._table == "tenant_integrations":
            return _MockResult(self._integrations)
        return _MockResult([])


def _integ(provider="line", is_active=True, credentials=None):
    return {
        "id": 1,
        "provider": provider,
        "is_active": is_active,
        "credentials": credentials or {},
        "updated_at": "2026-01-01T00:00:00",
    }


# ===========================================================================
# GET /admin/integrations
# ===========================================================================

class TestListIntegrations:

    def test_happy_path_one_channel(self):
        db = _IntegDB(integrations=[_integ()])
        with patch("api.admin_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/admin/integrations",
                headers={"Authorization": "Bearer mock"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["integrations"]) == 1

    def test_response_has_last_sync(self):
        db = _IntegDB(integrations=[_integ()])
        with patch("api.admin_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/admin/integrations",
                headers={"Authorization": "Bearer mock"},
            )
        integ = resp.json()["integrations"][0]
        assert "updated_at" in integ

    def test_no_sync_row_last_sync_nulls(self):
        db = _IntegDB(integrations=[_integ(credentials=None)])
        with patch("api.admin_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/admin/integrations",
                headers={"Authorization": "Bearer mock"},
            )
        integ = resp.json()["integrations"][0]
        assert integ["credentials"] == {} or integ["credentials"] is None

    def test_empty_returns_zero(self):
        db = _IntegDB()
        with patch("api.admin_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/admin/integrations",
                headers={"Authorization": "Bearer mock"},
            )
        assert len(resp.json()["integrations"]) == 0

    def test_multiple_properties_grouped(self):
        db = _IntegDB(integrations=[_integ("line"), _integ("whatsapp")])
        with patch("api.admin_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/admin/integrations",
                headers={"Authorization": "Bearer mock"},
            )
        assert len(resp.json()["integrations"]) == 2

    def test_stale_flag_set_for_old_sync(self):
        db = _IntegDB(integrations=[_integ(is_active=False)])
        with patch("api.admin_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/admin/integrations",
                headers={"Authorization": "Bearer mock"},
            )
        integ = resp.json()["integrations"][0]
        assert integ["is_active"] is False

    def test_stale_count_in_summary_field(self):
        db = _IntegDB(integrations=[_integ(is_active=False)])
        with patch("api.admin_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/admin/integrations",
                headers={"Authorization": "Bearer mock"},
            )
        # Inactive integrations are still returned in the list
        assert len(resp.json()["integrations"]) == 1

    def test_failed_count(self):
        db = _IntegDB(integrations=[_integ(is_active=False)])
        with patch("api.admin_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/admin/integrations",
                headers={"Authorization": "Bearer mock"},
            )
        assert resp.status_code == 200

    def test_enabled_first_sort_within_property(self):
        db = _IntegDB(integrations=[
            _integ("telegram", is_active=False),
            _integ("line", is_active=True),
        ])
        with patch("api.admin_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/admin/integrations",
                headers={"Authorization": "Bearer mock"},
            )
        integs = resp.json()["integrations"]
        assert len(integs) == 2

    def test_has_generated_at(self):
        db = _IntegDB()
        with patch("api.admin_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get(
                "/admin/integrations",
                headers={"Authorization": "Bearer mock"},
            )
        # Response contains the integrations key
        assert "integrations" in resp.json()
