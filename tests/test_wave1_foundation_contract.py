"""
Phases 586–605 — Wave 1 Foundation Contract Tests

Tests for all Wave 1 API routers:
    - Property Location (Phase 586)
    - Check-in/out Times + Deposit + House Rules (Phases 587-590)
    - Reference & Marketing Photos (Phases 591-592)
    - Amenities (Phase 593)
    - Extras Catalog (Phase 596)
    - Property-Extras Mapping (Phase 597)
    - Problem Reports (Phase 598)
    - Owner Visibility (Phase 604)
"""
from __future__ import annotations

from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import main

_TENANT = "tenant-wave1-test"


def _make_client() -> TestClient:
    return TestClient(main.app)


def _auth_header() -> dict:
    return {"Authorization": "Bearer mock-token"}


# ---------------------------------------------------------------------------
# Mock DB helpers
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


def _prop_db(extra_tables=None):
    """DB with a property row."""
    prop = {
        "id": "uuid-1", "property_id": "prop-1", "tenant_id": _TENANT,
        "display_name": "Test Villa", "timezone": "UTC", "base_currency": "USD",
        "latitude": 13.756, "longitude": 100.501, "gps_source": "manual",
        "house_rules": [{"text": "No smoking"}],
        "checkin_time": "15:00", "checkout_time": "11:00",
    }
    tables = {"properties": _MockTable([prop])}
    if extra_tables:
        tables.update(extra_tables)
    return _MockDB(tables)


# ===========================================================================
# Phase 586 — Property Location
# ===========================================================================

