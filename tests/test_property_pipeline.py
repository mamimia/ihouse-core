"""
Phase 404 — Property Onboarding Pipeline — Contract Tests
============================================================

Tests for the approve → channel_map bridge:
    1. Approve creates channel_map entry
    2. Approve idempotent — doesn't duplicate channel_map
    3. Pending_review property from onboard submit can be approved
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("IHOUSE_JWT_SECRET", "test-secret-phase404")
    monkeypatch.setenv("IHOUSE_DEV_MODE", "true")
    monkeypatch.setenv("IHOUSE_DEV_PASSWORD", "dev")
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-key")


@pytest.fixture()
def client():
    from main import app
    from fastapi.testclient import TestClient
    return TestClient(app, raise_server_exceptions=False)


def _make_property_db(property_data: dict, channel_map_exists: bool = False):
    """Create a mock DB that handles property + channel_map operations."""
    mock_db = MagicMock()

    # Route table calls to appropriate mocks
    prop_select_result = MagicMock()
    prop_select_result.data = [property_data]

    prop_update_result = MagicMock()
    prop_update_result.data = [{**property_data, "status": "approved"}]

    channel_select_result = MagicMock()
    channel_select_result.data = [{"property_id": property_data.get("property_id")}] if channel_map_exists else []

    channel_insert_result = MagicMock()
    channel_insert_result.data = [{"property_id": property_data.get("property_id")}]

    # The tricky part: table() is called with different table names.
    # We need the mock to handle multiple tables correctly.
    def table_side_effect(name):
        t = MagicMock()
        if name == "properties":
            t.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = prop_select_result
            t.update.return_value.eq.return_value.eq.return_value.execute.return_value = prop_update_result
        elif name == "property_channel_map":
            t.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = channel_select_result
            t.insert.return_value.execute.return_value = channel_insert_result
        elif name in ("audit_events", "event_log"):
            t.insert.return_value.execute.return_value = MagicMock()
        # status summary query (select all for counting)
        if name == "properties":
            all_result = MagicMock()
            all_result.data = [property_data]
            t.select.return_value.eq.return_value.execute.return_value = all_result
        return t

    mock_db.table = MagicMock(side_effect=table_side_effect)
    return mock_db


class TestPropertyOnboardingPipeline:

    def test_approve_provisions_channel_map(self, client):
        """Approving a pending property auto-creates a channel_map entry."""
        login_resp = client.post("/auth/token", json={"tenant_id": "t1", "secret": "dev"})
        auth = {"Authorization": f"Bearer {login_resp.json()['token']}"}

        mock_db = _make_property_db({
            "property_id": "p-404",
            "tenant_id": "t1",
            "name": "Test Villa",
            "status": "pending",
            "property_type": "villa",
        }, channel_map_exists=False)

        with patch("api.property_admin_router._get_supabase_client", return_value=mock_db):
            resp = client.post("/admin/properties/p-404/approve", headers=auth)

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "approved"
        assert body.get("channel_map_provisioned") is True

    def test_approve_skips_duplicate_channel_map(self, client):
        """Re-approving doesn't duplicate channel_map (already exists)."""
        login_resp = client.post("/auth/token", json={"tenant_id": "t1", "secret": "dev"})
        auth = {"Authorization": f"Bearer {login_resp.json()['token']}"}

        mock_db = _make_property_db({
            "property_id": "p-existing",
            "tenant_id": "t1",
            "name": "Existing Villa",
            "status": "pending",
        }, channel_map_exists=True)

        with patch("api.property_admin_router._get_supabase_client", return_value=mock_db):
            resp = client.post("/admin/properties/p-existing/approve", headers=auth)

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "approved"
        # channel_map_provisioned should NOT be set (already exists)
        assert body.get("channel_map_provisioned") is None

    def test_approve_rejects_non_pending(self, client):
        """Approving an already-approved property returns 409."""
        login_resp = client.post("/auth/token", json={"tenant_id": "t1", "secret": "dev"})
        auth = {"Authorization": f"Bearer {login_resp.json()['token']}"}

        mock_db = _make_property_db({
            "property_id": "p-already",
            "tenant_id": "t1",
            "name": "Already Approved",
            "status": "approved",  # Not pending!
        })

        with patch("api.property_admin_router._get_supabase_client", return_value=mock_db):
            resp = client.post("/admin/properties/p-already/approve", headers=auth)

        assert resp.status_code == 409

    def test_onboard_to_approval_pipeline(self, client):
        """Full pipeline: issue onboard token → submit property → approve."""
        from services.access_token_service import issue_access_token, TokenType
        raw_token, _ = issue_access_token(TokenType.ONBOARD, "t1", "owner@test.com", 3600)

        # Step 1: Submit via onboard (creates pending_review property)
        mock_db_onboard = MagicMock()
        mock_select = MagicMock()
        mock_select.data = [{
            "id": "tok-pipeline", "token_type": "onboard", "entity_id": "t1",
            "email": "owner@test.com", "used_at": None, "revoked_at": None,
            "metadata": {}, "expires_at": "2026-03-20",
        }]
        mock_db_onboard.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = mock_select
        mock_db_onboard.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_prop_result = MagicMock()
        mock_prop_result.data = [{"property_id": "p-pipeline", "name": "Pipeline Villa"}]
        mock_db_onboard.table.return_value.insert.return_value.execute.return_value = mock_prop_result

        with patch("api.onboard_token_router._get_db", return_value=mock_db_onboard):
            submit_resp = client.post("/onboard/submit", json={
                "token": raw_token,
                "property_name": "Pipeline Villa",
                "property_type": "villa",
                "address": "456 Pipeline St",
                "capacity": "8",
                "contact_name": "Pipeline Owner",
                "contact_phone": "+1 555 0404",
            })

        assert submit_resp.status_code == 201
        assert submit_resp.json()["status"] == "submitted"

        # Step 2: Admin approves the submitted property
        login_resp = client.post("/auth/token", json={"tenant_id": "t1", "secret": "dev"})
        auth = {"Authorization": f"Bearer {login_resp.json()['token']}"}

        mock_db_approve = _make_property_db({
            "property_id": "p-pipeline",
            "tenant_id": "t1",
            "name": "Pipeline Villa",
            "status": "pending",  # pending from onboard submit
        }, channel_map_exists=False)

        with patch("api.property_admin_router._get_supabase_client", return_value=mock_db_approve):
            approve_resp = client.post("/admin/properties/p-pipeline/approve", headers=auth)

        assert approve_resp.status_code == 200
        body = approve_resp.json()
        assert body["status"] == "approved"
        assert body.get("channel_map_provisioned") is True
