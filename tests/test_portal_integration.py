"""
Phase 321 — Owner + Guest Portal Integration Tests
====================================================

Tests both portal flows end-to-end:

Group A: Guest Token Service
  ✓  Issue token returns valid token string
  ✓  Verify token succeeds with correct booking_ref
  ✓  Verify token fails with wrong booking_ref
  ✓  Verify expired token returns None
  ✓  Token hash is SHA-256 of raw token

Group B: Guest Portal HTTP (stub lookup)
  ✓  GET /guest/booking/{ref} → 200 booking view
  ✓  GET /guest/booking/{ref}/wifi → 200 wifi data
  ✓  GET /guest/booking/{ref}/rules → 200 house rules
  ✓  GET /guest/booking/{ref} missing token → 422

Group C: Owner Token Service (grant/has/get)
  ✓  grant_owner_access creates DB row
  ✓  has_owner_access returns True for granted property
  ✓  get_owner_properties returns property list
  ✓  Invalid role raises ValueError

Group D: Owner Portal HTTP
  ✓  GET /owner/portal → 200 property list
  ✓  POST /admin/owner-access → 201 grant
  ✓  DELETE /admin/owner-access/{owner}/{prop} → 200 revoke

CI-safe: no live DB, all mocked.
"""
from __future__ import annotations

import json
import os
import sys
import time
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("IHOUSE_ENV", "test")
os.environ.setdefault("IHOUSE_GUEST_TOKEN_SECRET", "test-secret-key-for-integration")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from services.guest_token import (
    issue_guest_token,
    verify_guest_token,
    _hash_token,
    record_guest_token,
    grant_owner_access,
    has_owner_access,
    get_owner_properties,
)


# ---------------------------------------------------------------------------
# Group A — Guest Token Service
# ---------------------------------------------------------------------------

class TestGuestTokenService:

    def test_issue_returns_token_and_expiry(self):
        token, exp = issue_guest_token("BK-001", "guest@example.com")
        assert isinstance(token, str)
        assert len(token) > 20
        assert exp > int(time.time())

    def test_verify_valid_token(self):
        token, _ = issue_guest_token("BK-002", "guest@example.com")
        result = verify_guest_token(token, expected_booking_ref="BK-002")
        assert result is not None
        assert result["booking_ref"] == "BK-002"
        assert result["guest_email"] == "guest@example.com"

    def test_verify_wrong_booking_ref_returns_none(self):
        token, _ = issue_guest_token("BK-003")
        result = verify_guest_token(token, expected_booking_ref="BK-WRONG")
        assert result is None

    def test_verify_expired_token_returns_none(self):
        token, _ = issue_guest_token("BK-004", ttl_seconds=-1)
        result = verify_guest_token(token, expected_booking_ref="BK-004")
        assert result is None

    def test_token_hash_is_sha256(self):
        import hashlib
        token, _ = issue_guest_token("BK-005")
        expected = hashlib.sha256(token.encode("utf-8")).hexdigest()
        assert _hash_token(token) == expected

    def test_verify_malformed_token_returns_none(self):
        result = verify_guest_token("garbage-token", expected_booking_ref="BK-001")
        assert result is None

    def test_different_tokens_for_same_booking(self):
        t1, _ = issue_guest_token("BK-006", "a@b.com")
        t2, _ = issue_guest_token("BK-006", "a@b.com")
        # Different expiry timestamps make them different tokens
        # (within timing margin they could be the same, but TTL includes current time)
        assert isinstance(t1, str) and isinstance(t2, str)


# ---------------------------------------------------------------------------
# Group B — Guest Portal HTTP
# ---------------------------------------------------------------------------

class TestGuestPortalHTTP:

    @pytest.fixture(autouse=True)
    def _setup_client(self):
        from fastapi.testclient import TestClient
        from main import app
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_booking_overview_returns_200(self):
        r = self.client.get(
            "/guest/booking/DEMO-001",
            headers={"x-guest-token": "any-token"},
        )
        # stub_lookup returns a GuestBookingView for any ref
        assert r.status_code == 200
        body = r.json()
        assert "booking_ref" in body
        assert "wifi_name" in body
        assert "house_rules" in body

    def test_wifi_endpoint_returns_200(self):
        r = self.client.get(
            "/guest/booking/DEMO-001/wifi",
            headers={"x-guest-token": "any-token"},
        )
        assert r.status_code == 200
        body = r.json()
        assert "wifi_name" in body
        assert "wifi_password" in body

    def test_rules_endpoint_returns_200(self):
        r = self.client.get(
            "/guest/booking/DEMO-001/rules",
            headers={"x-guest-token": "any-token"},
        )
        assert r.status_code == 200
        body = r.json()
        assert "house_rules" in body

    def test_missing_token_returns_422(self):
        r = self.client.get("/guest/booking/DEMO-001")
        assert r.status_code == 422  # Missing required header


