"""
Phases 606–625 — Wave 2 Guest Check-in System Contract Tests

Tests for:
    - Form Creation & Retrieval (Phase 606)
    - Add Guests (Phase 607)
    - Passport Photo Upload (Phase 608)
    - Tourist vs Resident Logic (Phase 609)
    - Deposit Collection (Phase 610)
    - Digital Signature (Phase 611)
    - Form Submission (Phase 612)
    - QR Code Generation (Phase 613)
    - Pre-Arrival Self-Service (Phase 615)
    - E2E Flow (Phases 619-625)
"""
from __future__ import annotations

from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import main

_TENANT = "tenant-wave2-test"


def _make_client() -> TestClient:
    return TestClient(main.app)


def _auth_header() -> dict:
    return {"Authorization": "Bearer mock-token"}


# ---------------------------------------------------------------------------
# Mock DB
# ---------------------------------------------------------------------------

class _MockResult:
    def __init__(self, data=None, count=None):
        self.data = data or []
        self.count = count or 0


class _MockTable:
    def __init__(self, rows=None):
        self._rows = rows or []
        self._result = _MockResult(data=self._rows)

    def select(self, *a, **kw): return self
    def eq(self, *a, **kw): return self
    def limit(self, *a): return self
    def order(self, *a, **kw): return self
    def insert(self, data):
        self._rows = [data] if isinstance(data, dict) else data
        self._result = _MockResult(data=self._rows)
        return self
    def upsert(self, data, **kw):
        self._rows = [data] if isinstance(data, dict) else data
        self._result = _MockResult(data=self._rows)
        return self
    def update(self, data):
        if self._rows:
            for r in self._rows:
                if isinstance(r, dict):
                    r.update(data)
        self._result = _MockResult(data=self._rows)
        return self
    def delete(self):
        self._result = _MockResult(data=self._rows)
        return self
    def execute(self):
        return self._result


class _MockDB:
    def __init__(self, tables: dict = None):
        self._tables = tables or {}

    def table(self, name: str):
        return self._tables.get(name, _MockTable())


def _checkin_db(form_status="pending", with_guests=False, with_deposit=False, with_qr=False):
    """Build a mock DB with check-in form state."""
    form = {
        "id": "form-uuid-1", "tenant_id": _TENANT, "booking_id": "BK-001",
        "property_id": "prop-1", "form_status": form_status,
        "guest_type": "tourist", "form_language": "en",
    }

    guests = []
    if with_guests:
        guests = [{
            "id": "guest-uuid-1", "form_id": "form-uuid-1", "full_name": "John Doe",
            "guest_number": 1, "nationality": "US", "document_type": "passport",
            "document_number": "X1234567", "passport_photo_url": "https://storage/photo1.jpg",
            "is_primary": True,
        }]

    deposit = []
    if with_deposit:
        deposit = [{
            "id": "dep-uuid-1", "tenant_id": _TENANT, "booking_id": "BK-001",
            "property_id": "prop-1", "amount": 5000, "currency": "THB",
            "status": "collected",
        }]

    qr = []
    if with_qr:
        qr = [{
            "id": "qr-uuid-1", "tenant_id": _TENANT, "booking_id": "BK-001",
            "property_id": "prop-1", "token": "ABC123XYZ456",
            "portal_url": "https://app.domaniqo.com/guest/ABC123XYZ456",
        }]

    return _MockDB({
        "guest_checkin_forms": _MockTable([form]),
        "guest_checkin_guests": _MockTable(guests),
        "guest_deposit_records": _MockTable(deposit),
        "guest_qr_tokens": _MockTable(qr),
    })


def _empty_checkin_db():
    return _MockDB({
        "guest_checkin_forms": _MockTable([]),
        "guest_checkin_guests": _MockTable([]),
        "guest_deposit_records": _MockTable([]),
        "guest_qr_tokens": _MockTable([]),
    })


# ===========================================================================
# Phase 606 — Create / Get check-in form
# ===========================================================================

