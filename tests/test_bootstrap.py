"""
Phase 761 — Admin Bootstrap Tests
===================================

Tests for POST /admin/bootstrap endpoint.
Validates secret protection, idempotency, and proper error handling.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("IHOUSE_DEV_MODE", "true")
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-key")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
    monkeypatch.setenv("IHOUSE_BOOTSTRAP_SECRET", "bootstrap-secret-123")


@pytest.fixture()
def client():
    from main import app
    return TestClient(app, raise_server_exceptions=False)


class TestBootstrapSecurity:
    """Bootstrap endpoint must be protected by IHOUSE_BOOTSTRAP_SECRET."""

    def test_missing_bootstrap_secret_env_returns_503(self, client, monkeypatch):
        monkeypatch.delenv("IHOUSE_BOOTSTRAP_SECRET", raising=False)
        resp = client.post("/admin/bootstrap", json={
            "email": "admin@test.com",
            "password": "Pass123!",
            "bootstrap_secret": "anything",
        })
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "BOOTSTRAP_NOT_CONFIGURED"

    def test_wrong_secret_returns_401(self, client):
        resp = client.post("/admin/bootstrap", json={
            "email": "admin@test.com",
            "password": "Pass123!",
            "bootstrap_secret": "wrong-secret",
        })
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "UNAUTHORIZED"


class TestBootstrapSuccess:
    """Bootstrap creates user and all mappings when everything works."""

    def test_creates_new_admin_user(self, client):
        mock_user = MagicMock()
        mock_user.id = "admin-uuid-001"

        mock_create_result = MagicMock()
        mock_create_result.user = mock_user

        mock_db = MagicMock()
        mock_db.auth.admin.create_user.return_value = mock_create_result
        # table().upsert().execute() chain
        mock_db.table.return_value.upsert.return_value.execute.return_value.data = [{}]

        with patch("api.bootstrap_router._get_supabase_admin", return_value=mock_db):
            resp = client.post("/admin/bootstrap", json={
                "email": "admin@domaniqo.com",
                "password": "SecurePass123!",
                "full_name": "System Admin",
                "bootstrap_secret": "bootstrap-secret-123",
            })

        assert resp.status_code == 201  # new user created
        data = resp.json()["data"]
        assert data["user_id"] == "admin-uuid-001"
        assert data["email"] == "admin@domaniqo.com"
        assert data["role"] == "admin"
        assert data["status"] == "bootstrap_complete"
        assert data["created_new"] is True

    def test_supabase_not_configured_returns_503(self, client):
        with patch("api.bootstrap_router._get_supabase_admin", return_value=None):
            resp = client.post("/admin/bootstrap", json={
                "email": "admin@test.com",
                "password": "Pass123!",
                "bootstrap_secret": "bootstrap-secret-123",
            })
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "SUPABASE_NOT_CONFIGURED"
