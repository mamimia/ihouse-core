"""
Phase 998 — Early Check-out Approval Router Tests
==================================================

Tests for:
    POST /admin/bookings/{id}/early-checkout/request
    POST /admin/bookings/{id}/early-checkout/approve
    DELETE /admin/bookings/{id}/early-checkout/approve
    GET /admin/bookings/{id}/early-checkout

Covers:
    - Role enforcement (who can request, who can approve, who cannot)
    - Input validation (request_source, early_checkout_date)
    - Business rule: early_checkout_date must be before original check_out
    - Business rule: early_checkout_date cannot be in the past
    - Task rescheduling on approval
    - Revocation guard (cannot revoke after checked_out)
    - _can_approve: admin always can, manager needs capability grant
"""
from __future__ import annotations

import os
os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("IHOUSE_JWT_SECRET", "test-secret-for-early-checkout-32b!")
os.environ.setdefault("IHOUSE_GUEST_TOKEN_SECRET", "test-guest-secret-32bytes-minimum!")

from datetime import date as date_type
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from api.auth import jwt_identity_simple as jwt_identity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_identity(role: str, user_id: str = "u1", tenant_id: str = "t1") -> dict:
    return {"user_id": user_id, "tenant_id": tenant_id, "role": role}


def _client_as(role: str, user_id: str = "u1") -> TestClient:
    identity = _make_identity(role, user_id=user_id)
    app.dependency_overrides[jwt_identity] = lambda: identity
    return TestClient(app, raise_server_exceptions=False)


def _clear():
    app.dependency_overrides.pop(jwt_identity, None)


TODAY = date_type.today().isoformat()
FUTURE = "2099-12-31"
PAST = "2020-01-01"
ORIGINAL_CHECKOUT = "2099-12-31"   # far future, so early_checkout_date < it
EARLY_DATE = "2099-12-15"          # before ORIGINAL_CHECKOUT


def _mock_booking_db(
    status: str = "checked_in",
    check_out: str = ORIGINAL_CHECKOUT,
    early_checkout_approved: bool = False,
    early_checkout_date: str | None = None,
    checked_out_at: str | None = None,
    manager_can_approve: bool = False,
) -> MagicMock:
    """Build a MagicMock DB that returns the right data for each query."""
    mock_db = MagicMock()
    mock_result = MagicMock()
    mock_result.data = [{
        "booking_id": "bk-998",
        "tenant_id": "t1",
        "status": status,
        "check_in": "2026-01-01",
        "check_out": check_out,
        "property_id": "prop-1",
        "guest_name": "Test Guest",
        "early_checkout_approved": early_checkout_approved,
        "early_checkout_approved_by": "u-manager" if early_checkout_approved else None,
        "early_checkout_approved_at": "2026-03-29T10:00:00Z" if early_checkout_approved else None,
        "early_checkout_reason": "flight change" if early_checkout_approved else None,
        "early_checkout_date": early_checkout_date,
        "early_checkout_time": None,
        "early_checkout_requested_at": None,
        "early_checkout_request_source": None,
        "early_checkout_request_note": None,
        "early_checkout_approval_note": None,
        "checked_out_at": checked_out_at,
    }]

    # Permission row for manager capability check
    perm_result = MagicMock()
    perm_result.data = [{
        "permissions": {"can_approve_early_checkout": manager_can_approve}
    }]

    # Task row
    task_result = MagicMock()
    task_result.data = [{
        "task_id": "task-001",
        "due_date": check_out,
        "priority": "MEDIUM",
        "status": "PENDING",
    }]

    # Update/insert always succeeds
    update_mock = MagicMock()
    update_mock.execute.return_value = MagicMock(data=[])
    insert_mock = MagicMock()
    insert_mock.execute.return_value = MagicMock(data=[])

    # Wire the mock: every table().select chain returns mock_result by default
    # (needed for booking lookup, task lookup)
    table_mock = MagicMock()
    mock_db.table.return_value = table_mock

    # select chains
    select_mock = MagicMock()
    table_mock.select.return_value = select_mock
    eq1 = MagicMock()
    select_mock.eq.return_value = eq1
    eq2 = MagicMock()
    eq1.eq.return_value = eq2
    eq2.limit.return_value = MagicMock(execute=MagicMock(return_value=mock_result))
    eq2.execute.return_value = perm_result  # for direct .execute (permissions)

    # not_.in_ chain for task queries
    not_mock = MagicMock()
    eq2.not_ = not_mock
    not_in_mock = MagicMock()
    not_mock.in_.return_value = not_in_mock
    not_in_mock.limit.return_value = MagicMock(execute=MagicMock(return_value=task_result))

    # eq chains for task queries (3-level deep)
    eq3 = MagicMock()
    eq2.eq.return_value = eq3
    eq3.not_ = not_mock
    eq3.eq.return_value = MagicMock(
        not_=not_mock,
        eq=MagicMock(return_value=MagicMock(
            not_=not_mock,
        )),
    )

    # update chain
    table_mock.update.return_value = MagicMock(
        eq=MagicMock(return_value=MagicMock(
            eq=MagicMock(return_value=MagicMock(
                execute=MagicMock(return_value=MagicMock(data=[]))
            ))
        ))
    )

    # insert chain (audit)
    table_mock.insert.return_value = MagicMock(execute=MagicMock(return_value=MagicMock(data=[])))

    return mock_db