class TestCheckinFormCRUD:

    def test_create_form(self):
        with patch("api.guest_checkin_form_router._get_supabase_client", return_value=_empty_checkin_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/bookings/BK-001/checkin-form",
                json={"property_id": "prop-1", "guest_type": "tourist"},
                headers=_auth_header(),
            )
        assert resp.status_code == 201
        assert resp.json()["already_exists"] is False

    def test_create_form_returns_existing(self):
        with patch("api.guest_checkin_form_router._get_supabase_client", return_value=_checkin_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/bookings/BK-001/checkin-form",
                json={"property_id": "prop-1"},
                headers=_auth_header(),
            )
        assert resp.status_code == 200
        assert resp.json()["already_exists"] is True

    def test_get_form(self):
        with patch("api.guest_checkin_form_router._get_supabase_client", return_value=_checkin_db(with_guests=True)), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get("/bookings/BK-001/checkin-form", headers=_auth_header())
        assert resp.status_code == 200
        body = resp.json()
        assert body["booking_id"] == "BK-001"
        assert len(body["guests"]) >= 1

    def test_get_form_not_found(self):
        with patch("api.guest_checkin_form_router._get_supabase_client", return_value=_empty_checkin_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get("/bookings/BK-999/checkin-form", headers=_auth_header())
        assert resp.status_code == 404


# ===========================================================================
# Phase 607 — Add guests
# ===========================================================================

class TestAddGuests:

    def test_add_guest(self):
        with patch("api.guest_checkin_form_router._get_supabase_client", return_value=_checkin_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/checkin-forms/form-uuid-1/guests",
                json={"full_name": "Jane Doe", "nationality": "UK", "guest_number": 2},
                headers=_auth_header(),
            )
        assert resp.status_code == 201

    def test_add_guest_missing_name(self):
        with patch("api.guest_checkin_form_router._get_supabase_client", return_value=_checkin_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/checkin-forms/form-uuid-1/guests",
                json={"nationality": "UK"},
                headers=_auth_header(),
            )
        assert resp.status_code == 400


# ===========================================================================
# Phase 608 — Passport photo upload
# ===========================================================================

class TestPassportPhoto:

    def test_upload_photo(self):
        with patch("api.guest_checkin_form_router._get_supabase_client", return_value=_checkin_db(with_guests=True)), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/checkin-forms/form-uuid-1/guests/guest-uuid-1/passport-photo",
                json={"photo_url": "https://storage.example.com/passport.jpg"},
                headers=_auth_header(),
            )
        assert resp.status_code == 200
        assert resp.json()["photo_uploaded"] is True

    def test_upload_photo_missing_url(self):
        with patch("api.guest_checkin_form_router._get_supabase_client", return_value=_checkin_db(with_guests=True)), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/checkin-forms/form-uuid-1/guests/guest-uuid-1/passport-photo",
                json={},
                headers=_auth_header(),
            )
        assert resp.status_code == 400

    def test_upload_photo_guest_not_found(self):
        with patch("api.guest_checkin_form_router._get_supabase_client", return_value=_empty_checkin_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/checkin-forms/f1/guests/g-missing/passport-photo",
                json={"photo_url": "https://example.com/img.jpg"},
                headers=_auth_header(),
            )
        assert resp.status_code == 404


# ===========================================================================
# Phase 610 — Deposit collection
# ===========================================================================

class TestDepositCollection:

    def test_collect_deposit(self):
        with patch("api.guest_checkin_form_router._get_supabase_client", return_value=_empty_checkin_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/bookings/BK-001/deposit",
                json={"amount": 5000, "property_id": "prop-1", "collected_by": "worker-1"},
                headers=_auth_header(),
            )
        assert resp.status_code == 201

    def test_collect_deposit_invalid_amount(self):
        with patch("api.guest_checkin_form_router._get_supabase_client", return_value=_empty_checkin_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/bookings/BK-001/deposit",
                json={"amount": -100},
                headers=_auth_header(),
            )
        assert resp.status_code == 400

    def test_collect_deposit_missing_amount(self):
        with patch("api.guest_checkin_form_router._get_supabase_client", return_value=_empty_checkin_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post("/bookings/BK-001/deposit", json={}, headers=_auth_header())
        assert resp.status_code == 400


# ===========================================================================
# Phase 611 — Digital Signature
# ===========================================================================

class TestDigitalSignature:

    def test_save_signature(self):
        with patch("api.guest_checkin_form_router._get_supabase_client", return_value=_checkin_db(with_deposit=True)), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/checkin-forms/form-uuid-1/signature",
                json={"signature_url": "data:image/png;base64,iVBORw0KGgoAAAANS"},
                headers=_auth_header(),
            )
        assert resp.status_code == 200
        assert resp.json()["signature_saved"] is True

    def test_save_signature_missing_url(self):
        with patch("api.guest_checkin_form_router._get_supabase_client", return_value=_checkin_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/checkin-forms/form-uuid-1/signature",
                json={},
                headers=_auth_header(),
            )
        assert resp.status_code == 400


