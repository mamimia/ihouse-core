"""
Phase 63 — Check-in / Check-out Role Guard Tests
===================================================

Proves role-based enforcement for check-in and check-out endpoints.

Strategy:
    - Frozenset tests: pure unit — no HTTP, no mocks
    - Guard logic tests: call _assert_checkin/checkout_role() directly
    - HTTP tests: override jwt_identity via dependency_overrides to inject
                  specific roles cleanly without fighting dev-mode JWT bypass
"""
from __future__ import annotations

import os
os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("IHOUSE_JWT_SECRET", "test-secret-for-role-guard-32bytes!")
os.environ.setdefault("IHOUSE_GUEST_TOKEN_SECRET", "test-guest-secret-32bytes-minimum!")

import pytest
from datetime import date as date_type
from fastapi import HTTPException
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from main import app
import api.booking_checkin_router as checkin_mod
from api.auth import jwt_identity_simple as jwt_identity


def _make_identity(role: str, tenant_id: str = "t1", user_id: str = "u1") -> dict:
    return {"user_id": user_id, "tenant_id": tenant_id, "role": role}


def _mock_active_booking():
    mock_db = MagicMock()
    mock_result = MagicMock()
    mock_result.data = [{
        "booking_id": "bk-63",
        "tenant_id": "t1",
        "status": "active",
        "property_id": "prop-1",
    }]
    mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = mock_result
    mock_db.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock()
    mock_db.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "r1"}])
    mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.is_.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    return mock_db


def _mock_checked_in_booking(check_out: str | None = None):
    """Return a mock DB simulating a checked-in booking.

    Phase 993-harden: check_out defaults to TODAY so the eligibility guard
    passes for role-focused tests. Tests that exercise the timing gate should
    pass an explicit future date and expect 422.
    """
    mock_db = MagicMock()
    mock_result = MagicMock()
    today = date_type.today().isoformat()
    mock_result.data = [{
        "booking_id": "bk-63",
        "tenant_id": "t1",
        "status": "checked_in",
        "property_id": "prop-1",
        "check_out": check_out or today,  # default = today = eligible
        "early_checkout_approved": False,
        "early_checkout_approved_by": None,
        "source": "direct",
    }]
    mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = mock_result
    mock_db.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock()
    mock_db.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])
    return mock_db


def _client_as(role: str) -> TestClient:
    """Return a TestClient with jwt_identity overridden to return given role."""
    identity = _make_identity(role)
    app.dependency_overrides[jwt_identity] = lambda: identity
    return TestClient(app, raise_server_exceptions=False)


def _clear_overrides():
    app.dependency_overrides.pop(jwt_identity, None)


# ---------------------------------------------------------------------------
# Frozenset correctness (pure unit)
# ---------------------------------------------------------------------------

class TestRoleGuardSets:

    def test_checkin_allowed_roles(self):
        assert checkin_mod._CHECKIN_ALLOWED_ROLES == frozenset({"admin", "manager", "checkin"})

    def test_checkout_allowed_roles(self):
        assert checkin_mod._CHECKOUT_ALLOWED_ROLES == frozenset({"admin", "manager", "checkin", "checkout"})

    def test_checkout_not_in_checkin_set(self):
        assert "checkout" not in checkin_mod._CHECKIN_ALLOWED_ROLES

    def test_checkin_in_checkout_set(self):
        assert "checkin" in checkin_mod._CHECKOUT_ALLOWED_ROLES

    def test_cleaner_excluded_from_both(self):
        assert "cleaner" not in checkin_mod._CHECKIN_ALLOWED_ROLES
        assert "cleaner" not in checkin_mod._CHECKOUT_ALLOWED_ROLES

    def test_worker_excluded_from_both(self):
        assert "worker" not in checkin_mod._CHECKIN_ALLOWED_ROLES
        assert "worker" not in checkin_mod._CHECKOUT_ALLOWED_ROLES

    def test_owner_excluded_from_both(self):
        assert "owner" not in checkin_mod._CHECKIN_ALLOWED_ROLES
        assert "owner" not in checkin_mod._CHECKOUT_ALLOWED_ROLES


# ---------------------------------------------------------------------------
# Guard helper logic (direct function call — no HTTP)
# ---------------------------------------------------------------------------

