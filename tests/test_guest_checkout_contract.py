"""
Phase 1045 — Guest Checkout Router — Contract Tests
=====================================================

Tests for:
  1. TokenType.GUEST_CHECKOUT exists and round-trips correctly
  2. POST /bookings/{id}/guest-checkout-token — JWT auth, role guard, token issued
  3. GET  /guest-checkout/{token}             — resolves portal state, marks initiated_at
  4. POST /guest-checkout/{token}/step/{key}  — records step completion, idempotent
  5. POST /guest-checkout/{token}/complete    — requires required steps, writes confirmed_at, idempotent
  6. Revoked token path — rejected at portal level
  7. Unknown step rejected
  8. complete without required steps rejected
  9. _compute_token_ttl — booking-date-anchored TTL (three paths: effective_at, date, fallback)
"""
from __future__ import annotations

import asyncio
import time
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("IHOUSE_JWT_SECRET",             "test-secret-for-checkout-1045")
    monkeypatch.setenv("IHOUSE_ACCESS_TOKEN_SECRET",    "access-token-secret-32-bytes-ok")
    monkeypatch.setenv("IHOUSE_DEV_MODE",               "true")
    monkeypatch.setenv("SUPABASE_URL",                  "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY",     "test-service-role-key")
    monkeypatch.setenv("NEXT_PUBLIC_SITE_URL",          "https://app.test.example")


# ---------------------------------------------------------------------------
# Helper: build a valid GUEST_CHECKOUT token
# ---------------------------------------------------------------------------

def _make_token(booking_id: str = "booking-abc-123", ttl: int = 3600):
    from services.access_token_service import TokenType, issue_access_token
    raw_token, exp = issue_access_token(
        token_type=TokenType.GUEST_CHECKOUT,
        entity_id=booking_id,
        ttl_seconds=ttl,
    )
    return raw_token, exp


def _make_booking_row(
    booking_id: str = "booking-abc-123",
    tenant_id: str = "tenant-x",
    property_id: str = "KPG-500",
    status: str = "confirmed",
    steps: dict | None = None,
    confirmed_at=None,
    initiated_at=None,
    early_checkout_approved=False,
    early_checkout_date=None,
) -> dict:
    return {
        "booking_id":                    booking_id,
        "tenant_id":                     tenant_id,
        "property_id":                   property_id,
        "status":                        status,
        "guest_name":                    "Test Guest",
        "guest_id":                      None,
        "check_in":                      "2026-04-01",
        "check_out":                     "2026-04-05",
        "checked_out_at":                None,
        "early_checkout_approved":       early_checkout_approved,
        "early_checkout_date":           early_checkout_date,
        "early_checkout_effective_at":   None,
        "early_checkout_status":         None,
        "guest_checkout_initiated_at":   initiated_at,
        "guest_checkout_confirmed_at":   confirmed_at,
        "guest_checkout_steps_completed": steps or {},
        "guest_checkout_token_hash":     None,
    }


def _make_property_row(property_id: str = "KPG-500", tenant_id: str = "tenant-x") -> dict:
    return {
        "property_id":       property_id,
        "display_name":      "Emuna Villa",
        "name":              "Emuna Villa",
        "address":           "123 Test St",
        "city":              "Phuket",
        "country":           "TH",
        "checkout_time":     "11:00",
        "emergency_contact": "+66-800-000",
        "wifi_name":         "TestWifi",
        "wifi_password":     "testpassword",
    }


def _stub_db(booking_row: dict, property_row: dict | None = None, access_token_revoked: bool = False):
    """Build a mock Supabase client for portal endpoint tests."""
    db = MagicMock()
    _prop = property_row or _make_property_row()

    def _table(table_name):
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.limit.return_value = chain
        chain.update.return_value = chain
        chain.insert.return_value = chain

        if table_name == "booking_state":
            chain.execute.return_value = MagicMock(data=[booking_row])
        elif table_name == "properties":
            chain.execute.return_value = MagicMock(data=[_prop])
        elif table_name == "access_tokens":
            revoked_at = "2026-04-02T10:00:00Z" if access_token_revoked else None
            chain.execute.return_value = MagicMock(data=[{"id": "tok-1", "revoked_at": revoked_at}])
        elif table_name == "audit_events":
            chain.execute.return_value = MagicMock(data=[{}])
        else:
            chain.execute.return_value = MagicMock(data=[])

        return chain

    db.table.side_effect = _table
    return db


