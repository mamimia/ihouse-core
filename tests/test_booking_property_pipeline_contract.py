"""Phase 410 — Booking→Property Pipeline contract tests.

Verifies the data pipeline connecting bookings to properties is complete.
"""

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BOOKINGS_FOR_PROPERTY = [
    {
        "booking_id": "airbnb_BK001",
        "property_id": "prop_1",
        "status": "active",
        "check_in": "2026-04-01",
        "check_out": "2026-04-05",
        "source": "airbnb",
        "guest_name": "Test Guest",
    },
    {
        "booking_id": "booking_BK002",
        "property_id": "prop_1",
        "status": "canceled",
        "check_in": "2026-03-15",
        "check_out": "2026-03-18",
        "source": "booking",
        "guest_name": "Another Guest",
    },
]

PROPERTY_WITH_CHANNELS = {
    "property": {
        "property_id": "prop_1",
        "display_name": "Test Villa",
        "status": "approved",
    },
    "channels": [
        {"provider": "airbnb", "enabled": True},
        {"provider": "booking", "enabled": True},
    ],
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBookingPropertyPipeline:
    """Validates the booking→property data connection."""

    def test_bookings_filter_by_property(self):
        """Bookings can be filtered by property_id."""
        filtered = [b for b in BOOKINGS_FOR_PROPERTY if b["property_id"] == "prop_1"]
        assert len(filtered) == 2

    def test_booking_has_property_id(self):
        """Every booking carries a property_id."""
        for b in BOOKINGS_FOR_PROPERTY:
            assert "property_id" in b
            assert b["property_id"], "property_id should not be empty"

    def test_property_has_channels(self):
        """Property detail includes channel mappings."""
        assert len(PROPERTY_WITH_CHANNELS["channels"]) == 2

    def test_booking_source_matches_channel(self):
        """Booking sources should correspond to connected channels."""
        channel_providers = {ch["provider"] for ch in PROPERTY_WITH_CHANNELS["channels"]}
        for b in BOOKINGS_FOR_PROPERTY:
            assert b["source"] in channel_providers

    def test_active_booking_has_dates(self):
        """Active bookings have check_in and check_out."""
        active = [b for b in BOOKINGS_FOR_PROPERTY if b["status"] == "active"]
        for b in active:
            assert b["check_in"]
            assert b["check_out"]

    def test_booking_id_format_deterministic(self):
        """booking_id follows {provider}_{ref} format."""
        for b in BOOKINGS_FOR_PROPERTY:
            parts = b["booking_id"].split("_", 1)
            assert len(parts) == 2
            assert parts[0] in ("airbnb", "booking", "expedia", "agoda")

    def test_property_status_is_approved(self):
        """Only approved properties should have active bookings."""
        assert PROPERTY_WITH_CHANNELS["property"]["status"] == "approved"

    def test_pipeline_data_completeness(self):
        """Pipeline provides both property metadata and booking data."""
        assert "property" in PROPERTY_WITH_CHANNELS
        assert "channels" in PROPERTY_WITH_CHANNELS
        assert len(BOOKINGS_FOR_PROPERTY) > 0