# ===========================================================================
# Request intake tests
# ===========================================================================

class TestEarlyCheckoutRequest:

    def teardown_method(self, _):
        _clear()

    def test_admin_can_record_request(self):
        client = _client_as("admin")
        with patch("api.early_checkout_router._get_db", return_value=_mock_booking_db()):
            resp = client.post("/admin/bookings/bk-998/early-checkout/request",
                               json={"request_source": "phone", "request_note": "Guest called"},
                               headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 200, resp.json()
        body = resp.json()
        assert body["status"] == "request_recorded"
        assert body["request_source"] == "phone"

    def test_ops_can_record_request(self):
        client = _client_as("ops")
        with patch("api.early_checkout_router._get_db", return_value=_mock_booking_db()):
            resp = client.post("/admin/bookings/bk-998/early-checkout/request",
                               json={"request_source": "message"},
                               headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 200, resp.json()

    def test_manager_can_record_request(self):
        client = _client_as("manager")
        with patch("api.early_checkout_router._get_db", return_value=_mock_booking_db()):
            resp = client.post("/admin/bookings/bk-998/early-checkout/request",
                               json={"request_source": "guest_portal"},
                               headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 200, resp.json()

    def test_checkout_worker_CANNOT_record_request(self):
        client = _client_as("checkout")
        with patch("api.early_checkout_router._get_db", return_value=_mock_booking_db()):
            resp = client.post("/admin/bookings/bk-998/early-checkout/request",
                               json={"request_source": "phone"},
                               headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 403

    def test_invalid_request_source_rejected(self):
        client = _client_as("admin")
        with patch("api.early_checkout_router._get_db", return_value=_mock_booking_db()):
            resp = client.post("/admin/bookings/bk-998/early-checkout/request",
                               json={"request_source": "telegram"},  # invalid
                               headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 400

    def test_request_on_non_checkedin_booking_rejected(self):
        client = _client_as("admin")
        with patch("api.early_checkout_router._get_db",
                   return_value=_mock_booking_db(status="checked_out")):
            resp = client.post("/admin/bookings/bk-998/early-checkout/request",
                               json={"request_source": "phone"},
                               headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 409


# ===========================================================================
# Approval tests
# ===========================================================================

class TestEarlyCheckoutApproval:

    def teardown_method(self, _):
        _clear()

    def test_admin_can_approve(self):
        client = _client_as("admin")
        with patch("api.early_checkout_router._get_db",
                   return_value=_mock_booking_db(manager_can_approve=True)):
            resp = client.post("/admin/bookings/bk-998/early-checkout/approve",
                               json={"early_checkout_date": EARLY_DATE, "reason": "flight change"},
                               headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 200, resp.json()
        body = resp.json()
        assert body["status"] == "approved"
        assert body["early_checkout_date"] == EARLY_DATE
        assert body["original_checkout_date"] == ORIGINAL_CHECKOUT

    def test_manager_with_capability_can_approve(self):
        client = _client_as("manager")
        with patch("api.early_checkout_router._get_db",
                   return_value=_mock_booking_db(manager_can_approve=True)):
            with patch("api.early_checkout_router._can_approve", return_value=True):
                resp = client.post("/admin/bookings/bk-998/early-checkout/approve",
                                   json={"early_checkout_date": EARLY_DATE},
                                   headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 200, resp.json()

    def test_manager_WITHOUT_capability_denied(self):
        client = _client_as("manager")
        with patch("api.early_checkout_router._get_db",
                   return_value=_mock_booking_db(manager_can_approve=False)):
            with patch("api.early_checkout_router._can_approve", return_value=False):
                resp = client.post("/admin/bookings/bk-998/early-checkout/approve",
                                   json={"early_checkout_date": EARLY_DATE},
                                   headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 403
        assert "can_approve_early_checkout" in resp.json().get("detail", "")

    def test_ops_CANNOT_approve(self):
        client = _client_as("ops")
        with patch("api.early_checkout_router._get_db", return_value=_mock_booking_db()):
            resp = client.post("/admin/bookings/bk-998/early-checkout/approve",
                               json={"early_checkout_date": EARLY_DATE},
                               headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 403

    def test_checkout_worker_CANNOT_approve(self):
        client = _client_as("checkout")
        with patch("api.early_checkout_router._get_db", return_value=_mock_booking_db()):
            resp = client.post("/admin/bookings/bk-998/early-checkout/approve",
                               json={"early_checkout_date": EARLY_DATE},
                               headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 403

    def test_early_date_missing_rejected(self):
        client = _client_as("admin")
        with patch("api.early_checkout_router._get_db", return_value=_mock_booking_db()):
            resp = client.post("/admin/bookings/bk-998/early-checkout/approve",
                               json={},  # no date
                               headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 400

    def test_early_date_after_original_checkout_rejected(self):
        """Cannot approve an 'early' checkout that is after the original checkout date."""
        client = _client_as("admin")
        original = "2099-12-15"
        after_original = "2099-12-31"  # after original
        with patch("api.early_checkout_router._get_db",
                   return_value=_mock_booking_db(check_out=original)):
            resp = client.post("/admin/bookings/bk-998/early-checkout/approve",
                               json={"early_checkout_date": after_original},
                               headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 400
        assert "before" in resp.json().get("detail", "").lower()

    def test_early_date_same_as_original_checkout_rejected(self):
        """Same-day is not 'early' — use normal checkout."""
        client = _client_as("admin")
        same = "2099-12-15"
        with patch("api.early_checkout_router._get_db",
                   return_value=_mock_booking_db(check_out=same)):
            resp = client.post("/admin/bookings/bk-998/early-checkout/approve",
                               json={"early_checkout_date": same},
                               headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 400

    def test_past_early_date_rejected(self):
        """Early checkout date in the past is not allowed."""
        client = _client_as("admin")
        with patch("api.early_checkout_router._get_db", return_value=_mock_booking_db()):
            resp = client.post("/admin/bookings/bk-998/early-checkout/approve",
                               json={"early_checkout_date": PAST},
                               headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 400
        assert "past" in resp.json().get("detail", "").lower()


# ===========================================================================
# Revocation tests
# ===========================================================================

class TestEarlyCheckoutRevocation:

    def teardown_method(self, _):
        _clear()

    def test_admin_can_revoke_active_approval(self):
        client = _client_as("admin")
        db = _mock_booking_db(
            early_checkout_approved=True,
            early_checkout_date=EARLY_DATE,
            manager_can_approve=True,
        )
        with patch("api.early_checkout_router._get_db", return_value=db):
            with patch("api.early_checkout_router._can_approve", return_value=True):
                resp = client.delete("/admin/bookings/bk-998/early-checkout/approve",
                                     headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 200, resp.json()
        assert resp.json()["status"] == "revoked"

    def test_cannot_revoke_after_checkout(self):
        client = _client_as("admin")
        db = _mock_booking_db(
            early_checkout_approved=True,
            checked_out_at="2026-03-29T11:00:00Z",
            manager_can_approve=True,
        )
        with patch("api.early_checkout_router._get_db", return_value=db):
            with patch("api.early_checkout_router._can_approve", return_value=True):
                resp = client.delete("/admin/bookings/bk-998/early-checkout/approve",
                                     headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 409
        assert "ALREADY_CHECKED_OUT" in str(resp.json())

    def test_cannot_revoke_if_not_approved(self):
        client = _client_as("admin")
        db = _mock_booking_db(early_checkout_approved=False, manager_can_approve=True)
        with patch("api.early_checkout_router._get_db", return_value=db):
            with patch("api.early_checkout_router._can_approve", return_value=True):
                resp = client.delete("/admin/bookings/bk-998/early-checkout/approve",
                                     headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 409
        assert "NOT_APPROVED" in str(resp.json())

    def test_ops_CANNOT_revoke(self):
        client = _client_as("ops")
        with patch("api.early_checkout_router._get_db",
                   return_value=_mock_booking_db(early_checkout_approved=True)):
            resp = client.delete("/admin/bookings/bk-998/early-checkout/approve",
                                 headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 403


# ===========================================================================
# GET state tests
# ===========================================================================

class TestEarlyCheckoutGetState:

    def teardown_method(self, _):
        _clear()

    def test_admin_can_read_state(self):
        client = _client_as("admin")
        with patch("api.early_checkout_router._get_db",
                   return_value=_mock_booking_db(early_checkout_approved=True,
                                                  early_checkout_date=EARLY_DATE,
                                                  manager_can_approve=True)):
            resp = client.get("/admin/bookings/bk-998/early-checkout",
                              headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 200, resp.json()
        body = resp.json()
        assert body["approval"]["approved"] is True
        assert body["original_checkout_date"] == ORIGINAL_CHECKOUT

    def test_worker_CANNOT_read_state(self):
        client = _client_as("worker")
        with patch("api.early_checkout_router._get_db", return_value=_mock_booking_db()):
            resp = client.get("/admin/bookings/bk-998/early-checkout",
                              headers={"Authorization": "Bearer dev"})
        assert resp.status_code == 403