# ===========================================================================
# 1. TokenType.GUEST_CHECKOUT exists and round-trips
# ===========================================================================

class TestGuestCheckoutTokenType:
    def test_token_type_exists(self):
        from services.access_token_service import TokenType
        assert hasattr(TokenType, "GUEST_CHECKOUT")
        assert TokenType.GUEST_CHECKOUT.value == "guest_checkout"

    def test_token_issue_and_verify(self):
        from services.access_token_service import TokenType, issue_access_token, verify_access_token
        raw_token, exp = issue_access_token(TokenType.GUEST_CHECKOUT, "booking-xyz")
        assert raw_token
        assert exp > int(time.time())

        claims = verify_access_token(raw_token, expected_type=TokenType.GUEST_CHECKOUT)
        assert claims is not None
        assert claims["token_type"] == "guest_checkout"
        assert claims["entity_id"] == "booking-xyz"

    def test_wrong_type_rejected(self):
        from services.access_token_service import TokenType, issue_access_token, verify_access_token
        raw_token, _ = issue_access_token(TokenType.SELF_CHECKIN, "booking-xyz")
        claims = verify_access_token(raw_token, expected_type=TokenType.GUEST_CHECKOUT)
        assert claims is None

    def test_expired_token_rejected(self):
        from services.access_token_service import TokenType, issue_access_token, verify_access_token
        # ttl_seconds=-1 creates token with exp = now - 1 → immediately expired
        raw_token, _ = issue_access_token(TokenType.GUEST_CHECKOUT, "booking-xyz", ttl_seconds=-1)
        claims = verify_access_token(raw_token, expected_type=TokenType.GUEST_CHECKOUT)
        assert claims is None


# ===========================================================================
# 9. _compute_token_ttl — booking-date-anchored TTL
# ===========================================================================

class TestComputeTokenTTL:
    """
    _compute_token_ttl() must derive TTL from the booking's effective checkout
    time, not a flat constant.

    Three resolution paths (in priority order):
      1. early_checkout_effective_at (precise TIMESTAMPTZ) → expires eff_at + 4h
      2. date fallback (early_checkout_date or check_out at 11:00 UTC) → + 4h
      3. no date data → fallback constant (24h)
    """

    def test_ttl_uses_early_checkout_effective_at(self):
        """Path 1: precise effective_at → TTL anchored to that moment + 4h."""
        from datetime import datetime, timezone, timedelta
        from api.guest_checkout_router import _compute_token_ttl

        # Effective checkout 6 hours from now with 4h grace = ~10h from now
        eff = datetime.now(tz=timezone.utc) + timedelta(hours=6)
        booking = {
            "early_checkout_approved": True,
            "early_checkout_effective_at": eff.isoformat(),
            "early_checkout_date": None,
            "check_out": "2026-04-05",
        }
        ttl = _compute_token_ttl(booking)
        # Should be approximately 6h (eff) + 4h (grace) = 10h = 36000s
        # Allow ±30s for test execution time
        assert 36000 - 30 <= ttl <= 36000 + 30, f"Expected ~36000s, got {ttl}"

    def test_ttl_uses_checkout_date_when_no_effective_at(self):
        """Path 2: regular checkout on a future date → TTL to that date at 11:00 UTC + 4h."""
        from datetime import datetime, timezone, timedelta, date as date_type
        from api.guest_checkout_router import _compute_token_ttl

        # Checkout tomorrow
        tomorrow = (datetime.now(tz=timezone.utc) + timedelta(days=1)).date()
        booking = {
            "early_checkout_approved": False,
            "early_checkout_effective_at": None,
            "early_checkout_date": None,
            "check_out": tomorrow.isoformat(),
        }
        now = datetime.now(tz=timezone.utc)
        target = datetime(tomorrow.year, tomorrow.month, tomorrow.day,
                          11, 0, 0, tzinfo=timezone.utc) + timedelta(hours=4)
        expected = int((target - now).total_seconds())

        ttl = _compute_token_ttl(booking)
        assert abs(ttl - expected) <= 5, f"Expected ~{expected}s, got {ttl}"

    def test_ttl_uses_early_checkout_date_when_approved_but_no_effective_at(self):
        """Path 2 (early): early date is used when approved but no precise TIMESTAMPTZ."""
        from datetime import datetime, timezone, timedelta
        from api.guest_checkout_router import _compute_token_ttl

        in_two_days = (datetime.now(tz=timezone.utc) + timedelta(days=2)).date()
        booking = {
            "early_checkout_approved": True,
            "early_checkout_effective_at": None,   # no precise time
            "early_checkout_date": in_two_days.isoformat(),
            "check_out": "2026-04-10",             # original, should be ignored
        }
        now = datetime.now(tz=timezone.utc)
        target = datetime(in_two_days.year, in_two_days.month, in_two_days.day,
                          11, 0, 0, tzinfo=timezone.utc) + timedelta(hours=4)
        expected = int((target - now).total_seconds())

        ttl = _compute_token_ttl(booking)
        assert abs(ttl - expected) <= 5, f"Expected ~{expected}s, got {ttl}"

    def test_ttl_minimum_floor_when_checkout_already_past(self):
        """
        If checkout + grace is already in the past (e.g. staff sends token late),
        TTL must not be zero or negative — floor is 1 hour.
        """
        from api.guest_checkout_router import _compute_token_ttl

        booking = {
            "early_checkout_approved": False,
            "early_checkout_effective_at": None,
            "early_checkout_date": None,
            "check_out": "2020-01-01",  # well in the past
        }
        ttl = _compute_token_ttl(booking)
        assert ttl >= 3600, f"Expected at least 3600s floor, got {ttl}"

    def test_ttl_fallback_when_no_date_data(self):
        """Path 3: no date data at all → 24h fallback constant."""
        from api.guest_checkout_router import _compute_token_ttl, _TOKEN_TTL_FALLBACK_SECONDS

        booking = {
            "early_checkout_approved": False,
            "early_checkout_effective_at": None,
            "early_checkout_date": None,
            "check_out": None,
            "booking_id": "test-fallback",
        }
        ttl = _compute_token_ttl(booking)
        assert ttl == _TOKEN_TTL_FALLBACK_SECONDS