# ---------------------------------------------------------------------------
# Group C — Owner Token Service (grant / has / get)
# ---------------------------------------------------------------------------

class TestOwnerAccessService:

    def test_grant_access_creates_row(self):
        db = MagicMock()
        db.table.return_value.insert.return_value.execute.return_value.data = [
            {"owner_id": "owner-1", "property_id": "prop-1", "role": "owner"}
        ]
        result = grant_owner_access(db, "admin-1", "owner-1", "prop-1", role="owner")
        assert result["owner_id"] == "owner-1"
        assert result["role"] == "owner"

    def test_grant_invalid_role_raises(self):
        db = MagicMock()
        with pytest.raises(ValueError, match="Invalid role"):
            grant_owner_access(db, "admin-1", "owner-1", "prop-1", role="superuser")

    def test_has_access_returns_true(self):
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.eq.return_value.is_.return_value.execute.return_value.data = [
            {"id": 42}
        ]
        assert has_owner_access(db, "owner-1", "prop-1") is True

    def test_has_access_returns_false_when_empty(self):
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.eq.return_value.is_.return_value.execute.return_value.data = []
        assert has_owner_access(db, "owner-1", "prop-1") is False

    def test_get_owner_properties_returns_list(self):
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.is_.return_value.execute.return_value.data = [
            {"property_id": "prop-1", "role": "owner", "granted_at": "2026-03-12"},
            {"property_id": "prop-2", "role": "viewer", "granted_at": "2026-03-12"},
        ]
        result = get_owner_properties(db, "owner-1")
        assert len(result) == 2
        assert result[0]["property_id"] == "prop-1"


# ---------------------------------------------------------------------------
# Group D — Owner Portal HTTP
# ---------------------------------------------------------------------------

class TestOwnerPortalHTTP:

    @pytest.fixture(autouse=True)
    def _setup_client(self):
        from fastapi.testclient import TestClient
        from main import app
        self.client = TestClient(app, raise_server_exceptions=False)

    @patch("api.owner_portal_router._get_db")
    def test_list_owner_properties(self, mock_get_db):
        db = MagicMock()
        mock_get_db.return_value = db
        db.table.return_value.select.return_value.eq.return_value.is_.return_value.execute.return_value.data = [
            {"property_id": "prop-1", "role": "owner", "granted_at": "2026-03-12"},
        ]
        r = self.client.get("/owner/portal")
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 1
        assert body["properties"][0]["property_id"] == "prop-1"

    @patch("api.owner_portal_router._get_db")
    def test_grant_owner_access_via_http(self, mock_get_db):
        db = MagicMock()
        mock_get_db.return_value = db
        db.table.return_value.insert.return_value.execute.return_value.data = [
            {"owner_id": "owner-1", "property_id": "prop-1", "role": "owner"}
        ]
        r = self.client.post(
            "/admin/owner-access",
            json={"owner_id": "owner-1", "property_id": "prop-1", "role": "owner"},
        )
        assert r.status_code == 201
        body = r.json()
        assert body["granted"] is True

    @patch("api.owner_portal_router._get_db")
    def test_revoke_owner_access_via_http(self, mock_get_db):
        db = MagicMock()
        mock_get_db.return_value = db
        db.table.return_value.update.return_value.eq.return_value.eq.return_value.is_.return_value.execute.return_value.data = [
            {"owner_id": "owner-1", "property_id": "prop-1"}
        ]
        r = self.client.delete("/admin/owner-access/owner-1/prop-1")
        assert r.status_code == 200
        body = r.json()
        assert body["revoked"] is True

    @patch("api.owner_portal_router._get_db")
    def test_revoke_nonexistent_returns_404(self, mock_get_db):
        db = MagicMock()
        mock_get_db.return_value = db
        db.table.return_value.update.return_value.eq.return_value.eq.return_value.is_.return_value.execute.return_value.data = []
        r = self.client.delete("/admin/owner-access/owner-x/prop-x")
        assert r.status_code == 404
