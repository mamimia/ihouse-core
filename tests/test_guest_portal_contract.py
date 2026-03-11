"""
Phase 262 — Guest Self-Service Portal Contract Tests
=====================================================

Tests: 21 across 5 groups.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from main import app
import services.guest_portal as portal

client = TestClient(app, raise_server_exceptions=False)

# Valid header for DEMO-001 booking
VALID_TOKEN = "guest-valid-token"
INVALID_TOKEN = "INVALID-bad"
GOOD_REF = "DEMO-001"
BAD_REF  = "NO-SUCH-BOOKING"

HEADERS_OK  = {"x-guest-token": VALID_TOKEN}
HEADERS_BAD = {"x-guest-token": INVALID_TOKEN}


# ---------------------------------------------------------------------------
# Group A — Service: validate_guest_token
# ---------------------------------------------------------------------------

class TestGroupATokenValidation:

    def test_a1_valid_token_returns_true(self):
        assert portal.validate_guest_token("DEMO-001", "any-token") is True

    def test_a2_empty_token_returns_false(self):
        assert portal.validate_guest_token("DEMO-001", "") is False

    def test_a3_invalid_prefix_returns_false(self):
        assert portal.validate_guest_token("DEMO-001", "INVALID-xyz") is False


# ---------------------------------------------------------------------------
# Group B — Service: get_guest_booking
# ---------------------------------------------------------------------------

class TestGroupBGetGuestBooking:

    def test_b1_returns_view_for_valid_token_and_known_ref(self):
        result = portal.get_guest_booking(GOOD_REF, VALID_TOKEN, portal.stub_lookup)
        assert isinstance(result, portal.GuestBookingView)
        assert result.booking_ref == GOOD_REF

    def test_b2_returns_error_for_invalid_token(self):
        result = portal.get_guest_booking(GOOD_REF, INVALID_TOKEN, portal.stub_lookup)
        assert isinstance(result, portal.GuestPortalError)
        assert result.code == "token_invalid"

    def test_b3_returns_error_for_unknown_booking(self):
        result = portal.get_guest_booking(BAD_REF, VALID_TOKEN, portal.stub_lookup)
        assert isinstance(result, portal.GuestPortalError)
        assert result.code == "not_found"

    def test_b4_demo_booking_has_wifi_fields(self):
        result = portal.get_guest_booking(GOOD_REF, VALID_TOKEN, portal.stub_lookup)
        assert isinstance(result, portal.GuestBookingView)
        assert result.wifi_name is not None
        assert result.wifi_password is not None

    def test_b5_demo_booking_has_house_rules(self):
        result = portal.get_guest_booking(GOOD_REF, VALID_TOKEN, portal.stub_lookup)
        assert isinstance(result, portal.GuestBookingView)
        assert len(result.house_rules) > 0


# ---------------------------------------------------------------------------
# Group C — HTTP: GET /guest/booking/{ref}
# ---------------------------------------------------------------------------

class TestGroupCHttpOverview:

    def test_c1_valid_token_returns_200(self):
        resp = client.get(f"/guest/booking/{GOOD_REF}", headers=HEADERS_OK)
        assert resp.status_code == 200
        body = resp.json()
        assert body["booking_ref"] == GOOD_REF
        assert "check_in_date" in body
        assert "check_out_date" in body
        assert "access_code" in body

    def test_c2_invalid_token_returns_401(self):
        resp = client.get(f"/guest/booking/{GOOD_REF}", headers=HEADERS_BAD)
        assert resp.status_code == 401

    def test_c3_unknown_booking_returns_404(self):
        resp = client.get(f"/guest/booking/{BAD_REF}", headers=HEADERS_OK)
        assert resp.status_code == 404

    def test_c4_response_includes_property_name(self):
        resp = client.get(f"/guest/booking/{GOOD_REF}", headers=HEADERS_OK)
        assert "property_name" in resp.json()

    def test_c5_response_includes_nights(self):
        resp = client.get(f"/guest/booking/{GOOD_REF}", headers=HEADERS_OK)
        assert resp.json()["nights"] == 5


# ---------------------------------------------------------------------------
# Group D — HTTP: GET /guest/booking/{ref}/wifi
# ---------------------------------------------------------------------------

class TestGroupDHttpWifi:

    def test_d1_wifi_endpoint_returns_200(self):
        resp = client.get(f"/guest/booking/{GOOD_REF}/wifi", headers=HEADERS_OK)
        assert resp.status_code == 200
        body = resp.json()
        assert "wifi_name" in body
        assert "wifi_password" in body

    def test_d2_wifi_invalid_token_returns_401(self):
        resp = client.get(f"/guest/booking/{GOOD_REF}/wifi", headers=HEADERS_BAD)
        assert resp.status_code == 401

    def test_d3_wifi_unknown_booking_returns_404(self):
        resp = client.get(f"/guest/booking/{BAD_REF}/wifi", headers=HEADERS_OK)
        assert resp.status_code == 404

    def test_d4_wifi_response_has_booking_ref(self):
        resp = client.get(f"/guest/booking/{GOOD_REF}/wifi", headers=HEADERS_OK)
        assert resp.json()["booking_ref"] == GOOD_REF


# ---------------------------------------------------------------------------
# Group E — HTTP: GET /guest/booking/{ref}/rules
# ---------------------------------------------------------------------------

class TestGroupEHttpRules:

    def test_e1_rules_endpoint_returns_200(self):
        resp = client.get(f"/guest/booking/{GOOD_REF}/rules", headers=HEADERS_OK)
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body["house_rules"], list)
        assert len(body["house_rules"]) > 0

    def test_e2_rules_invalid_token_returns_401(self):
        resp = client.get(f"/guest/booking/{GOOD_REF}/rules", headers=HEADERS_BAD)
        assert resp.status_code == 401

    def test_e3_rules_unknown_booking_returns_404(self):
        resp = client.get(f"/guest/booking/{BAD_REF}/rules", headers=HEADERS_OK)
        assert resp.status_code == 404

    def test_e4_rules_response_has_booking_ref(self):
        resp = client.get(f"/guest/booking/{GOOD_REF}/rules", headers=HEADERS_OK)
        assert resp.json()["booking_ref"] == GOOD_REF

    def test_e5_rules_contain_expected_content(self):
        resp = client.get(f"/guest/booking/{GOOD_REF}/rules", headers=HEADERS_OK)
        rules = resp.json()["house_rules"]
        # At least one rule contains "smoking" (from the DEMO stub)
        assert any("smoking" in r.lower() or "quiet" in r.lower() for r in rules)
