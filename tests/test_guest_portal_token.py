"""
Phase 400 — Guest Portal Token Endpoint — Contract Tests
==========================================================

Tests for GET /guest/portal/{token}:
    1. Valid token returns 200 with property data
    2. Invalid/malformed token returns 401
    3. Expired token returns 401
    4. Tampered token returns 401
"""
from __future__ import annotations

import os
import time
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("IHOUSE_JWT_SECRET", "test-secret-phase400")
    monkeypatch.setenv("IHOUSE_GUEST_TOKEN_SECRET", "guest-token-secret-32-bytes-ok!!")
    monkeypatch.setenv("IHOUSE_DEV_MODE", "true")
    monkeypatch.setenv("IHOUSE_DEV_PASSWORD", "dev")
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-key")


@pytest.fixture()
def client():
    from main import app
    from fastapi.testclient import TestClient
    return TestClient(app, raise_server_exceptions=False)


def _issue_test_token(booking_ref="BK-001", email="guest@test.com", ttl=3600):
    """Issue a valid guest token for testing."""
    from services.guest_token import issue_guest_token
    return issue_guest_token(booking_ref, email, ttl)


class TestGuestPortalByToken:
    """Tests for GET /guest/portal/{token}."""

    def test_valid_token_returns_200_with_fallback(self, client):
        """Valid token with no DB returns 200 with fallback minimal data."""
        raw_token, _ = _issue_test_token()

        # Mock supabase create_client to raise (simulating no DB)
        with patch("supabase.create_client", side_effect=Exception("no db")):
            resp = client.get(f"/guest/portal/{raw_token}")

        assert resp.status_code == 200
        body = resp.json()
        assert "property_name" in body
        assert body["check_in_time"] == "15:00"
        assert body["check_out_time"] == "11:00"

    def test_valid_token_with_db_returns_property_data(self, client):
        """Valid token + DB available returns real property data."""
        raw_token, _ = _issue_test_token(booking_ref="BK-100")

        mock_db = MagicMock()

        # is_guest_token_revoked returns False
        # Booking lookup
        mock_booking_result = MagicMock()
        mock_booking_result.data = [{"booking_id": "BK-100", "property_id": "prop-1", "check_in": "2026-03-15", "check_out": "2026-03-18", "status": "active", "source": "airbnb"}]

        # Property lookup
        mock_prop_result = MagicMock()
        mock_prop_result.data = [{"property_id": "prop-1", "name": "Villa Zen", "address": "123 Beach Rd", "wifi_name": "VillaZen_5G", "wifi_password": "zen2026", "check_in_time": "14:00", "check_out_time": "12:00", "house_rules": ["No smoking", "Quiet after 10pm"], "emergency_contact": "+66 80 111 2222", "welcome_message": "Welcome to paradise!"}]

        # Chain mocks for table calls
        call_count = [0]
        original_table = mock_db.table

        def table_side_effect(name):
            mock_table = MagicMock()
            if name == "guest_tokens":
                mock_select = MagicMock()
                mock_select.data = []  # No revocation record
                mock_table.select.return_value.eq.return_value.execute.return_value = mock_select
            elif name == "bookings":
                mock_table.select.return_value.eq.return_value.limit.return_value.execute.return_value = mock_booking_result
            elif name == "properties":
                mock_table.select.return_value.eq.return_value.limit.return_value.execute.return_value = mock_prop_result
            return mock_table

        mock_db.table = table_side_effect

        with patch("supabase.create_client", return_value=mock_db):
            resp = client.get(f"/guest/portal/{raw_token}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["property_name"] == "Villa Zen"
        assert body["wifi_name"] == "VillaZen_5G"
        assert body["wifi_password"] == "zen2026"
        assert body["check_in_time"] == "14:00"
        assert body["check_out_time"] == "12:00"
        assert len(body["house_rules"]) == 2
        assert body["emergency_contact"] == "+66 80 111 2222"
        assert body["welcome_message"] == "Welcome to paradise!"

    def test_malformed_token_returns_401(self, client):
        """Non-token string returns 401."""
        resp = client.get("/guest/portal/not-a-real-token")
        assert resp.status_code == 401

    def test_expired_token_returns_401(self, client):
        """Expired token returns 401."""
        raw_token, _ = _issue_test_token(ttl=-10)
        resp = client.get(f"/guest/portal/{raw_token}")
        assert resp.status_code == 401
        assert resp.json()["error"] == "TOKEN_EXPIRED"

    def test_tampered_token_returns_401(self, client):
        """Tampered token returns 401."""
        raw_token, _ = _issue_test_token()
        tampered = raw_token[:-3] + "XXX"
        resp = client.get(f"/guest/portal/{tampered}")
        assert resp.status_code == 401

    def test_no_pii_leakage_in_error(self, client):
        """Invalid token error response contains no PII."""
        resp = client.get("/guest/portal/invalid-token-abc")
        body = resp.json()
        assert "guest" not in body.get("message", "").lower() or "link" in body.get("message", "").lower()
        # Should only say "invalid" or "malformed", never leak booking/guest info
        assert "booking" not in body.get("message", "").lower()