# ===========================================================================
# 2. POST /bookings/{id}/guest-checkout-token
# ===========================================================================

class TestGenerateGuestCheckoutToken:
    def _make_db_for_generate(self, booking_row: dict):
        db = MagicMock()

        mock_bs = MagicMock()
        mock_bs.select.return_value = mock_bs
        mock_bs.eq.return_value = mock_bs
        mock_bs.limit.return_value = mock_bs
        mock_bs.update.return_value = mock_bs
        mock_bs.execute.return_value = MagicMock(data=[booking_row])

        mock_at = MagicMock()
        mock_at.insert.return_value = mock_at
        mock_at.execute.return_value = MagicMock(data=[{"id": "at-row-1"}])

        mock_audit = MagicMock()
        mock_audit.insert.return_value = mock_audit
        mock_audit.execute.return_value = MagicMock(data=[{}])

        def _table(t):
            if t == "booking_state":
                return mock_bs
            elif t == "access_tokens":
                return mock_at
            elif t == "audit_events":
                return mock_audit
            return MagicMock()

        db.table.side_effect = _table
        return db

    def _identity(self, role: str = "admin"):
        return {"user_id": "staff-001", "tenant_id": "tenant-x", "role": role, "sub": "staff-001"}

    def test_generates_token_for_admin(self):
        import json
        booking = _make_booking_row()
        db = self._make_db_for_generate(booking)

        with patch("api.guest_checkout_router._get_identity",
                   return_value=self._identity("admin")):
            from api.guest_checkout_router import generate_guest_checkout_token
            resp = asyncio.run(generate_guest_checkout_token(
                booking_id="booking-abc-123",
                authorization="Bearer fakeJWT",
                client=db,
            ))

        body = json.loads(resp.body)
        assert body["status"] == "token_issued"
        assert "token" in body
        assert "/guest-checkout/" in body["portal_url"]
        assert body["qr_data"] == body["portal_url"]
        assert body["effective_checkout_date"] == "2026-04-05"

    def test_generates_token_for_manager(self):
        import json
        booking = _make_booking_row()
        db = self._make_db_for_generate(booking)

        with patch("api.guest_checkout_router._get_identity",
                   return_value=self._identity("manager")):
            from api.guest_checkout_router import generate_guest_checkout_token
            resp = asyncio.run(generate_guest_checkout_token(
                booking_id="booking-abc-123", authorization="Bearer fake", client=db
            ))
        body = json.loads(resp.body)
        assert body["status"] == "token_issued"

    def test_unauthorized_role_rejected(self):
        import json
        booking = _make_booking_row()
        db = self._make_db_for_generate(booking)

        with patch("api.guest_checkout_router._get_identity",
                   return_value={"user_id": "u", "tenant_id": "tenant-x", "role": "owner", "sub": "u"}):
            from api.guest_checkout_router import generate_guest_checkout_token
            resp = asyncio.run(generate_guest_checkout_token(
                "booking-abc-123", "Bearer fake", db
            ))
        assert resp.status_code == 403

    def test_cancelled_booking_rejected(self):
        import json
        booking = _make_booking_row(status="CANCELLED")
        db = self._make_db_for_generate(booking)

        with patch("api.guest_checkout_router._get_identity",
                   return_value=self._identity("admin")):
            from api.guest_checkout_router import generate_guest_checkout_token
            resp = asyncio.run(generate_guest_checkout_token(
                "booking-abc-123", "Bearer fake", db
            ))
        assert resp.status_code == 409

    def test_early_checkout_date_in_response(self):
        import json
        booking = _make_booking_row(early_checkout_approved=True, early_checkout_date="2026-04-03")
        db = self._make_db_for_generate(booking)

        with patch("api.guest_checkout_router._get_identity",
                   return_value=self._identity("admin")):
            from api.guest_checkout_router import generate_guest_checkout_token
            resp = asyncio.run(generate_guest_checkout_token(
                "booking-abc-123", "Bearer fake", db
            ))
        body = json.loads(resp.body)
        assert body["effective_checkout_date"] == "2026-04-03"