class TestGuardHelpers:
    """Call _assert_checkin_role / _assert_checkout_role directly.
    Production signature: (identity: dict, db: Any).
    For allowed roles, db is never accessed (early return).
    For denied roles with 'worker', db is queried — use MagicMock returning empty data.
    """

    def _mock_db(self):
        """Return a mock DB that simulates no worker_roles found."""
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        return db

    def test_assert_checkin_allows_admin(self):
        checkin_mod._assert_checkin_role(_make_identity("admin"), self._mock_db())  # no raise

    def test_assert_checkin_allows_manager(self):
        checkin_mod._assert_checkin_role(_make_identity("manager"), self._mock_db())

    def test_assert_checkin_allows_checkin(self):
        checkin_mod._assert_checkin_role(_make_identity("checkin"), self._mock_db())

    def test_assert_checkin_denies_checkout(self):
        with pytest.raises(HTTPException) as exc_info:
            checkin_mod._assert_checkin_role(_make_identity("checkout"), self._mock_db())
        assert exc_info.value.status_code == 403
        assert "CHECKIN_DENIED" in exc_info.value.detail

    def test_assert_checkin_denies_cleaner(self):
        with pytest.raises(HTTPException) as exc_info:
            checkin_mod._assert_checkin_role(_make_identity("cleaner"), self._mock_db())
        assert exc_info.value.status_code == 403

    def test_assert_checkin_denies_worker(self):
        with pytest.raises(HTTPException):
            checkin_mod._assert_checkin_role(_make_identity("worker"), self._mock_db())

    def test_assert_checkin_denies_owner(self):
        with pytest.raises(HTTPException):
            checkin_mod._assert_checkin_role(_make_identity("owner"), self._mock_db())

    def test_assert_checkout_allows_admin(self):
        checkin_mod._assert_checkout_role(_make_identity("admin"), self._mock_db())

    def test_assert_checkout_allows_checkout(self):
        checkin_mod._assert_checkout_role(_make_identity("checkout"), self._mock_db())

    def test_assert_checkout_allows_checkin(self):
        checkin_mod._assert_checkout_role(_make_identity("checkin"), self._mock_db())

    def test_assert_checkout_denies_cleaner(self):
        with pytest.raises(HTTPException) as exc_info:
            checkin_mod._assert_checkout_role(_make_identity("cleaner"), self._mock_db())
        assert exc_info.value.status_code == 403
        assert "CHECKOUT_DENIED" in exc_info.value.detail

    def test_assert_checkout_denies_owner(self):
        with pytest.raises(HTTPException):
            checkin_mod._assert_checkout_role(_make_identity("owner"), self._mock_db())


# ---------------------------------------------------------------------------
# HTTP enforcement via jwt_identity dependency override
# ---------------------------------------------------------------------------

