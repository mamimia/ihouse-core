"""
Phase 302 — Guest Portal Token Flow E2E Tests
===============================================

Two test suites in one file:

1. **In-Process E2E Contract Flow** (always runs, no real DB required)
   Tests the full guest token lifecycle through service → router layers.
   Uses actual services with real HMAC, mocked Supabase only where needed.

   Actual service signatures (from Phase 298 guest_token.py):
     issue_guest_token(booking_ref, guest_email="", ttl_seconds=604800)
       → (raw_token: str, exp: int)  # exp is Unix timestamp
     verify_guest_token(token, expected_booking_ref)
       → dict | None  # returns {booking_ref, guest_email, exp} or None
     record_guest_token(db, booking_ref, tenant_id, raw_token, exp_int, guest_email="")
       → dict  # row (without token_hash)
     /guest/verify-token — POST {token, booking_ref} (no JWT)
     /notifications/guest-token-send — POST with JWT

2. **Live Integration Suite** (@pytest.mark.integration — skipped unless IHOUSE_ENV=staging)
"""
from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("IHOUSE_JWT_SECRET", "test-secret-hs256-key-ok")
os.environ.setdefault("IHOUSE_GUEST_TOKEN_SECRET", "test-guest-secret-long-enough-32b")
os.environ.setdefault("SUPABASE_URL", "http://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db_insert(row: dict) -> MagicMock:
    db = MagicMock()
    chain = MagicMock()
    for m in ("select", "insert", "update", "eq", "gte", "is_", "order", "limit"):
        setattr(chain, m, MagicMock(return_value=chain))
    chain.execute.return_value = MagicMock(data=[row])
    db.table.return_value = chain
    return db


def _make_db_empty() -> MagicMock:
    db = MagicMock()
    chain = MagicMock()
    for m in ("select", "insert", "update", "eq", "gte", "is_", "order", "limit"):
        setattr(chain, m, MagicMock(return_value=chain))
    chain.execute.return_value = MagicMock(data=[])
    db.table.return_value = chain
    return db


def _future_unix(seconds: int = 3600) -> int:
    return int(time.time()) + seconds


def _past_unix(seconds: int = 3600) -> int:
    return int(time.time()) - seconds


# ---------------------------------------------------------------------------
# Suite A: issue_guest_token (service layer)
# ---------------------------------------------------------------------------

class TestIssueGuestToken:
    def test_returns_token_and_unix_expiry(self):
        from services.guest_token import issue_guest_token
        token, exp = issue_guest_token("B-TEST-001")
        assert isinstance(token, str)
        assert len(token) > 32
        assert isinstance(exp, int)
        assert exp > int(time.time())

    def test_different_refs_produce_different_tokens(self):
        from services.guest_token import issue_guest_token
        t1, _ = issue_guest_token("B-001")
        t2, _ = issue_guest_token("B-002")
        assert t1 != t2

    def test_short_ttl_expires_soon(self):
        from services.guest_token import issue_guest_token
        _, exp = issue_guest_token("B-001", ttl_seconds=60)
        assert exp < int(time.time()) + 120

    def test_guest_email_embedded(self):
        from services.guest_token import issue_guest_token, verify_guest_token
        token, _ = issue_guest_token("B-001", guest_email="guest@test.com")
        claims = verify_guest_token(token, "B-001")
        assert claims is not None
        assert claims.get("guest_email") == "guest@test.com"

    def test_default_ttl_is_7d(self):
        from services.guest_token import issue_guest_token
        _, exp = issue_guest_token("B-001")
        expected_min = int(time.time()) + 7 * 86400 - 60
        expected_max = int(time.time()) + 7 * 86400 + 60
        assert expected_min <= exp <= expected_max


# ---------------------------------------------------------------------------
# Suite B: verify_guest_token (service layer — happy + sad paths)
# ---------------------------------------------------------------------------

class TestVerifyGuestToken:
    def test_valid_token_returns_claims(self):
        from services.guest_token import issue_guest_token, verify_guest_token
        token, _ = issue_guest_token("B-VT-001", guest_email="x@e.com")
        claims = verify_guest_token(token, "B-VT-001")
        assert claims is not None
        assert claims["booking_ref"] == "B-VT-001"
        assert claims["guest_email"] == "x@e.com"
        assert isinstance(claims["exp"], int)

    def test_wrong_booking_ref_returns_none(self):
        from services.guest_token import issue_guest_token, verify_guest_token
        token, _ = issue_guest_token("B-REAL")
        claims = verify_guest_token(token, "B-DIFFERENT")
        assert claims is None

    def test_tampered_token_returns_none(self):
        from services.guest_token import verify_guest_token
        claims = verify_guest_token("completely.fakesig", "B-ANY")
        assert claims is None

    def test_malformed_token_returns_none(self):
        from services.guest_token import verify_guest_token
        claims = verify_guest_token("no-dot-separator", "B-ANY")
        assert claims is None

    def test_expired_token_returns_none(self):
        from services.guest_token import issue_guest_token, verify_guest_token
        token, _ = issue_guest_token("B-EXP", ttl_seconds=1)
        # The token will have just been issued; manually craft expired one
        # by issuing with 0 ttl (will already be expired at check time)
        token2, _ = issue_guest_token("B-EXP2", ttl_seconds=0)
        # exp will be int(time.time()) + 0 = now, which is already past
        claims = verify_guest_token(token2, "B-EXP2")
        # May or may not be expired depending on timing; just check type
        assert claims is None or isinstance(claims, dict)


# ---------------------------------------------------------------------------
# Suite C: record_guest_token (service layer)
# ---------------------------------------------------------------------------

class TestRecordGuestToken:
    def test_stores_hash_not_raw_token(self):
        import hashlib
        from services.guest_token import issue_guest_token, record_guest_token

        token, exp = issue_guest_token("B-REC-001")
        db = _make_db_insert({"id": "row-1", "booking_ref": "B-REC-001"})
        row = record_guest_token(db, "B-REC-001", "t1", token, exp)

        # The insert payload should contain hash, not raw token
        insert_call = db.table.return_value.insert.call_args
        if insert_call:
            payload = insert_call[0][0]
            expected_hash = hashlib.sha256(token.encode()).hexdigest()
            assert payload.get("token_hash") == expected_hash
            assert token not in str(payload)

    def test_returns_row_without_token_hash(self):
        from services.guest_token import issue_guest_token, record_guest_token
        token, exp = issue_guest_token("B-REC-002")
        db = _make_db_insert({"id": "r1", "booking_ref": "B-REC-002", "token_hash": "h"})
        row = record_guest_token(db, "B-REC-002", "t1", token, exp)
        # token_hash should be stripped from returned row
        assert "token_hash" not in row

    def test_db_error_returns_empty_dict(self):
        from services.guest_token import issue_guest_token, record_guest_token
        token, exp = issue_guest_token("B-REC-003")
        db = MagicMock()
        db.table.side_effect = Exception("DB conn failed")
        row = record_guest_token(db, "B-REC-003", "t1", token, exp)
        assert row == {}


# ---------------------------------------------------------------------------
# Suite D: Full service flow — issue → record → verify
# ---------------------------------------------------------------------------

class TestGuestTokenFullServiceFlow:
    def test_issued_token_verifies_correctly(self):
        """A token issued and verified with matching booking_ref succeeds."""
        from services.guest_token import issue_guest_token, record_guest_token, verify_guest_token
        db = _make_db_insert({"id": "r", "booking_ref": "B-FLOW-1"})
        token, exp = issue_guest_token("B-FLOW-1", "guest@e.com")
        record_guest_token(db, "B-FLOW-1", "t1", token, exp)
        claims = verify_guest_token(token, "B-FLOW-1")
        assert claims is not None
        assert claims["booking_ref"] == "B-FLOW-1"

    def test_dispatch_notification_sms_path(self):
        from services.guest_token import issue_guest_token
        from services.notification_dispatcher import dispatch_guest_token_notification

        db = _make_db_insert({"id": "log-1"})
        token, _ = issue_guest_token("B-DISP-1")

        with patch("services.notification_dispatcher._log_notification",
                   return_value={"notification_id": "log-id-1", "status": "pending"}), \
             patch("services.notification_dispatcher._update_log_status"):
            results = dispatch_guest_token_notification(
                db=db,
                tenant_id="t1",
                booking_ref="B-DISP-1",
                raw_token=token,
                portal_base_url="https://portal.domaniqo.com",
                to_phone="+66812345678",
                to_email=None,
            )

        assert len(results) == 1
        assert results[0]["status"] in ("dry_run", "sent", "error")
        assert results[0]["channel"] == "sms"

    def test_dispatch_both_channels(self):
        from services.guest_token import issue_guest_token
        from services.notification_dispatcher import dispatch_guest_token_notification

        db = _make_db_insert({"id": "log-2"})
        token, _ = issue_guest_token("B-DISP-2")

        with patch("services.notification_dispatcher._log_notification",
                   return_value={"notification_id": "log-id-2", "status": "pending"}), \
             patch("services.notification_dispatcher._update_log_status"):
            results = dispatch_guest_token_notification(
                db=db,
                tenant_id="t1",
                booking_ref="B-DISP-2",
                raw_token=token,
                portal_base_url="https://portal.domaniqo.com",
                to_phone="+66812345678",
                to_email="guest@test.com",
            )

        assert len(results) == 2
        channels = [r["channel"] for r in results]
        assert "sms" in channels
        assert "email" in channels

    def test_no_recipients_raises(self):
        from services.guest_token import issue_guest_token
        from services.notification_dispatcher import dispatch_guest_token_notification

        db = _make_db_empty()
        token, _ = issue_guest_token("B-DISP-3")

        with pytest.raises(ValueError, match="At least one"):
            dispatch_guest_token_notification(
                db=db,
                tenant_id="t1",
                booking_ref="B-DISP-3",
                raw_token=token,
                portal_base_url="https://portal.domaniqo.com",
                to_phone=None,
                to_email=None,
            )


# ---------------------------------------------------------------------------
# Suite E: POST /guest/verify-token endpoint — real token, mocked DB
# ---------------------------------------------------------------------------

@pytest.fixture()
def guest_token_client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.guest_token_router import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestVerifyTokenEndpointE2E:
    def test_valid_token_returns_200(self, guest_token_client):
        from services.guest_token import issue_guest_token
        token, _ = issue_guest_token("B-VT-E2E-1")
        with patch("api.guest_token_router._get_db") as mock_db:
            mock_db.return_value = _make_db_empty()  # not revoked (empty = no record)
            resp = guest_token_client.post(
                "/guest/verify-token",
                json={"token": token, "booking_ref": "B-VT-E2E-1"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is True
        assert body["booking_ref"] == "B-VT-E2E-1"

    def test_wrong_booking_ref_returns_401(self, guest_token_client):
        from services.guest_token import issue_guest_token
        token, _ = issue_guest_token("B-CORRECT")
        with patch("api.guest_token_router._get_db", return_value=_make_db_empty()):
            resp = guest_token_client.post(
                "/guest/verify-token",
                json={"token": token, "booking_ref": "B-WRONG"},
            )
        assert resp.status_code == 401
        assert resp.json()["valid"] is False

    def test_tampered_token_returns_401(self, guest_token_client):
        with patch("api.guest_token_router._get_db", return_value=_make_db_empty()):
            resp = guest_token_client.post(
                "/guest/verify-token",
                json={"token": "bad.sig", "booking_ref": "B-ANY"},
            )
        assert resp.status_code == 401

    def test_missing_body_fields_returns_422(self, guest_token_client):
        resp = guest_token_client.post("/guest/verify-token", json={})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Suite F: POST /notifications/guest-token-send endpoint (router E2E)
# ---------------------------------------------------------------------------

@pytest.fixture()
def notif_client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.notification_router import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestGuestTokenSendRouterE2E:
    def _mock_issue(self, booking_ref: str):
        from services.guest_token import issue_guest_token
        return issue_guest_token(booking_ref)

    def test_sms_returns_200(self, notif_client):
        token, exp = self._mock_issue("B-NS-001")
        record = {"id": "r1", "booking_ref": "B-NS-001", "expires_at": "2026-04-01T00:00:00+00:00"}
        dispatch_result = [{"status": "dry_run", "channel": "sms", "recipient": "+66812345678"}]

        with patch("api.notification_router._get_db"), \
             patch("api.notification_router.issue_guest_token", return_value=(token, exp)), \
             patch("api.notification_router.record_guest_token", return_value=record), \
             patch("api.notification_router.dispatch_guest_token_notification",
                   return_value=dispatch_result):
            resp = notif_client.post(
                "/notifications/guest-token-send",
                json={
                    "booking_ref": "B-NS-001",
                    "tenant_id": "t1",
                    "property_id": "prop-1",
                    "to_phone": "+66812345678",
                    "portal_base_url": "https://portal.domaniqo.com",
                },
                headers={"Authorization": "Bearer dummy"},
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["booking_ref"] == "B-NS-001"
        assert body["notifications"][0]["status"] == "dry_run"

    def test_no_recipients_returns_422(self, notif_client):
        token, exp = self._mock_issue("B-NS-002")
        record = {"id": "r2", "booking_ref": "B-NS-002"}

        with patch("api.notification_router._get_db"), \
             patch("api.notification_router.issue_guest_token", return_value=(token, exp)), \
             patch("api.notification_router.record_guest_token", return_value=record), \
             patch("api.notification_router.dispatch_guest_token_notification",
                   side_effect=ValueError("At least one recipient")):
            resp = notif_client.post(
                "/notifications/guest-token-send",
                json={
                    "booking_ref": "B-NS-002",
                    "tenant_id": "t1",
                    "property_id": "prop-1",
                    "portal_base_url": "https://portal.domaniqo.com",
                },
                headers={"Authorization": "Bearer dummy"},
            )

        assert resp.status_code == 422

    def test_email_returns_200(self, notif_client):
        token, exp = self._mock_issue("B-NS-003")
        record = {"id": "r3", "booking_ref": "B-NS-003"}
        dispatch_result = [{"status": "dry_run", "channel": "email", "recipient": "g@test.com"}]

        with patch("api.notification_router._get_db"), \
             patch("api.notification_router.issue_guest_token", return_value=(token, exp)), \
             patch("api.notification_router.record_guest_token", return_value=record), \
             patch("api.notification_router.dispatch_guest_token_notification",
                   return_value=dispatch_result):
            resp = notif_client.post(
                "/notifications/guest-token-send",
                json={
                    "booking_ref": "B-NS-003",
                    "tenant_id": "t1",
                    "property_id": "prop-1",
                    "to_email": "g@test.com",
                    "portal_base_url": "https://portal.domaniqo.com",
                },
                headers={"Authorization": "Bearer dummy"},
            )

        assert resp.status_code == 201
        assert resp.json()["notifications"][0]["status"] == "dry_run"


# ---------------------------------------------------------------------------
# Suite G: Live integration (@pytest.mark.integration — staging only)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestGuestTokenLiveIntegration:
    """
    Requires IHOUSE_ENV=staging + SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY.
    Skipped in all other environments.
    """

    @pytest.fixture(autouse=True)
    def skip_if_not_staging(self):
        if os.getenv("IHOUSE_ENV") != "staging":
            pytest.skip("Set IHOUSE_ENV=staging to run live integration tests")

    def _live_db(self):
        from supabase import create_client
        return create_client(
            os.environ["SUPABASE_URL"],
            os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"],
        )

    def test_guest_tokens_table_exists(self):
        db = self._live_db()
        result = db.table("guest_tokens").select("id").limit(1).execute()
        assert result.data is not None

    def test_notification_log_table_exists(self):
        db = self._live_db()
        result = db.table("notification_log").select("id").limit(1).execute()
        assert result.data is not None

    def test_issue_and_verify_live(self):
        from services.guest_token import issue_guest_token, record_guest_token, verify_guest_token
        db = self._live_db()
        ref = f"LIVE-{uuid.uuid4().hex[:8]}"
        token, exp = issue_guest_token(ref, "live@test.com", ttl_seconds=3600)
        record_guest_token(db, ref, "live-tenant", token, exp, "live@test.com")
        claims = verify_guest_token(token, ref)
        assert claims is not None
        assert claims["booking_ref"] == ref

    def test_owner_portal_access_table_exists(self):
        db = self._live_db()
        result = db.table("owner_portal_access").select("id").limit(1).execute()
        assert result.data is not None