# ===========================================================================
# 3. GET /guest-checkout/{token}
# ===========================================================================

class TestGetGuestCheckoutPortal:
    def test_returns_steps_and_booking(self):
        import json
        raw_token, _ = _make_token()
        booking = _make_booking_row()
        db = _stub_db(booking)

        from api.guest_checkout_router import get_guest_checkout_portal
        resp = asyncio.run(get_guest_checkout_portal(token=raw_token, client=db))
        body = json.loads(resp.body)

        assert resp.status_code == 200
        assert body["booking"]["guest_name"] == "Test Guest"
        assert body["booking"]["effective_checkout_date"] == "2026-04-05"
        assert len(body["steps"]) == 3
        step_keys = [s["key"] for s in body["steps"]]
        assert "confirm_departure" in step_keys
        assert "key_handover" in step_keys
        assert "feedback" in step_keys
        assert body["already_confirmed"] is False
        assert body["required_complete"] is False

    def test_already_confirmed_flag(self):
        import json
        raw_token, _ = _make_token()
        booking = _make_booking_row(
            steps={"confirm_departure": {"completed_at": "2026-04-05T08:00:00Z"},
                   "key_handover":       {"completed_at": "2026-04-05T08:01:00Z"}},
            confirmed_at="2026-04-05T08:05:00Z",
        )
        db = _stub_db(booking)

        from api.guest_checkout_router import get_guest_checkout_portal
        resp = asyncio.run(get_guest_checkout_portal(token=raw_token, client=db))
        body = json.loads(resp.body)
        assert body["already_confirmed"] is True
        assert body["required_complete"] is True

    def test_invalid_token_rejected(self):
        db = MagicMock()
        from api.guest_checkout_router import get_guest_checkout_portal
        resp = asyncio.run(get_guest_checkout_portal(token="INVALID.TOKEN", client=db))
        assert resp.status_code == 401

    def test_revoked_token_rejected(self):
        import json
        raw_token, _ = _make_token()
        booking = _make_booking_row()
        db = _stub_db(booking, access_token_revoked=True)

        from api.guest_checkout_router import get_guest_checkout_portal
        resp = asyncio.run(get_guest_checkout_portal(token=raw_token, client=db))
        assert resp.status_code == 401
        body = json.loads(resp.body)
        assert "revoked" in str(body)


# ===========================================================================
# 4. POST /guest-checkout/{token}/step/{step_key}
# ===========================================================================

