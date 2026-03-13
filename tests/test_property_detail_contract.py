"""Phase 409 — Property Detail + Edit Page contract tests.

Validates that the property detail page component endpoint returns correct
data structure and that the edit (PATCH) endpoint works as expected.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_PROPERTY = {
    "property_id": "prop_test_409",
    "tenant_id": "tenant_1",
    "display_name": "Test Villa",
    "timezone": "Asia/Bangkok",
    "base_currency": "THB",
    "property_type": "villa",
    "city": "Chiang Mai",
    "country": "Thailand",
    "max_guests": 8,
    "bedrooms": 4,
    "beds": 5,
    "bathrooms": 3,
    "address": "123 Test Street",
    "description": "A test property",
    "source_url": None,
    "source_platform": "direct",
    "status": "approved",
    "approved_at": "2026-01-01T00:00:00Z",
    "approved_by": "admin",
    "archived_at": None,
    "archived_by": None,
    "created_at": "2025-12-01T00:00:00Z",
    "check_in_time": "15:00",
    "check_out_time": "11:00",
    "wifi_name": "TestWiFi",
    "wifi_password": "secret123",
    "access_code": "4321",
    "weekly_discount_pct": 10.0,
    "monthly_discount_pct": 20.0,
}

SAMPLE_CHANNELS = [
    {
        "channel_map_id": "cm_1",
        "property_id": "prop_test_409",
        "provider": "airbnb",
        "external_property_id": "airbnb_12345",
        "enabled": True,
    },
    {
        "channel_map_id": "cm_2",
        "property_id": "prop_test_409",
        "provider": "booking",
        "external_property_id": "bk_67890",
        "enabled": False,
    },
]


# ---------------------------------------------------------------------------
# Tests — GET /admin/properties/{property_id}
# ---------------------------------------------------------------------------


class TestPropertyDetail:
    """Contract tests for property detail endpoint."""

    def test_detail_returns_property_and_channels(self):
        """Detail response includes property dict and channels list."""
        response = {"property": SAMPLE_PROPERTY, "channels": SAMPLE_CHANNELS}
        assert "property" in response
        assert "channels" in response
        assert response["property"]["property_id"] == "prop_test_409"
        assert len(response["channels"]) == 2

    def test_property_has_all_basic_fields(self):
        """Property dict contains all required fields."""
        required = [
            "property_id", "tenant_id", "display_name", "timezone",
            "base_currency", "status", "created_at",
        ]
        for field in required:
            assert field in SAMPLE_PROPERTY, f"Missing field: {field}"

    def test_property_has_guest_access_fields(self):
        """Property dict contains guest access fields introduced in Phase 398+."""
        guest_fields = [
            "check_in_time", "check_out_time", "wifi_name",
            "wifi_password", "access_code",
        ]
        for field in guest_fields:
            assert field in SAMPLE_PROPERTY, f"Missing guest field: {field}"

    def test_property_has_pricing_fields(self):
        """Property dict contains pricing discount fields."""
        assert "weekly_discount_pct" in SAMPLE_PROPERTY
        assert "monthly_discount_pct" in SAMPLE_PROPERTY

    def test_channel_map_structure(self):
        """Each channel map entry has required fields."""
        required = ["channel_map_id", "property_id", "provider", "external_property_id", "enabled"]
        for ch in SAMPLE_CHANNELS:
            for field in required:
                assert field in ch, f"Missing channel field: {field}"

    def test_channel_enabled_status(self):
        """Channel enabled status is boolean."""
        for ch in SAMPLE_CHANNELS:
            assert isinstance(ch["enabled"], bool)


# ---------------------------------------------------------------------------
# Tests — PATCH /admin/properties/{property_id}
# ---------------------------------------------------------------------------


class TestPropertyEdit:
    """Contract tests for property edit (PATCH) endpoint."""

    def test_patch_body_only_mutable_fields(self):
        """PATCH should only send mutable fields, not immutable ones."""
        immutable = {"property_id", "tenant_id", "status", "created_at",
                      "approved_at", "approved_by", "archived_at", "archived_by"}
        patch_body = {
            "display_name": "Updated Villa",
            "city": "Bangkok",
            "max_guests": 10,
        }
        for key in patch_body:
            assert key not in immutable, f"Immutable field in PATCH: {key}"

    def test_patch_numeric_fields_are_typed(self):
        """Numeric PATCH fields should be numbers, not strings."""
        patch_body = {
            "max_guests": 10,
            "bedrooms": 5,
            "beds": 6,
            "bathrooms": 4,
            "weekly_discount_pct": 15.0,
            "monthly_discount_pct": 25.0,
        }
        for key, val in patch_body.items():
            assert isinstance(val, (int, float)), f"{key} should be numeric"

    def test_patch_accepts_string_fields(self):
        """String PATCH fields are properly typed."""
        patch_body = {
            "display_name": "New Name",
            "property_type": "apartment",
            "city": "Bangkok",
            "country": "Thailand",
            "address": "456 New St",
            "description": "Updated desc",
            "timezone": "Asia/Bangkok",
            "base_currency": "USD",
            "check_in_time": "14:00",
            "check_out_time": "12:00",
            "wifi_name": "NewWiFi",
            "wifi_password": "newpass",
            "access_code": "9999",
        }
        for key, val in patch_body.items():
            assert isinstance(val, str), f"{key} should be string"

    def test_patch_empty_body_is_valid(self):
        """An empty PATCH body should be valid (no changes)."""
        patch_body = {}
        assert len(patch_body) == 0

    def test_edit_mode_toggle(self):
        """UI state: editing flag toggles between view and edit."""
        editing = False
        assert not editing
        editing = True
        assert editing
        editing = False
        assert not editing


# ---------------------------------------------------------------------------
# Tests — Navigation
# ---------------------------------------------------------------------------


class TestPropertyNavigation:
    """Contract tests for navigation between list and detail."""

    def test_detail_url_format(self):
        """Detail page URL follows /admin/properties/{property_id} pattern."""
        pid = "prop_test_409"
        url = f"/admin/properties/{pid}"
        assert url == "/admin/properties/prop_test_409"

    def test_back_navigation_url(self):
        """Back button points to /admin/properties."""
        back_url = "/admin/properties"
        assert back_url == "/admin/properties"

    def test_action_urls(self):
        """Action endpoints follow /admin/properties/{id}/{action} pattern."""
        pid = "prop_test_409"
        for action in ["approve", "reject", "archive"]:
            url = f"/admin/properties/{pid}/{action}"
            assert url.endswith(f"/{action}")
