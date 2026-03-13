"""
Phase 485 — Guest Profile Backfill Tests

Tests for:
1. Guest profile backfill service — extraction from event payloads
2. Backfill API endpoint — POST /guests/backfill
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from adapters.ota.guest_profile_extractor import extract_guest_profile, GuestProfile


# ---------------------------------------------------------------------------
# Unit tests: extract_guest_profile
# ---------------------------------------------------------------------------

class TestGuestProfileExtractor:
    """Test that extract_guest_profile works across providers."""

    def test_airbnb_extraction(self):
        payload = {
            "guest": {"name": "John Doe", "email": "john@example.com", "phone": "+1234567890"},
        }
        profile = extract_guest_profile("airbnb", payload)
        assert profile.guest_name == "John Doe"
        assert profile.guest_email == "john@example.com"
        assert profile.guest_phone == "+1234567890"
        assert profile.source == "airbnb"

    def test_bookingcom_extraction(self):
        payload = {
            "booker": {"first_name": "Jane", "last_name": "Smith", "email": "jane@test.com"},
        }
        profile = extract_guest_profile("bookingcom", payload)
        assert profile.guest_name == "Jane Smith"
        assert profile.guest_email == "jane@test.com"
        assert profile.source == "bookingcom"

    def test_generic_provider_extraction(self):
        payload = {
            "guest": {"name": "Generic Guest", "email": "guest@hotel.com"},
        }
        profile = extract_guest_profile("hotelbeds", payload)
        assert profile.guest_name == "Generic Guest"
        assert profile.guest_email == "guest@hotel.com"
        assert profile.source == "hotelbeds"

    def test_empty_payload_returns_empty_profile(self):
        profile = extract_guest_profile("airbnb", {})
        assert profile.is_empty()

    def test_exception_returns_empty_profile(self):
        """Extractor never raises — returns empty profile on error."""
        profile = extract_guest_profile("airbnb", None)  # type: ignore
        assert profile.source == "airbnb"

    def test_profile_to_dict(self):
        profile = GuestProfile(
            guest_name="Test User",
            guest_email="test@example.com",
            guest_phone="+1000000000",
            source="airbnb",
        )
        d = profile.to_dict()
        assert d["guest_name"] == "Test User"
        assert d["guest_email"] == "test@example.com"
        assert d["guest_phone"] == "+1000000000"
        assert d["source"] == "airbnb"


# ---------------------------------------------------------------------------
# Unit tests: backfill service
# ---------------------------------------------------------------------------

class TestBackfillService:
    """Test backfill logic with mocked Supabase."""

    @patch("services.guest_profile_backfill._get_db")
    def test_backfill_dry_run(self, mock_get_db):
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        # Simulate event_log response with BOOKING_CREATED events
        mock_response = MagicMock()
        mock_response.data = [
            {
                "event_id": "evt1",
                "payload_json": {
                    "booking_id": "airbnb_123",
                    "tenant_id": "tenant_A",
                    "source": "airbnb",
                    "raw_payload": {
                        "guest": {"name": "John", "email": "john@test.com"},
                    },
                },
            },
        ]
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        from services.guest_profile_backfill import backfill_guest_profiles
        result = backfill_guest_profiles(tenant_id="tenant_A", dry_run=True)

        assert result["total_events"] == 1
        assert result["dry_run"] is True
        # In dry_run, no upsert should be called
        mock_db.table.return_value.upsert.assert_not_called()

    @patch("services.guest_profile_backfill._get_db")
    def test_backfill_skips_empty_profiles(self, mock_get_db):
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        mock_response = MagicMock()
        mock_response.data = [
            {
                "event_id": "evt2",
                "payload_json": {
                    "booking_id": "bk_456",
                    "tenant_id": "t1",
                    "source": "unknown",
                    "raw_payload": {},  # empty — no guest data
                },
            },
        ]
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        from services.guest_profile_backfill import backfill_guest_profiles
        result = backfill_guest_profiles(tenant_id="t1", dry_run=True)

        assert result["skipped_empty"] == 1
        assert result["extracted"] == 0


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

class TestBackfillEndpoint:
    """Test POST /guests/backfill via TestClient."""

    @pytest.fixture
    def client(self):
        """Create a TestClient with dev mode enabled."""
        import os
        os.environ.setdefault("IHOUSE_DEV_MODE", "true")
        os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
        os.environ.setdefault("SUPABASE_KEY", "test-key")
        os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
        os.environ.setdefault("IHOUSE_JWT_SECRET", "test-secret-key-minimum-32-chars-long")

        from main import app
        from starlette.testclient import TestClient
        return TestClient(app, raise_server_exceptions=False)

    @patch("services.guest_profile_backfill.backfill_guest_profiles")
    def test_backfill_endpoint_returns_200(self, mock_backfill, client):
        mock_backfill.return_value = {
            "total_events": 10,
            "extracted": 5,
            "skipped_empty": 3,
            "skipped_no_booking_id": 1,
            "errors": 1,
            "dry_run": False,
        }

        response = client.post("/guests/backfill?dry_run=false")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["total_events"] == 10
        assert data["extracted"] == 5

    @patch("services.guest_profile_backfill.backfill_guest_profiles")
    def test_backfill_dry_run_endpoint(self, mock_backfill, client):
        mock_backfill.return_value = {
            "total_events": 5,
            "extracted": 3,
            "skipped_empty": 2,
            "skipped_no_booking_id": 0,
            "errors": 0,
            "dry_run": True,
        }

        response = client.post("/guests/backfill?dry_run=true")
        assert response.status_code == 200
        data = response.json()
        assert data["dry_run"] is True