class TestSubmitCheckoutStep:
    def test_confirm_departure_step(self):
        import json
        raw_token, _ = _make_token()
        booking = _make_booking_row()
        db = _stub_db(booking)

        from api.guest_checkout_router import submit_checkout_step
        resp = asyncio.run(submit_checkout_step(
            token=raw_token, step_key="confirm_departure", body={}, client=db
        ))
        body = json.loads(resp.body)
        assert resp.status_code == 200
        assert body["status"] == "step_completed"
        assert body["step_key"] == "confirm_departure"
        assert "confirm_departure" in body["steps_completed"]

    def test_feedback_step_with_rating(self):
        import json
        raw_token, _ = _make_token()
        booking = _make_booking_row()
        db = _stub_db(booking)

        from api.guest_checkout_router import submit_checkout_step
        resp = asyncio.run(submit_checkout_step(
            token=raw_token, step_key="feedback",
            body={"rating": 5, "comment": "Wonderful stay!"},
            client=db,
        ))
        body = json.loads(resp.body)
        assert resp.status_code == 200
        assert body["step_key"] == "feedback"

    def test_unknown_step_rejected(self):
        raw_token, _ = _make_token()
        db = MagicMock()

        from api.guest_checkout_router import submit_checkout_step
        resp = asyncio.run(submit_checkout_step(
            token=raw_token, step_key="invalid_step", body={}, client=db
        ))
        assert resp.status_code == 400


# ===========================================================================
# 5. POST /guest-checkout/{token}/complete
# ===========================================================================

class TestCompleteGuestCheckout:
    def test_complete_with_required_steps_done(self):
        import json
        raw_token, _ = _make_token()
        booking = _make_booking_row(steps={
            "confirm_departure": {"completed_at": "2026-04-05T08:00:00Z", "confirmed_by_guest": True},
            "key_handover":       {"completed_at": "2026-04-05T08:01:00Z", "method": "confirmed"},
        })
        db = _stub_db(booking)

        from api.guest_checkout_router import complete_guest_checkout
        resp = asyncio.run(complete_guest_checkout(token=raw_token, client=db))
        body = json.loads(resp.body)
        assert resp.status_code == 200
        assert body["status"] == "confirmed"
        assert "confirmed_at" in body
        assert body["property_name"] == "Emuna Villa"
        assert "Thank you" in body["message"]

    def test_complete_missing_required_step_rejected(self):
        import json
        raw_token, _ = _make_token()
        booking = _make_booking_row(steps={
            "confirm_departure": {"completed_at": "2026-04-05T08:00:00Z"},
            # key_handover missing
        })
        db = _stub_db(booking)

        from api.guest_checkout_router import complete_guest_checkout
        resp = asyncio.run(complete_guest_checkout(token=raw_token, client=db))
        assert resp.status_code == 409
        body = json.loads(resp.body)
        assert "key_handover" in str(body)

    def test_complete_no_steps_rejected(self):
        raw_token, _ = _make_token()
        db = _stub_db(_make_booking_row(steps={}))

        from api.guest_checkout_router import complete_guest_checkout
        resp = asyncio.run(complete_guest_checkout(token=raw_token, client=db))
        assert resp.status_code == 409

    def test_complete_idempotent_already_confirmed(self):
        import json
        raw_token, _ = _make_token()
        booking = _make_booking_row(
            steps={"confirm_departure": {}, "key_handover": {}},
            confirmed_at="2026-04-05T08:05:00+00:00",
        )
        db = _stub_db(booking)

        from api.guest_checkout_router import complete_guest_checkout
        resp = asyncio.run(complete_guest_checkout(token=raw_token, client=db))
        body = json.loads(resp.body)
        assert resp.status_code == 200
        assert body["status"] == "already_confirmed"
        assert body["noop"] is True

    def test_feedback_optional_does_not_block_complete(self):
        """complete() must succeed even when feedback step is missing."""
        import json
        raw_token, _ = _make_token()
        booking = _make_booking_row(steps={
            "confirm_departure": {"completed_at": "2026-04-05T08:00:00Z"},
            "key_handover":       {"completed_at": "2026-04-05T08:01:00Z"},
            # no feedback — optional, must not block
        })
        db = _stub_db(booking)

        from api.guest_checkout_router import complete_guest_checkout
        resp = asyncio.run(complete_guest_checkout(token=raw_token, client=db))
        body = json.loads(resp.body)
        assert resp.status_code == 200
        assert body["status"] == "confirmed"