class TestCheckinHTTPEnforcement:

    def teardown_method(self, _):
        _clear_overrides()

    def test_admin_can_checkin(self):
        client = _client_as("admin")
        with patch("api.booking_checkin_router._get_supabase_client", return_value=_mock_active_booking()):
            resp = client.post("/bookings/bk-63/checkin",
                               headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "checked_in"

    def test_manager_can_checkin(self):
        client = _client_as("manager")
        with patch("api.booking_checkin_router._get_supabase_client", return_value=_mock_active_booking()):
            resp = client.post("/bookings/bk-63/checkin",
                               headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 200

    def test_checkin_role_can_checkin(self):
        client = _client_as("checkin")
        with patch("api.booking_checkin_router._get_supabase_client", return_value=_mock_active_booking()):
            resp = client.post("/bookings/bk-63/checkin",
                               headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 200

    def test_checkout_role_CANNOT_checkin(self):
        client = _client_as("checkout")
        with patch("api.booking_checkin_router._get_supabase_client", return_value=_mock_active_booking()):
            resp = client.post("/bookings/bk-63/checkin",
                               headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 403
        assert "CHECKIN_DENIED" in resp.json()["detail"]

    def test_cleaner_CANNOT_checkin(self):
        client = _client_as("cleaner")
        with patch("api.booking_checkin_router._get_supabase_client", return_value=_mock_active_booking()):
            resp = client.post("/bookings/bk-63/checkin",
                               headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 403

    def test_worker_CANNOT_checkin(self):
        client = _client_as("worker")
        with patch("api.booking_checkin_router._get_supabase_client", return_value=_mock_active_booking()):
            resp = client.post("/bookings/bk-63/checkin",
                               headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 403

    def test_owner_CANNOT_checkin(self):
        client = _client_as("owner")
        with patch("api.booking_checkin_router._get_supabase_client", return_value=_mock_active_booking()):
            resp = client.post("/bookings/bk-63/checkin",
                               headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 403


class TestCheckoutHTTPEnforcement:

    def teardown_method(self, _):
        _clear_overrides()

    def test_admin_can_checkout(self):
        client = _client_as("admin")
        with patch("api.booking_checkin_router._get_supabase_client", return_value=_mock_checked_in_booking()):
            with patch("tasks.task_writer.write_tasks_for_booking_created", return_value=0):
                resp = client.post("/bookings/bk-63/checkout",
                                   headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 200

    def test_checkout_role_can_checkout(self):
        client = _client_as("checkout")
        with patch("api.booking_checkin_router._get_supabase_client", return_value=_mock_checked_in_booking()):
            with patch("tasks.task_writer.write_tasks_for_booking_created", return_value=0):
                resp = client.post("/bookings/bk-63/checkout",
                                   headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 200

    def test_checkin_role_can_also_checkout(self):
        client = _client_as("checkin")
        with patch("api.booking_checkin_router._get_supabase_client", return_value=_mock_checked_in_booking()):
            with patch("tasks.task_writer.write_tasks_for_booking_created", return_value=0):
                resp = client.post("/bookings/bk-63/checkout",
                                   headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 200

    def test_cleaner_CANNOT_checkout(self):
        client = _client_as("cleaner")
        with patch("api.booking_checkin_router._get_supabase_client", return_value=_mock_checked_in_booking()):
            resp = client.post("/bookings/bk-63/checkout",
                               headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 403
        assert "CHECKOUT_DENIED" in resp.json()["detail"]

    def test_owner_CANNOT_checkout(self):
        client = _client_as("owner")
        with patch("api.booking_checkin_router._get_supabase_client", return_value=_mock_checked_in_booking()):
            resp = client.post("/bookings/bk-63/checkout",
                               headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Phase 993-harden: Checkout-date eligibility enforcement tests
# ---------------------------------------------------------------------------

class TestCheckoutEligibilityEnforcement:
    """Verify the checkout-date gate fires correctly for worker roles
    and is bypassed correctly for admin/manager/ops roles."""

    def teardown_method(self, _):
        _clear_overrides()

    def test_checkout_role_blocked_when_checkout_date_is_future(self):
        """A checkout-role worker cannot checkout before the booking checkout date."""
        client = _client_as("checkout")
        # Provide a future checkout date — eligibility guard must block this.
        future_date = "2099-12-31"
        with patch("api.booking_checkin_router._get_supabase_client",
                   return_value=_mock_checked_in_booking(check_out=future_date)):
            resp = client.post("/bookings/bk-63/checkout",
                               headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 422, resp.json()
        body = resp.json()
        # Should surface CHECKOUT_NOT_ELIGIBLE
        assert "CHECKOUT_NOT_ELIGIBLE" in str(body) or "not permitted" in str(body).lower()

    def test_admin_bypasses_date_gate_on_future_checkout(self):
        """Admin can checkout even before the booking checkout date (bypass role)."""
        client = _client_as("admin")
        future_date = "2099-12-31"
        with patch("api.booking_checkin_router._get_supabase_client",
                   return_value=_mock_checked_in_booking(check_out=future_date)):
            with patch("tasks.task_writer.write_tasks_for_booking_created", return_value=0):
                resp = client.post("/bookings/bk-63/checkout",
                                   headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 200, resp.json()

    def test_checkout_role_allowed_on_checkout_day(self):
        """A checkout-role worker can checkout when check_out equals today."""
        client = _client_as("checkout")
        today = date_type.today().isoformat()
        with patch("api.booking_checkin_router._get_supabase_client",
                   return_value=_mock_checked_in_booking(check_out=today)):
            with patch("tasks.task_writer.write_tasks_for_booking_created", return_value=0):
                resp = client.post("/bookings/bk-63/checkout",
                                   headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 200, resp.json()

    def test_checkout_role_allowed_when_past_checkout_date(self):
        """A checkout-role worker can checkout when check_out is in the past (overdue)."""
        client = _client_as("checkout")
        past_date = "2020-01-01"
        with patch("api.booking_checkin_router._get_supabase_client",
                   return_value=_mock_checked_in_booking(check_out=past_date)):
            with patch("tasks.task_writer.write_tasks_for_booking_created", return_value=0):
                resp = client.post("/bookings/bk-63/checkout",
                                   headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 200, resp.json()
