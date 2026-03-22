"""
Phase 862 P54 — Guest Portal Endpoint Integration Tests
=========================================================

HTTP-level tests through the FastAPI test client proving:
1. Valid test tokens → 200 response with data
2. Invalid tokens → 401 response
3. Token-gated chat endpoint works with valid token
4. Token-gated contact endpoint works with valid token
5. Deny path: expired/bad tokens are rejected at the endpoint level
"""

import os
os.environ.setdefault("IHOUSE_GUEST_TOKEN_SECRET", "test-secret-key-for-guest-tokens-v1-minimum-32-bytes")
os.environ.setdefault("IHOUSE_DEV_MODE", "true")

from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

import main

from services.guest_token import issue_guest_token


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _client() -> TestClient:
    return TestClient(main.app)


class _MockResult:
    def __init__(self, data=None):
        self.data = data or []


class _MockTable:
    def __init__(self, rows=None):
        self._rows = rows or []

    def select(self, *a, **kw):
        return self

    def eq(self, *a, **kw):
        return self

    def limit(self, *a):
        return self

    def order(self, *a, **kw):
        return self

    def insert(self, data):
        self._rows = [data] if isinstance(data, dict) else data
        return self

    def execute(self):
        return _MockResult(data=self._rows)


class _MockDB:
    def __init__(self, tables=None):
        self._tables = tables or {}

    def table(self, name):
        return self._tables.get(name, _MockTable())


# ---------------------------------------------------------------------------
# Allow path: valid test token
# ---------------------------------------------------------------------------

class TestGuestPortalAllow:
    """Tests with valid test tokens (test- prefix) — should return 200."""

    def test_guest_messages_valid_token(self):
        """POST /guest/{token}/messages with valid test token → 201."""
        db = _MockDB({"guest_chat_messages": _MockTable()})
        with patch("api.guest_portal_router._get_supabase_client", return_value=db):
            resp = _client().post(
                "/guest/test-ABCD1234/messages",
                json={"content": "Hello host!"},
            )
        assert resp.status_code == 201

    def test_guest_read_messages_valid_token(self):
        """GET /guest/{token}/messages with valid test token → 200."""
        db = _MockDB({"guest_chat_messages": _MockTable([
            {"id": "1", "content": "Hello", "sender_type": "guest", "created_at": "2026-01-01"},
        ])})
        with patch("api.guest_portal_router._get_supabase_client", return_value=db):
            resp = _client().get("/guest/test-XYZ99999/messages")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] >= 0

    def test_guest_contact_valid_token(self):
        """GET /guest/{token}/contact with valid test token → 200."""
        db = _MockDB({"properties": _MockTable([{
            "name": "Villa Test",
            "manager_phone": "+66891234567",
            "manager_email": "host@test.com",
            "manager_whatsapp": "+66891234567",
        }])})
        with patch("api.guest_portal_router._get_supabase_client", return_value=db):
            resp = _client().get("/guest/test-ABCD1234/contact")
        assert resp.status_code == 200
        body = resp.json()
        assert body["phone"] == "+66891234567"
        assert "wa.me" in body["whatsapp_link"]

    def test_guest_location_valid_token(self):
        """GET /guest/{token}/location with valid test token → 200."""
        db = _MockDB({"properties": _MockTable([{
            "name": "Villa Test",
            "address": "123 Beach Rd",
            "latitude": 13.75,
            "longitude": 100.50,
        }])})
        with patch("api.guest_portal_router._get_supabase_client", return_value=db):
            resp = _client().get("/guest/test-ABCD1234/location")
        assert resp.status_code == 200
        body = resp.json()
        assert body["latitude"] == 13.75
        assert "google.com/maps" in body["map_url"]

    def test_guest_house_info_valid_token(self):
        """GET /guest/{token}/house-info with valid test token → 200."""
        db = _MockDB({"properties": _MockTable([{
            "ac_instructions": "Remote on wall",
            "parking_info": "Slot B12",
        }])})
        with patch("api.guest_portal_router._get_supabase_client", return_value=db):
            resp = _client().get("/guest/test-ABCD1234/house-info")
        assert resp.status_code == 200
        body = resp.json()
        assert body["info"]["ac_instructions"] == "Remote on wall"

    def test_guest_i18n_valid_token(self):
        """GET /guest/{token}/portal-i18n with valid test token → 200."""
        resp = _client().get("/guest/test-ABCD1234/portal-i18n?lang=th")
        assert resp.status_code == 200
        body = resp.json()
        assert body["lang"] == "th"
        assert "labels" in body


# ---------------------------------------------------------------------------
# Deny path: invalid/expired tokens
# ---------------------------------------------------------------------------

class TestGuestPortalDeny:
    """Tests with invalid tokens — should return 401."""

    def test_messages_invalid_token(self):
        """POST /guest/bad-token/messages → 401."""
        resp = _client().post(
            "/guest/not-a-valid-token/messages",
            json={"content": "Hello"},
        )
        assert resp.status_code == 401

    def test_contact_invalid_token(self):
        """GET /guest/bad-token/contact → 401."""
        resp = _client().get("/guest/garbage-token/contact")
        assert resp.status_code == 401

    def test_location_invalid_token(self):
        """GET /guest/bad-token/location → 401."""
        resp = _client().get("/guest/xyz/location")
        assert resp.status_code == 401

    def test_house_info_invalid_token(self):
        """GET /guest/bad-token/house-info → 401."""
        resp = _client().get("/guest/no/house-info")
        assert resp.status_code == 401

    def test_i18n_invalid_token(self):
        """GET /guest/bad-token/portal-i18n → 401."""
        resp = _client().get("/guest/invalid/portal-i18n")
        assert resp.status_code == 401

    def test_messages_empty_content_still_validates_token_first(self):
        """POST with empty content but bad token → 401 (not 400)."""
        resp = _client().post(
            "/guest/nope/messages",
            json={"content": ""},
        )
        # Token check comes before content validation
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Guest extras deny path
# ---------------------------------------------------------------------------

class TestGuestExtrasDeny:
    """Tests that guest extras endpoints also enforce tokens."""

    def test_extras_listing_invalid_token(self):
        """GET /guest/bad-token/extras → 401."""
        resp = _client().get("/guest/invalid-tok/extras")
        assert resp.status_code == 401

    def test_extras_order_invalid_token(self):
        """POST /guest/bad-token/extras/order → 401."""
        resp = _client().post(
            "/guest/nope/extras/order",
            json={"extra_id": "e1", "quantity": 1},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Portal main endpoint (frontend's primary entrypoint)
# ---------------------------------------------------------------------------

class TestGuestPortalMain:
    """Tests for GET /guest/portal/{token} — the frontend's QR-link endpoint."""

    def test_portal_valid_test_token(self):
        """GET /guest/portal/test-ABCD1234 → 200 with property data."""
        resp = _client().get("/guest/portal/test-ABCD1234")
        assert resp.status_code == 200
        body = resp.json()
        # Fallback data (no DB in test mode)
        assert "property_name" in body
        assert body["check_in_time"] == "15:00"
        assert body["check_out_time"] == "11:00"

    def test_portal_invalid_token(self):
        """GET /guest/portal/garbage → 401."""
        resp = _client().get("/guest/portal/not-valid")
        assert resp.status_code == 401
        body = resp.json()
        assert body["error"] == "TOKEN_INVALID"

    def test_portal_empty_token(self):
        """GET /guest/portal/ → should resolve to 401 or 404 (not 500)."""
        resp = _client().get("/guest/portal/x")
        assert resp.status_code in (401, 404)

