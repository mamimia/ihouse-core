"""
Contract tests — Phase 298: Guest Portal + Owner Portal Real Auth
=================================================================

Covers:
- guest_token.py: issue_guest_token, verify_guest_token, hmac signing
- guest_token.py: record_guest_token, is_guest_token_revoked
- guest_token.py: get_owner_properties, grant_owner_access, has_owner_access
- guest_token_router: POST /admin/guest-token, POST /guest/verify-token
- owner_portal_router: GET /owner/portal, GET /owner/portal/{id}/summary,
                POST /admin/owner-access, DELETE /admin/owner-access/{oid}/{pid}
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("IHOUSE_JWT_SECRET", "test-secret-hs256-key-ok")
os.environ.setdefault("IHOUSE_GUEST_TOKEN_SECRET", "test-guest-secret-hs256")
os.environ.setdefault("SUPABASE_URL", "http://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")


# ---------------------------------------------------------------------------
# guest_token.py service tests
# ---------------------------------------------------------------------------

class TestHashToken:
    def test_deterministic(self):
        from services.guest_token import _hash_token
        assert _hash_token("abc") == _hash_token("abc")

    def test_different_inputs(self):
        from services.guest_token import _hash_token
        assert _hash_token("a") != _hash_token("b")

    def test_64_hex_chars(self):
        from services.guest_token import _hash_token
        assert len(_hash_token("x")) == 64


class TestIssueVerifyGuestToken:
    def test_issue_returns_token_and_exp(self):
        from services.guest_token import issue_guest_token
        token, exp = issue_guest_token("DEMO-001", "guest@example.com", ttl_seconds=3600)
        assert isinstance(token, str)
        assert len(token) > 10
        assert exp > int(time.time())

    def test_verify_valid_token(self):
        from services.guest_token import issue_guest_token, verify_guest_token
        token, _ = issue_guest_token("DEMO-001", "guest@example.com", ttl_seconds=3600)
        claims = verify_guest_token(token, "DEMO-001")
        assert claims is not None
        assert claims["booking_ref"] == "DEMO-001"
        assert claims["guest_email"] == "guest@example.com"

    def test_verify_wrong_booking_ref(self):
        from services.guest_token import issue_guest_token, verify_guest_token
        token, _ = issue_guest_token("DEMO-001", "", ttl_seconds=3600)
        result = verify_guest_token(token, "DIFFERENT-REF")
        assert result is None

    def test_verify_tampered_token(self):
        from services.guest_token import issue_guest_token, verify_guest_token
        token, _ = issue_guest_token("DEMO-001", "", ttl_seconds=3600)
        # Tamper: change last char of token
        tampered = token[:-1] + ("X" if token[-1] != "X" else "Y")
        result = verify_guest_token(tampered, "DEMO-001")
        assert result is None

    def test_verify_expired_token(self):
        from services.guest_token import issue_guest_token, verify_guest_token
        # Issue with negative TTL to force immediate expiry
        token, _ = issue_guest_token("DEMO-001", "", ttl_seconds=-1)
        result = verify_guest_token(token, "DEMO-001")
        assert result is None

    def test_verify_malformed_token(self):
        from services.guest_token import verify_guest_token
        result = verify_guest_token("not-a-valid-token", "DEMO-001")
        assert result is None

    def test_verify_empty_token(self):
        from services.guest_token import verify_guest_token
        result = verify_guest_token("", "DEMO-001")
        assert result is None

    def test_no_secret_raises(self):
        from services.guest_token import issue_guest_token
        old = os.environ.pop("IHOUSE_GUEST_TOKEN_SECRET", None)
        try:
            with pytest.raises(RuntimeError, match="IHOUSE_GUEST_TOKEN_SECRET"):
                issue_guest_token("X", "")
        finally:
            if old:
                os.environ["IHOUSE_GUEST_TOKEN_SECRET"] = old


class TestRecordGuestToken:
    def test_record_stores_hash(self):
        from services.guest_token import record_guest_token
        db = MagicMock()
        exp = int(time.time()) + 3600
        row = {"token_id": "t-1", "booking_ref": "B1", "expires_at": "2026-03-19T00:00:00Z"}
        db.table.return_value.insert.return_value.execute.return_value.data = [
            {**row, "token_hash": "xxx"}
        ]
        result = record_guest_token(db, "B1", "tenant-1", "raw-token", exp)
        assert "token_hash" not in result  # hash not returned
        assert result["token_id"] == "t-1"


class TestIsGuestTokenRevoked:
    def test_not_revoked(self):
        from services.guest_token import is_guest_token_revoked
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"revoked_at": None}
        ]
        assert is_guest_token_revoked(db, "some-token") is False

    def test_revoked(self):
        from services.guest_token import is_guest_token_revoked
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"revoked_at": "2026-03-12T00:00:00Z"}
        ]
        assert is_guest_token_revoked(db, "some-token") is True

    def test_not_found_returns_false(self):
        from services.guest_token import is_guest_token_revoked
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        assert is_guest_token_revoked(db, "unknown-token") is False


class TestGetOwnerProperties:
    def test_returns_properties(self):
        from services.guest_token import get_owner_properties
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.is_.return_value.execute.return_value.data = [
            {"property_id": "P1", "role": "owner", "granted_at": "2026-03-12T00:00:00Z"}
        ]
        result = get_owner_properties(db, "owner-1")
        assert len(result) == 1
        assert result[0]["property_id"] == "P1"

    def test_returns_empty_on_error(self):
        from services.guest_token import get_owner_properties
        db = MagicMock()
        db.table.side_effect = Exception("DB error")
        result = get_owner_properties(db, "owner-1")
        assert result == []


class TestGrantOwnerAccess:
    def test_grant_success(self):
        from services.guest_token import grant_owner_access
        db = MagicMock()
        row = {"id": "a-1", "owner_id": "o1", "property_id": "P1", "role": "owner"}
        db.table.return_value.insert.return_value.execute.return_value.data = [row]
        result = grant_owner_access(db, "operator", "o1", "P1", "owner")
        assert result["id"] == "a-1"

    def test_invalid_role_raises(self):
        from services.guest_token import grant_owner_access
        db = MagicMock()
        with pytest.raises(ValueError, match="Invalid role"):
            grant_owner_access(db, "op", "o1", "P1", "superowner")

    def test_duplicate_raises(self):
        from services.guest_token import grant_owner_access
        db = MagicMock()
        db.table.return_value.insert.return_value.execute.side_effect = Exception(
            "owner_portal_access_owner_id_property_id_key"
        )
        with pytest.raises(ValueError, match="already has access"):
            grant_owner_access(db, "op", "o1", "P1", "owner")


class TestHasOwnerAccess:
    def test_has_access(self):
        from services.guest_token import has_owner_access
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.eq.return_value.is_.return_value.execute.return_value.data = [
            {"id": "a-1"}
        ]
        assert has_owner_access(db, "o1", "P1") is True

    def test_no_access(self):
        from services.guest_token import has_owner_access
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.eq.return_value.is_.return_value.execute.return_value.data = []
        assert has_owner_access(db, "o1", "P1") is False

    def test_error_returns_false(self):
        from services.guest_token import has_owner_access
        db = MagicMock()
        db.table.side_effect = Exception("error")
        assert has_owner_access(db, "o1", "P1") is False


# ---------------------------------------------------------------------------
# Router tests — Guest Token Router
# ---------------------------------------------------------------------------

@pytest.fixture()
def guest_token_client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.guest_token_router import router
    _app = FastAPI()
    _app.include_router(router)
    return TestClient(_app)


@pytest.fixture()
def owner_portal_client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.owner_portal_router import router
    _app = FastAPI()
    _app.include_router(router)
    return TestClient(_app)


class TestGuestTokenRouterIssue:
    def test_issue_returns_201(self, guest_token_client):
        from services.guest_token import issue_guest_token, record_guest_token
        token, exp = issue_guest_token("B1", "g@eg.com", 3600)
        record_row = {"token_id": "t-1", "booking_ref": "B1",
                      "expires_at": "2026-03-19T00:00:00Z"}
        with patch("api.guest_token_router._get_db"), \
             patch("api.guest_token_router.issue_guest_token", return_value=(token, exp)), \
             patch("api.guest_token_router.record_guest_token", return_value=record_row):
            resp = guest_token_client.post(
                "/admin/guest-token/B1",
                json={"guest_email": "g@eg.com", "ttl_days": 7},
                headers={"Authorization": "Bearer dummy"},
            )
        assert resp.status_code == 201
        assert "token" in resp.json()

    def test_issue_no_secret_returns_503(self, guest_token_client):
        old = os.environ.pop("IHOUSE_GUEST_TOKEN_SECRET", None)
        try:
            resp = guest_token_client.post(
                "/admin/guest-token/B1",
                json={"ttl_days": 7},
                headers={"Authorization": "Bearer dummy"},
            )
            assert resp.status_code == 503
        finally:
            if old:
                os.environ["IHOUSE_GUEST_TOKEN_SECRET"] = old


class TestGuestTokenRouterVerify:
    def test_verify_valid_token(self, guest_token_client):
        claims = {"booking_ref": "B1", "guest_email": "g@eg.com", "exp": int(time.time()) + 3600}
        with patch("api.guest_token_router._get_db"), \
             patch("api.guest_token_router.verify_guest_token", return_value=claims), \
             patch("api.guest_token_router.is_guest_token_revoked", return_value=False):
            resp = guest_token_client.post(
                "/guest/verify-token",
                json={"token": "some-token", "booking_ref": "B1"},
            )
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    def test_verify_invalid_token_returns_401(self, guest_token_client):
        with patch("api.guest_token_router._get_db"), \
             patch("api.guest_token_router.verify_guest_token", return_value=None):
            resp = guest_token_client.post(
                "/guest/verify-token",
                json={"token": "bad-token", "booking_ref": "B1"},
            )
        assert resp.status_code == 401
        assert resp.json()["valid"] is False

    def test_verify_revoked_token_returns_401(self, guest_token_client):
        claims = {"booking_ref": "B1", "guest_email": "", "exp": int(time.time()) + 3600}
        with patch("api.guest_token_router._get_db"), \
             patch("api.guest_token_router.verify_guest_token", return_value=claims), \
             patch("api.guest_token_router.is_guest_token_revoked", return_value=True):
            resp = guest_token_client.post(
                "/guest/verify-token",
                json={"token": "revoked-token", "booking_ref": "B1"},
            )
        assert resp.status_code == 401
        assert "REVOKED" in resp.json()["error"]


class TestOwnerPortalRouterList:
    def test_list_properties(self, owner_portal_client):
        props = [{"property_id": "P1", "role": "owner", "granted_at": "2026-03-12T00:00:00Z"}]
        with patch("api.owner_portal_router._get_db"), \
             patch("api.owner_portal_router.get_owner_properties", return_value=props):
            resp = owner_portal_client.get(
                "/owner/portal",
                headers={"Authorization": "Bearer dummy"},
            )
        assert resp.status_code == 200
        assert resp.json()["count"] == 1

    def test_list_empty(self, owner_portal_client):
        with patch("api.owner_portal_router._get_db"), \
             patch("api.owner_portal_router.get_owner_properties", return_value=[]):
            resp = owner_portal_client.get(
                "/owner/portal",
                headers={"Authorization": "Bearer dummy"},
            )
        assert resp.status_code == 200
        assert resp.json()["count"] == 0


class TestOwnerPortalRouterSummary:
    def test_summary_no_access_returns_403(self, owner_portal_client):
        with patch("api.owner_portal_router._get_db"), \
             patch("api.owner_portal_router.has_owner_access", return_value=False):
            resp = owner_portal_client.get(
                "/owner/portal/P1/summary",
                headers={"Authorization": "Bearer dummy"},
            )
        assert resp.status_code == 403

    def test_summary_with_access(self, owner_portal_client):
        props = [{"property_id": "P1", "role": "owner"}]
        with patch("api.owner_portal_router._get_db") as mock_db_fn, \
             patch("api.owner_portal_router.has_owner_access", return_value=True), \
             patch("api.owner_portal_router.get_owner_properties", return_value=props):
            # Mock booking_state query
            db_mock = MagicMock()
            db_mock.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = []
            mock_db_fn.return_value = db_mock
            resp = owner_portal_client.get(
                "/owner/portal/P1/summary",
                headers={"Authorization": "Bearer dummy"},
            )
        assert resp.status_code == 200
        assert resp.json()["property_id"] == "P1"


class TestOwnerPortalRouterAdmin:
    def test_grant_access_201(self, owner_portal_client):
        row = {"id": "a-1", "owner_id": "o1", "property_id": "P1", "role": "owner"}
        with patch("api.owner_portal_router._get_db"), \
             patch("api.owner_portal_router.grant_owner_access", return_value=row):
            resp = owner_portal_client.post(
                "/admin/owner-access",
                json={"owner_id": "o1", "property_id": "P1", "role": "owner"},
                headers={"Authorization": "Bearer dummy"},
            )
        assert resp.status_code == 201

    def test_grant_duplicate_returns_422(self, owner_portal_client):
        with patch("api.owner_portal_router._get_db"), \
             patch("api.owner_portal_router.grant_owner_access",
                   side_effect=ValueError("already has access")):
            resp = owner_portal_client.post(
                "/admin/owner-access",
                json={"owner_id": "o1", "property_id": "P1", "role": "owner"},
                headers={"Authorization": "Bearer dummy"},
            )
        assert resp.status_code == 422

    def test_revoke_access(self, owner_portal_client):
        db_mock = MagicMock()
        db_mock.table.return_value.update.return_value.eq.return_value.eq.return_value.is_.return_value.execute.return_value.data = [
            {"id": "a-1"}
        ]
        with patch("api.owner_portal_router._get_db", return_value=db_mock):
            resp = owner_portal_client.delete(
                "/admin/owner-access/o1/P1",
                headers={"Authorization": "Bearer dummy"},
            )
        assert resp.status_code == 200
        assert resp.json()["revoked"] is True