class TestPropertyLocation:

    def test_save_location_success(self):
        with patch("api.property_location_router._get_supabase_client", return_value=_prop_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/properties/prop-1/save-location",
                json={"latitude": 13.756, "longitude": 100.501, "source": "device"},
                headers=_auth_header(),
            )
        assert resp.status_code == 200
        assert resp.json()["saved"] is True

    def test_save_location_missing_coords(self):
        with patch("api.property_location_router._get_supabase_client", return_value=_prop_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/properties/prop-1/save-location",
                json={"latitude": 13.756},
                headers=_auth_header(),
            )
        assert resp.status_code == 400

    def test_save_location_invalid_range(self):
        with patch("api.property_location_router._get_supabase_client", return_value=_prop_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/properties/prop-1/save-location",
                json={"latitude": 200, "longitude": 100},
                headers=_auth_header(),
            )
        assert resp.status_code == 400

    def test_get_location(self):
        with patch("api.property_location_router._get_supabase_client", return_value=_prop_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get("/properties/prop-1/location", headers=_auth_header())
        assert resp.status_code == 200
        body = resp.json()
        assert body["latitude"] == 13.756
        assert "maps.google.com" in body["map_url"]

    def test_get_location_not_found(self):
        with patch("api.property_location_router._get_supabase_client", return_value=_MockDB()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get("/properties/prop-missing/location", headers=_auth_header())
        assert resp.status_code == 404


# ===========================================================================
# Phase 589 — House Rules
# ===========================================================================

class TestHouseRules:

    def test_set_house_rules(self):
        with patch("api.property_house_rules_router._get_supabase_client", return_value=_prop_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().put(
                "/properties/prop-1/house-rules",
                json={"rules": [{"text": "No smoking"}, {"text": "Quiet hours 22:00-08:00"}]},
                headers=_auth_header(),
            )
        assert resp.status_code == 200
        assert resp.json()["count"] == 2

    def test_set_house_rules_invalid(self):
        with patch("api.property_house_rules_router._get_supabase_client", return_value=_prop_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().put(
                "/properties/prop-1/house-rules",
                json={"rules": "not a list"},
                headers=_auth_header(),
            )
        assert resp.status_code == 400

    def test_get_house_rules(self):
        with patch("api.property_house_rules_router._get_supabase_client", return_value=_prop_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get("/properties/prop-1/house-rules", headers=_auth_header())
        assert resp.status_code == 200


# ===========================================================================
# Phases 591-592 — Property Photos
# ===========================================================================

class TestPropertyPhotos:

    def test_add_reference_photo(self):
        with patch("api.property_photos_router._get_supabase_client", return_value=_prop_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/properties/prop-1/reference-photos",
                json={"photo_url": "https://storage.example.com/img1.jpg", "room_label": "Living Room"},
                headers=_auth_header(),
            )
        assert resp.status_code == 201

    def test_add_reference_photo_missing_room_label(self):
        with patch("api.property_photos_router._get_supabase_client", return_value=_prop_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/properties/prop-1/reference-photos",
                json={"photo_url": "https://storage.example.com/img1.jpg"},
                headers=_auth_header(),
            )
        assert resp.status_code == 400

    def test_list_reference_photos(self):
        with patch("api.property_photos_router._get_supabase_client", return_value=_prop_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get("/properties/prop-1/reference-photos", headers=_auth_header())
        assert resp.status_code == 200

    def test_add_marketing_photo(self):
        with patch("api.property_photos_router._get_supabase_client", return_value=_prop_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/properties/prop-1/marketing-photos",
                json={"photo_url": "https://storage.example.com/mkt1.jpg", "caption": "Pool view"},
                headers=_auth_header(),
            )
        assert resp.status_code == 201

    def test_list_marketing_photos(self):
        with patch("api.property_photos_router._get_supabase_client", return_value=_prop_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get("/properties/prop-1/marketing-photos", headers=_auth_header())
        assert resp.status_code == 200


# ===========================================================================
# Phase 593 — Amenities
# ===========================================================================

class TestAmenities:

    def test_upsert_amenities(self):
        with patch("api.property_amenities_router._get_supabase_client", return_value=_prop_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/properties/prop-1/amenities",
                json={"amenities": [
                    {"amenity_key": "wifi", "category": "general"},
                    {"amenity_key": "pool", "category": "outdoor"},
                ]},
                headers=_auth_header(),
            )
        assert resp.status_code == 200
        assert resp.json()["count"] == 2

    def test_upsert_amenities_empty(self):
        with patch("api.property_amenities_router._get_supabase_client", return_value=_prop_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/properties/prop-1/amenities",
                json={"amenities": []},
                headers=_auth_header(),
            )
        assert resp.status_code == 400

    def test_list_amenities(self):
        with patch("api.property_amenities_router._get_supabase_client", return_value=_prop_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get("/properties/prop-1/amenities", headers=_auth_header())
        assert resp.status_code == 200


# ===========================================================================
# Phase 596 — Extras Catalog
# ===========================================================================

class TestExtrasCatalog:

    def test_create_extra(self):
        with patch("api.extras_catalog_router._get_supabase_client", return_value=_MockDB({"extras_catalog": _MockTable()})), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/extras/",
                json={"name": "Airport Transfer", "category": "transport", "default_price": 1500},
                headers=_auth_header(),
            )
        assert resp.status_code == 201

    def test_create_extra_missing_name(self):
        with patch("api.extras_catalog_router._get_supabase_client", return_value=_MockDB()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post("/extras/", json={}, headers=_auth_header())
        assert resp.status_code == 400

    def test_list_extras(self):
        with patch("api.extras_catalog_router._get_supabase_client", return_value=_MockDB({"extras_catalog": _MockTable([{"id": "1", "name": "Transfer"}])})), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get("/extras/", headers=_auth_header())
        assert resp.status_code == 200
        assert resp.json()["count"] >= 0

    def test_get_extra(self):
        with patch("api.extras_catalog_router._get_supabase_client", return_value=_MockDB({"extras_catalog": _MockTable([{"id": "1", "name": "Transfer"}])})), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get("/extras/1", headers=_auth_header())
        assert resp.status_code == 200

    def test_get_extra_not_found(self):
        with patch("api.extras_catalog_router._get_supabase_client", return_value=_MockDB()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get("/extras/missing", headers=_auth_header())
        assert resp.status_code == 404


# ===========================================================================
# Phase 597 — Property-Extras Mapping
# ===========================================================================

class TestPropertyExtras:

    def test_add_property_extras(self):
        with patch("api.property_extras_router._get_supabase_client", return_value=_prop_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/properties/prop-1/extras",
                json={"extras": [{"extra_id": "uuid-extra-1"}]},
                headers=_auth_header(),
            )
        assert resp.status_code == 200
        assert len(resp.json()["registered"]) == 1

    def test_add_property_extras_empty(self):
        with patch("api.property_extras_router._get_supabase_client", return_value=_prop_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/properties/prop-1/extras", json={"extras": []}, headers=_auth_header(),
            )
        assert resp.status_code == 400

    def test_list_property_extras(self):
        with patch("api.property_extras_router._get_supabase_client", return_value=_prop_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get("/properties/prop-1/extras", headers=_auth_header())
        assert resp.status_code == 200


# ===========================================================================
# Phase 598 — Problem Reports
# ===========================================================================

class TestProblemReports:

    def test_create_problem_report(self):
        with patch("api.problem_report_router._get_supabase_client", return_value=_MockDB({"problem_reports": _MockTable()})), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/problem-reports/",
                json={
                    "property_id": "prop-1", "reported_by": "worker-1",
                    "category": "plumbing", "description": "Toilet leaking",
                },
                headers=_auth_header(),
            )
        assert resp.status_code == 201

    def test_create_report_missing_category(self):
        with patch("api.problem_report_router._get_supabase_client", return_value=_MockDB()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/problem-reports/",
                json={"property_id": "prop-1", "reported_by": "w1", "description": "Leak"},
                headers=_auth_header(),
            )
        assert resp.status_code == 400

    def test_create_report_invalid_category(self):
        with patch("api.problem_report_router._get_supabase_client", return_value=_MockDB()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/problem-reports/",
                json={"property_id": "p1", "reported_by": "w1", "category": "aliens", "description": "X"},
                headers=_auth_header(),
            )
        assert resp.status_code == 400

    def test_list_problem_reports(self):
        with patch("api.problem_report_router._get_supabase_client", return_value=_MockDB({"problem_reports": _MockTable([{"id": "r1"}])})), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get("/problem-reports/", headers=_auth_header())
        assert resp.status_code == 200

    def test_get_problem_report(self):
        with patch("api.problem_report_router._get_supabase_client", return_value=_MockDB({"problem_reports": _MockTable([{"id": "r1"}])})), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get("/problem-reports/r1", headers=_auth_header())
        assert resp.status_code == 200

    def test_update_problem_report_status(self):
        with patch("api.problem_report_router._get_supabase_client", return_value=_MockDB({"problem_reports": _MockTable([{"id": "r1", "status": "open"}])})), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().patch(
                "/problem-reports/r1",
                json={"status": "resolved", "resolved_by": "worker-2", "resolution_notes": "Fixed pipe"},
                headers=_auth_header(),
            )
        assert resp.status_code == 200

    def test_add_report_photo(self):
        with patch("api.problem_report_router._get_supabase_client", return_value=_MockDB({"problem_report_photos": _MockTable()})), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().post(
                "/problem-reports/r1/photos",
                json={"photo_url": "https://storage.example.com/leak.jpg"},
                headers=_auth_header(),
            )
        assert resp.status_code == 201

    def test_list_report_photos(self):
        with patch("api.problem_report_router._get_supabase_client", return_value=_MockDB({"problem_report_photos": _MockTable()})), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get("/problem-reports/r1/photos", headers=_auth_header())
        assert resp.status_code == 200


# ===========================================================================
# Phase 604 — Owner Visibility
# ===========================================================================

class TestOwnerVisibility:

    def test_get_visibility_defaults(self):
        with patch("api.owner_visibility_router._get_supabase_client", return_value=_MockDB()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().get("/owner/visibility/prop-1", headers=_auth_header())
        assert resp.status_code == 200
        body = resp.json()
        assert body["is_default"] is True
        assert "booking_count" in body["visible_fields"]

    def test_set_visibility(self):
        with patch("api.owner_visibility_router._get_supabase_client", return_value=_MockDB({"owner_visibility_settings": _MockTable()})), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().put(
                "/owner/visibility/prop-1",
                json={"visible_fields": {"booking_count": True, "revenue": True}, "owner_user_id": "owner-1"},
                headers=_auth_header(),
            )
        assert resp.status_code == 200
        assert resp.json()["saved"] is True

    def test_set_visibility_missing_fields(self):
        with patch("api.owner_visibility_router._get_supabase_client", return_value=_MockDB()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().put(
                "/owner/visibility/prop-1",
                json={"visible_fields": "not_dict"},
                headers=_auth_header(),
            )
        assert resp.status_code == 400


# ===========================================================================
# Phases 587-590 — Properties Router extended fields
# ===========================================================================

class TestPropertiesExtendedFields:

    def test_patch_checkin_checkout_times(self):
        with patch("api.properties_router._get_supabase_client", return_value=_prop_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().patch(
                "/properties/prop-1",
                json={"checkin_time": "14:00", "checkout_time": "10:00"},
                headers=_auth_header(),
            )
        assert resp.status_code == 200

    def test_patch_deposit_config(self):
        with patch("api.properties_router._get_supabase_client", return_value=_prop_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().patch(
                "/properties/prop-1",
                json={"deposit_required": True, "deposit_amount": 5000, "deposit_currency": "THB"},
                headers=_auth_header(),
            )
        assert resp.status_code == 200

    def test_patch_property_details(self):
        with patch("api.properties_router._get_supabase_client", return_value=_prop_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            resp = _make_client().patch(
                "/properties/prop-1",
                json={
                    "door_code": "1234", "wifi_name": "VillaNet",
                    "wifi_password": "secret", "parking_info": "Behind building",
                },
                headers=_auth_header(),
            )
        assert resp.status_code == 200

    def test_format_property_includes_new_fields(self):
        from api.properties_router import _format_property
        row = {
            "id": "1", "property_id": "p1", "tenant_id": "t1",
            "display_name": "V", "timezone": "UTC", "base_currency": "USD",
            "latitude": 13.0, "longitude": 100.0, "gps_source": "manual",
            "checkin_time": "15:00", "checkout_time": "11:00",
            "deposit_required": True, "deposit_amount": 5000,
            "door_code": "1234", "wifi_name": "Net",
        }
        result = _format_property(row)
        assert result["latitude"] == 13.0
        assert result["checkin_time"] == "15:00"
        assert result["deposit_required"] is True
        assert result["door_code"] == "1234"


# ===========================================================================
# Phase 616 — i18n Labels
# ===========================================================================

class TestI18nLabels:

    def test_english_labels(self):
        from i18n.checkin_form_labels import get_labels
        labels = get_labels("en")
        assert labels["page_title"] == "Guest Check-in Form"
        assert "full_name" in labels

    def test_thai_labels(self):
        from i18n.checkin_form_labels import get_labels
        labels = get_labels("th")
        assert "แบบฟอร์ม" in labels["page_title"]

    def test_hebrew_labels(self):
        from i18n.checkin_form_labels import get_labels
        labels = get_labels("he")
        assert "טופס" in labels["page_title"]

    def test_fallback_to_english(self):
        from i18n.checkin_form_labels import get_labels
        labels = get_labels("xx")
        assert labels["page_title"] == "Guest Check-in Form"

    def test_tourist_requires_passport(self):
        from i18n.checkin_form_labels import get_required_fields
        fields = get_required_fields("tourist")
        assert "passport_photo" in fields
        assert "nationality" in fields

    def test_resident_minimal_fields(self):
        from i18n.checkin_form_labels import get_required_fields
        fields = get_required_fields("resident")
        assert "passport_photo" not in fields
        assert "full_name" in fields