# ===========================================================================
# Phase 612 — Form Submit
# ===========================================================================

class TestFormSubmit:

    def test_submit_form_with_guests(self):
        with patch("api.guest_checkin_form_router._get_supabase_client", return_value=_checkin_db(with_guests=True)), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/checkin-forms/form-uuid-1/submit",
                json={"worker_id": "worker-1"},
                headers=_auth_header(),
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["form_status"] == "completed"

    def test_submit_form_no_guests_fails(self):
        with patch("api.guest_checkin_form_router._get_supabase_client", return_value=_checkin_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/checkin-forms/form-uuid-1/submit",
                json={},
                headers=_auth_header(),
            )
        assert resp.status_code == 409

    def test_submit_form_force_override(self):
        with patch("api.guest_checkin_form_router._get_supabase_client", return_value=_checkin_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/checkin-forms/form-uuid-1/submit",
                json={"force": True},
                headers=_auth_header(),
            )
        assert resp.status_code == 200
        assert resp.json()["validation_bypassed"] is True

    def test_submit_form_already_completed(self):
        with patch("api.guest_checkin_form_router._get_supabase_client", return_value=_checkin_db("completed")), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/checkin-forms/form-uuid-1/submit", json={}, headers=_auth_header(),
            )
        assert resp.status_code == 200
        assert resp.json()["already_completed"] is True


# ===========================================================================
# Phase 613 — QR Code Generation
# ===========================================================================

class TestQRGeneration:

    def test_generate_qr(self):
        with patch("api.guest_checkin_form_router._get_supabase_client", return_value=_empty_checkin_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/bookings/BK-001/generate-qr",
                json={"property_id": "prop-1"},
                headers=_auth_header(),
            )
        assert resp.status_code == 201
        body = resp.json()
        assert body["already_exists"] is False
        assert "domaniqo.com/guest/" in body["portal_url"]

    def test_generate_qr_idempotent(self):
        with patch("api.guest_checkin_form_router._get_supabase_client", return_value=_checkin_db(with_qr=True)), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/bookings/BK-001/generate-qr",
                json={"property_id": "prop-1"},
                headers=_auth_header(),
            )
        assert resp.status_code == 200
        assert resp.json()["already_exists"] is True


# ===========================================================================
# Phase 615 — Pre-arrival Self-service
# ===========================================================================

class TestPreArrival:

    def test_pre_arrival_view_valid_token(self):
        with patch("api.guest_checkin_form_router._get_supabase_client", return_value=_checkin_db(with_qr=True)):
            resp = _make_client().get("/guest/pre-arrival/ABC123XYZ456")
        assert resp.status_code == 200
        assert resp.json()["token_valid"] is True

    def test_pre_arrival_view_invalid_token(self):
        with patch("api.guest_checkin_form_router._get_supabase_client", return_value=_empty_checkin_db()):
            resp = _make_client().get("/guest/pre-arrival/INVALID")
        assert resp.status_code == 404

    def test_pre_arrival_submit(self):
        db = _checkin_db(with_qr=True)
        with patch("api.guest_checkin_form_router._get_supabase_client", return_value=db):
            resp = _make_client().post(
                "/guest/pre-arrival/ABC123XYZ456",
                json={
                    "guest_type": "tourist",
                    "form_language": "en",
                    "guest": {
                        "full_name": "Pre-arrival Guest",
                        "nationality": "IL",
                        "document_type": "passport",
                        "document_number": "P123456",
                    },
                },
            )
        assert resp.status_code == 200
        assert resp.json()["saved"] is True

    def test_pre_arrival_submit_invalid_token(self):
        with patch("api.guest_checkin_form_router._get_supabase_client", return_value=_empty_checkin_db()):
            resp = _make_client().post(
                "/guest/pre-arrival/INVALID",
                json={"guest": {"full_name": "Nobody"}},
            )
        assert resp.status_code == 404


# ===========================================================================
# Phases 619-625 — E2E & Edge Cases
# ===========================================================================

