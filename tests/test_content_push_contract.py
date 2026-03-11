"""
Phase 250 — Booking.com Content API Adapter (Outbound)
Contract test suite.

Groups:
    A — build_content_payload happy path
    B — build_content_payload validation errors
    C — push_property_content dry_run
    D — push_property_content live (mocked HTTP 200)
    E — push_property_content live (mocked HTTP error)
    F — POST /admin/content/push/{property_id} — HTTP router
    G — POST validation errors via router
    H — Route registration
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from adapters.outbound.bookingcom_content import (
    PushResult,
    build_content_payload,
    push_property_content,
)
from main import app

client = TestClient(app)

_BEARER = {"Authorization": "Bearer test-token"}
_BASE = "/admin/content/push"
_PATCH_PUSH = "api.content_push_router.push_property_content"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _meta(**overrides):
    base = {
        "property_id": "prop-1",
        "bcom_hotel_id": "BH-001",
        "name": "Villa Serenity",
        "address": "123 Beach Rd",
        "city": "Koh Samui",
        "country_code": "TH",
        "description": "Stunning beachfront villa.",
        "cancellation_policy_code": "FLEX",
    }
    return {**base, **overrides}


def _ok_result(**kw):
    defaults = dict(
        property_id="prop-1", bcom_hotel_id="BH-001", success=True,
        status_code=200, fields_pushed=["address", "city", "name"], dry_run=False
    )
    return PushResult(**(defaults | kw))


# ---------------------------------------------------------------------------
# Group A — build_content_payload happy path
# ---------------------------------------------------------------------------

class TestGroupABuildPayload:
    def test_a1_required_fields_present(self):
        p = build_content_payload(_meta())
        for k in ("hotel_id", "name", "address", "city", "country_code"):
            assert k in p

    def test_a2_hotel_id_from_bcom_hotel_id(self):
        p = build_content_payload(_meta(bcom_hotel_id="BH-999"))
        assert p["hotel_id"] == "BH-999"

    def test_a3_hotel_id_fallback_to_external_id(self):
        m = _meta()
        del m["bcom_hotel_id"]
        p = build_content_payload({**m, "external_id": "EXT-42"})
        assert p["hotel_id"] == "EXT-42"

    def test_a4_country_code_uppercased(self):
        p = build_content_payload(_meta(country_code="th"))
        assert p["country_code"] == "TH"

    def test_a5_description_included(self):
        p = build_content_payload(_meta(description="Nice!"))
        assert p["description"] == "Nice!"

    def test_a6_description_truncated_at_2000(self):
        long_desc = "A" * 2500
        p = build_content_payload(_meta(description=long_desc))
        assert len(p["description"]) == 2000

    def test_a7_optional_fields_omitted_when_absent(self):
        p = build_content_payload(_meta())
        assert "amenities" not in p
        assert "photos" not in p

    def test_a8_amenities_included_as_ints(self):
        p = build_content_payload(_meta(amenities=["1", "2", 3]))
        assert p["amenities"] == [1, 2, 3]


# ---------------------------------------------------------------------------
# Group B — build_content_payload validation errors
# ---------------------------------------------------------------------------

class TestGroupBValidation:
    def test_b1_missing_hotel_id_raises(self):
        m = _meta()
        del m["bcom_hotel_id"]
        with pytest.raises(ValueError, match="bcom_hotel_id"):
            build_content_payload(m)

    def test_b2_missing_name_raises(self):
        with pytest.raises(ValueError, match="name"):
            build_content_payload(_meta(name=None))

    def test_b3_missing_address_raises(self):
        with pytest.raises(ValueError, match="address"):
            build_content_payload(_meta(address=None))

    def test_b4_invalid_country_code_raises(self):
        with pytest.raises(ValueError, match="country_code"):
            build_content_payload(_meta(country_code="THAI"))

    def test_b5_invalid_cancellation_code_raises(self):
        with pytest.raises(ValueError, match="cancellation_policy_code"):
            build_content_payload(_meta(cancellation_policy_code="UNKNOWN"))


# ---------------------------------------------------------------------------
# Group C — push dry_run
# ---------------------------------------------------------------------------

class TestGroupCDryRun:
    def test_c1_dry_run_success_true(self):
        r = push_property_content(_meta(), dry_run=True)
        assert r.success is True

    def test_c2_dry_run_flag_true(self):
        r = push_property_content(_meta(), dry_run=True)
        assert r.dry_run is True

    def test_c3_dry_run_no_status_code(self):
        r = push_property_content(_meta(), dry_run=True)
        assert r.status_code is None

    def test_c4_dry_run_fields_pushed_populated(self):
        r = push_property_content(_meta(), dry_run=True)
        assert len(r.fields_pushed) > 0


# ---------------------------------------------------------------------------
# Group D — push live — HTTP 200
# ---------------------------------------------------------------------------

class TestGroupDLiveOk:
    def _push(self):
        http = MagicMock()
        http.put.return_value.status_code = 200
        http.put.return_value.text = "OK"
        return push_property_content(_meta(), dry_run=False, _http_client=http)

    def test_d1_success_true(self):
        assert self._push().success is True

    def test_d2_status_code_200(self):
        assert self._push().status_code == 200

    def test_d3_no_error(self):
        assert self._push().error is None

    def test_d4_fields_pushed_populated(self):
        assert len(self._push().fields_pushed) > 0


# ---------------------------------------------------------------------------
# Group E — push live — HTTP error
# ---------------------------------------------------------------------------

class TestGroupELiveError:
    def _push(self, status=422):
        http = MagicMock()
        http.put.return_value.status_code = status
        http.put.return_value.text = "Unprocessable"
        return push_property_content(_meta(), dry_run=False, _http_client=http)

    def test_e1_success_false(self):
        assert self._push().success is False

    def test_e2_error_message_present(self):
        assert "422" in (self._push().error or "")

    def test_e3_fields_pushed_empty_on_error(self):
        assert self._push().fields_pushed == []


# ---------------------------------------------------------------------------
# Group F — HTTP router POST /admin/content/push/{id}
# ---------------------------------------------------------------------------

class TestGroupFRouter:
    def _post(self, meta=None, dry_run=False, result=None):
        r = result or _ok_result()
        with patch(_PATCH_PUSH, return_value=r):
            url = f"{_BASE}/prop-1"
            if dry_run:
                url += "?dry_run=true"
            return client.post(url, json=meta or _meta(), headers=_BEARER)

    def test_f1_returns_200(self):
        assert self._post().status_code == 200

    def test_f2_success_in_response(self):
        assert self._post().json()["success"] is True

    def test_f3_property_id_echoed(self):
        assert self._post().json()["property_id"] == "prop-1"

    def test_f4_fields_pushed_in_response(self):
        assert isinstance(self._post().json()["fields_pushed"], list)

    def test_f5_dry_run_propagated(self):
        r = _ok_result(dry_run=True, status_code=None)
        assert self._post(dry_run=True, result=r).json()["dry_run"] is True


# ---------------------------------------------------------------------------
# Group G — router validation errors
# ---------------------------------------------------------------------------

class TestGroupGRouterValidation:
    def test_g1_missing_hotel_id_400(self):
        bad = {"name": "V", "address": "A", "city": "C", "country_code": "TH"}
        r = client.post(f"{_BASE}/prop-1", json=bad, headers=_BEARER)
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Group H — Route registration
# ---------------------------------------------------------------------------

class TestGroupHRoutes:
    def test_h1_route_registered(self):
        routes = [r.path for r in app.routes]
        assert "/admin/content/push/{property_id}" in routes

    def test_h2_get_returns_405(self):
        # No GET defined — should 405
        r = client.get(f"{_BASE}/prop-1", headers=_BEARER)
        assert r.status_code == 405
