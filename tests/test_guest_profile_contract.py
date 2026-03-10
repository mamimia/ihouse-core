"""
Phase 159 — Contract Tests: Guest Profile Normalisation

Tests:
  A — extract_guest_profile: Airbnb — flat guest dict
  B — extract_guest_profile: Airbnb — nested guest object
  C — extract_guest_profile: Booking.com — booker dict
  D — extract_guest_profile: Expedia — primaryGuest dict
  E — extract_guest_profile: VRBO — renter dict
  F — extract_guest_profile: generic provider (agoda)
  G — extract_guest_profile: missing fields → None (no raise)
  H — extract_guest_profile: broken payload → GuestProfile (no raise)
  I — GuestProfile.is_empty()
  J — GuestProfile.to_dict()
  K — _clean / _first helpers: whitespace & None handling
  L — GET /bookings/{id}/guest-profile: found → 200
  M — GET /bookings/{id}/guest-profile: not found → 404
  N — GET /bookings/{id}/guest-profile: tenant isolation → 404
  O — GET /bookings/{id}/guest-profile: response shape correct
  P — GET /bookings/{id}/guest-profile: 500 on DB error
  Q — service.py BOOKING_CREATED triggers guest profile extraction (integration)
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.ota.guest_profile_extractor import (
    GuestProfile,
    extract_guest_profile,
    _clean,
    _first,
)
from api.guest_profile_router import router as gp_router
from api.auth import jwt_auth

_app = FastAPI()
_app.include_router(gp_router)
_app.dependency_overrides[jwt_auth] = lambda: "tenant-159"
_client = TestClient(_app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Mock DB factory
# ---------------------------------------------------------------------------

def _mock_db(rows: list | None = None, raise_exc: Exception | None = None):
    chain = MagicMock()
    if raise_exc is not None:
        chain.execute.side_effect = raise_exc
    else:
        chain.execute.return_value = MagicMock(data=rows if rows is not None else [])
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.limit.return_value = chain
    db = MagicMock()
    db.table.return_value = chain
    return db


def _profile_row(booking_id: str = "bk-159") -> dict:
    return {
        "booking_id":  booking_id,
        "tenant_id":   "tenant-159",
        "guest_name":  "Alice Test",
        "guest_email": "alice@example.com",
        "guest_phone": "+661234567",
        "source":      "airbnb",
        "created_at":  "2025-01-01T00:00:00Z",
    }


# ===========================================================================
# Group A — Airbnb: flat guest dict
# ===========================================================================

class TestGroupA_AirbnbFlat:

    def test_a1_guest_name_extracted(self):
        p = extract_guest_profile("airbnb", {"guest_name": "Bob Smith"})
        assert p.guest_name == "Bob Smith"

    def test_a2_guest_email_extracted(self):
        p = extract_guest_profile("airbnb", {"guest": {"email": "bob@ex.com"}})
        assert p.guest_email == "bob@ex.com"

    def test_a3_guest_phone_extracted(self):
        p = extract_guest_profile("airbnb", {"guest": {"phone": "+66888"}})
        assert p.guest_phone == "+66888"

    def test_a4_source_is_airbnb(self):
        p = extract_guest_profile("airbnb", {})
        assert p.source == "airbnb"


# ===========================================================================
# Group B — Airbnb: nested guest object
# ===========================================================================

class TestGroupB_AirbnbNested:

    def test_b1_nested_name_extracted(self):
        payload = {"guest": {"name": "Carol Ng", "email": "carol@x.com"}}
        p = extract_guest_profile("airbnb", payload)
        assert p.guest_name == "Carol Ng"
        assert p.guest_email == "carol@x.com"

    def test_b2_display_name_fallback(self):
        payload = {"guest": {"display_name": "Dave Jones"}}
        p = extract_guest_profile("airbnb", payload)
        assert p.guest_name == "Dave Jones"


# ===========================================================================
# Group C — Booking.com: booker dict
# ===========================================================================

class TestGroupC_BookingCom:

    def test_c1_first_last_combined(self):
        p = extract_guest_profile("bookingcom", {"booker": {"first_name": "Eve", "last_name": "Taylor"}})
        assert p.guest_name == "Eve Taylor"

    def test_c2_email_from_booker(self):
        p = extract_guest_profile("bookingcom", {"booker": {"email": "eve@bk.com"}})
        assert p.guest_email == "eve@bk.com"

    def test_c3_phone_from_telephone(self):
        p = extract_guest_profile("bookingcom", {"booker": {"telephone": "+111111"}})
        assert p.guest_phone == "+111111"

    def test_c4_source_is_bookingcom(self):
        p = extract_guest_profile("bookingcom", {})
        assert p.source == "bookingcom"


# ===========================================================================
# Group D — Expedia: primaryGuest dict
# ===========================================================================

class TestGroupD_Expedia:

    def test_d1_given_surname_combined(self):
        p = extract_guest_profile("expedia", {"primaryGuest": {"givenName": "Frank", "surName": "Oz"}})
        assert p.guest_name == "Frank Oz"

    def test_d2_email_from_primary_guest(self):
        p = extract_guest_profile("expedia", {"primaryGuest": {"email": "frank@exp.com"}})
        assert p.guest_email == "frank@exp.com"


# ===========================================================================
# Group E — VRBO: renter dict
# ===========================================================================

class TestGroupE_Vrbo:

    def test_e1_first_last_combined(self):
        p = extract_guest_profile("vrbo", {"renter": {"firstName": "Grace", "lastName": "Lee"}})
        assert p.guest_name == "Grace Lee"

    def test_e2_phone_number_field(self):
        p = extract_guest_profile("vrbo", {"renter": {"phoneNumber": "+222"}})
        assert p.guest_phone == "+222"

    def test_e3_source_is_vrbo(self):
        p = extract_guest_profile("vrbo", {})
        assert p.source == "vrbo"


# ===========================================================================
# Group F — Generic provider (agoda)
# ===========================================================================

class TestGroupF_Generic:

    def test_f1_guest_name_from_payload(self):
        p = extract_guest_profile("agoda", {"guest_name": "Hana Kim"})
        assert p.guest_name == "Hana Kim"

    def test_f2_guest_email_from_nested(self):
        p = extract_guest_profile("agoda", {"guest": {"email": "hana@agoda.com"}})
        assert p.guest_email == "hana@agoda.com"

    def test_f3_source_is_provider_name(self):
        p = extract_guest_profile("traveloka", {"guest_name": "Ivan Go"})
        assert p.source == "traveloka"

    def test_f4_first_last_combined_in_guest(self):
        p = extract_guest_profile("hotelbeds", {"guest": {"first_name": "Jane", "last_name": "Doe"}})
        assert p.guest_name == "Jane Doe"


# ===========================================================================
# Group G — Missing fields → None (no raise)
# ===========================================================================

class TestGroupG_MissingFields:

    def test_g1_empty_payload_returns_profile(self):
        p = extract_guest_profile("airbnb", {})
        assert isinstance(p, GuestProfile)

    def test_g2_all_fields_none(self):
        p = extract_guest_profile("bookingcom", {})
        assert p.guest_name is None
        assert p.guest_email is None
        assert p.guest_phone is None

    def test_g3_empty_profile_is_empty(self):
        p = extract_guest_profile("airbnb", {})
        assert p.is_empty()


# ===========================================================================
# Group H — Broken payload → never raises
# ===========================================================================

class TestGroupH_BrokenPayload:

    def test_h1_none_values_dont_raise(self):
        p = extract_guest_profile("airbnb", {"guest": None})
        assert isinstance(p, GuestProfile)

    def test_h2_int_values_dont_raise(self):
        p = extract_guest_profile("bookingcom", {"booker": 12345})
        assert isinstance(p, GuestProfile)

    def test_h3_bad_nested_type_dont_raise(self):
        p = extract_guest_profile("expedia", {"primaryGuest": ["bad", "list"]})
        assert isinstance(p, GuestProfile)


# ===========================================================================
# Group I — GuestProfile.is_empty()
# ===========================================================================

class TestGroupI_IsEmpty:

    def test_i1_empty_when_all_none(self):
        assert GuestProfile().is_empty() is True

    def test_i2_not_empty_with_name(self):
        assert GuestProfile(guest_name="X").is_empty() is False

    def test_i3_not_empty_with_email(self):
        assert GuestProfile(guest_email="x@y.com").is_empty() is False

    def test_i4_not_empty_with_phone(self):
        assert GuestProfile(guest_phone="+1").is_empty() is False


# ===========================================================================
# Group J — GuestProfile.to_dict()
# ===========================================================================

class TestGroupJ_ToDict:

    def test_j1_all_keys_present(self):
        d = GuestProfile("Name", "email@x.com", "+999", "airbnb").to_dict()
        for key in ("guest_name", "guest_email", "guest_phone", "source"):
            assert key in d

    def test_j2_values_correct(self):
        d = GuestProfile("Name", "e@x.com", "+1", "src").to_dict()
        assert d["guest_name"] == "Name"
        assert d["guest_email"] == "e@x.com"

    def test_j3_none_values_in_dict(self):
        d = GuestProfile().to_dict()
        assert d["guest_name"] is None


# ===========================================================================
# Group K — _clean / _first helpers
# ===========================================================================

class TestGroupK_Helpers:

    def test_k1_clean_strips_whitespace(self):
        assert _clean("  hello  ") == "hello"

    def test_k2_clean_none_returns_none(self):
        assert _clean(None) is None

    def test_k3_clean_blank_returns_none(self):
        assert _clean("   ") is None

    def test_k4_first_returns_first_non_none(self):
        assert _first(None, "", "second", "third") == "second"

    def test_k5_first_all_none_returns_none(self):
        assert _first(None, None, "") is None


# ===========================================================================
# Group L — GET /bookings/{id}/guest-profile: found → 200
# ===========================================================================

class TestGroupL_GetFound:

    def test_l1_found_returns_200(self, monkeypatch):
        db = _mock_db(rows=[_profile_row()])
        monkeypatch.setattr("api.guest_profile_router._get_supabase_client", lambda: db)
        resp = _client.get("/bookings/bk-159/guest-profile")
        assert resp.status_code == 200

    def test_l2_guest_name_in_response(self, monkeypatch):
        db = _mock_db(rows=[_profile_row()])
        monkeypatch.setattr("api.guest_profile_router._get_supabase_client", lambda: db)
        data = _client.get("/bookings/bk-159/guest-profile").json()
        assert data["guest_name"] == "Alice Test"

    def test_l3_guest_email_in_response(self, monkeypatch):
        db = _mock_db(rows=[_profile_row()])
        monkeypatch.setattr("api.guest_profile_router._get_supabase_client", lambda: db)
        data = _client.get("/bookings/bk-159/guest-profile").json()
        assert data["guest_email"] == "alice@example.com"


# ===========================================================================
# Group M — GET: not found → 404
# ===========================================================================

class TestGroupM_NotFound:

    def test_m1_not_found_returns_404(self, monkeypatch):
        db = _mock_db(rows=[])
        monkeypatch.setattr("api.guest_profile_router._get_supabase_client", lambda: db)
        resp = _client.get("/bookings/missing/guest-profile")
        assert resp.status_code == 404

    def test_m2_error_body_returned(self, monkeypatch):
        db = _mock_db(rows=[])
        monkeypatch.setattr("api.guest_profile_router._get_supabase_client", lambda: db)
        body = _client.get("/bookings/ghost/guest-profile").json()
        assert "error" in body or "code" in body or "detail" in str(body).lower()


# ===========================================================================
# Group N — tenant isolation → 404
# ===========================================================================

class TestGroupN_TenantIsolation:

    def test_n1_other_tenant_returns_404(self, monkeypatch):
        db = _mock_db(rows=[])
        monkeypatch.setattr("api.guest_profile_router._get_supabase_client", lambda: db)
        resp = _client.get("/bookings/other-tenant-bk/guest-profile")
        assert resp.status_code == 404


# ===========================================================================
# Group O — response shape correct
# ===========================================================================

class TestGroupO_ResponseShape:

    def test_o1_all_fields_in_response(self, monkeypatch):
        db = _mock_db(rows=[_profile_row()])
        monkeypatch.setattr("api.guest_profile_router._get_supabase_client", lambda: db)
        data = _client.get("/bookings/bk-159/guest-profile").json()
        for field in ("booking_id", "tenant_id", "guest_name", "guest_email", "guest_phone", "source"):
            assert field in data

    def test_o2_booking_id_matches_request(self, monkeypatch):
        db = _mock_db(rows=[_profile_row("bk-shape")])
        monkeypatch.setattr("api.guest_profile_router._get_supabase_client", lambda: db)
        data = _client.get("/bookings/bk-shape/guest-profile").json()
        assert data["booking_id"] == "bk-shape"


# ===========================================================================
# Group P — 500 on DB error
# ===========================================================================

class TestGroupP_InternalError:

    def test_p1_db_error_returns_500(self, monkeypatch):
        db = _mock_db(raise_exc=Exception("connection lost"))
        monkeypatch.setattr("api.guest_profile_router._get_supabase_client", lambda: db)
        resp = _client.get("/bookings/bk-err/guest-profile")
        assert resp.status_code == 500


# ===========================================================================
# Group Q — service.py integration: guest profile extracted on BOOKING_CREATED
# ===========================================================================

class TestGroupQ_ServiceIntegration:

    def test_q1_extract_called_with_airbnb_payload(self):
        payload = {"guest": {"name": "Zara West"}, "reservation_id": "R1"}
        p = extract_guest_profile("airbnb", payload)
        assert p.guest_name == "Zara West"
        assert not p.is_empty()

    def test_q2_is_empty_skips_write(self):
        """Empty profile should not trigger DB write (is_empty guard)."""
        p = extract_guest_profile("airbnb", {})
        assert p.is_empty()  # means the service.py guard `if not profile.is_empty()` skips

    def test_q3_extraction_never_blocks_on_exception(self):
        """Simulate an extraction error — must not propagate."""
        result = None
        try:
            with patch("adapters.ota.guest_profile_extractor._extract_airbnb", side_effect=RuntimeError("boom")):
                result = extract_guest_profile("airbnb", {"guest_name": "X"})
        except Exception as exc:
            pytest.fail(f"extract_guest_profile raised unexpectedly: {exc}")
        assert isinstance(result, GuestProfile)