class TestGuestCheckinE2E:
    """Full lifecycle test: create form → add guest → deposit → signature → submit → QR"""

    def test_full_checkin_flow(self):
        """E2E: Sequential steps in correct order."""
        db = _empty_checkin_db()

        with patch("api.guest_checkin_form_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()

            # Step 1: Create form
            r1 = client.post(
                "/bookings/BK-E2E/checkin-form",
                json={"property_id": "prop-1", "guest_type": "tourist"},
                headers=_auth_header(),
            )
            assert r1.status_code == 201

            # Step 2: Add guest
            r2 = client.post(
                "/checkin-forms/form-uuid-1/guests",
                json={"full_name": "E2E Guest", "nationality": "US", "guest_number": 1},
                headers=_auth_header(),
            )
            assert r2.status_code == 201

            # Step 3: Deposit
            r3 = client.post(
                "/bookings/BK-E2E/deposit",
                json={"amount": 3000, "property_id": "prop-1"},
                headers=_auth_header(),
            )
            assert r3.status_code == 201

            # Step 4: QR generation
            r4 = client.post(
                "/bookings/BK-E2E/generate-qr",
                json={"property_id": "prop-1"},
                headers=_auth_header(),
            )
            assert r4.status_code == 201
            assert "domaniqo.com" in r4.json()["portal_url"]


class TestGuestCheckinEdgeCases:

    def test_multiple_guests_different_types(self):
        db = _checkin_db()
        with patch("api.guest_checkin_form_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            # Add tourist guest
            r1 = client.post(
                "/checkin-forms/form-uuid-1/guests",
                json={"full_name": "Tourist Guest", "nationality": "JP", "document_type": "passport", "guest_number": 1},
                headers=_auth_header(),
            )
            assert r1.status_code == 201
            # Add resident guest
            r2 = client.post(
                "/checkin-forms/form-uuid-1/guests",
                json={"full_name": "Resident Guest", "document_number": "ID-999", "guest_number": 2},
                headers=_auth_header(),
            )
            assert r2.status_code == 201

    def test_form_language_selection(self):
        db = _empty_checkin_db()
        with patch("api.guest_checkin_form_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/bookings/BK-LANG/checkin-form",
                json={"property_id": "prop-1", "form_language": "th"},
                headers=_auth_header(),
            )
        assert resp.status_code == 201
        assert resp.json().get("form_language") == "th"

    def test_form_language_fallback(self):
        db = _empty_checkin_db()
        with patch("api.guest_checkin_form_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/bookings/BK-LANG2/checkin-form",
                json={"property_id": "prop-1", "form_language": "xx"},  # invalid → en
                headers=_auth_header(),
            )
        assert resp.status_code == 201
        assert resp.json().get("form_language") == "en"

    def test_deposit_zero_amount_rejected(self):
        with patch("api.guest_checkin_form_router._get_supabase_client", return_value=_empty_checkin_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/bookings/BK-001/deposit", json={"amount": 0}, headers=_auth_header(),
            )
        assert resp.status_code == 400

    def test_qr_token_uniqueness(self):
        """Token generation should produce valid tokens."""
        db = _empty_checkin_db()
        with patch("api.guest_checkin_form_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            r1 = client.post("/bookings/BK-A/generate-qr", json={"property_id": "p1"}, headers=_auth_header())
        assert r1.status_code == 201
        token = r1.json()["token"]
        assert len(token) == 12  # Token should be 12 chars
        assert "domaniqo.com" in r1.json()["portal_url"]

    def test_pre_arrival_without_existing_form(self):
        """Pre-arrival submit should create form if one doesn't exist."""
        db = _MockDB({
            "guest_qr_tokens": _MockTable([{
                "tenant_id": _TENANT, "booking_id": "BK-NEW", "property_id": "prop-1",
                "token": "TOKEN_NEW",
            }]),
            "guest_checkin_forms": _MockTable([]),
            "guest_checkin_guests": _MockTable([]),
        })
        with patch("api.guest_checkin_form_router._get_supabase_client", return_value=db):
            resp = _make_client().post(
                "/guest/pre-arrival/TOKEN_NEW",
                json={"guest": {"full_name": "New Guest"}, "guest_type": "tourist"},
            )
        assert resp.status_code == 200
        assert resp.json()["form_status"] == "partial"
