"""
Phase 346 — Guest Portal + Owner Portal E2E Tests
===================================================

End-to-end tests for guest-facing and owner-facing portal endpoints.

Groups:
  A — Guest Portal booking overview  (GET /guest/booking/{ref})
  B — Guest Portal sub-endpoints     (wifi, rules)
  C — Guest Portal auth guards       (invalid/missing token)
  D — Owner Portal list properties   (GET /owner/portal)
  E — Owner Portal property summary  (GET /owner/portal/{id}/summary)
  F — Admin grant/revoke access      (POST + DELETE /admin/owner-access)
  G — Owner Portal access guards     (403 for unauthorized)

Design notes:
- Guest Portal: uses stub lookup (DEMO-001) — no real DB
- Owner Portal: mocked Supabase via patch on _get_db
- Guest endpoints: X-Guest-Token header required, no JWT
- Owner endpoints: JWT required (dev-mode → dev-tenant)
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

os.environ.setdefault("IHOUSE_ENV", "test")
os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("SUPABASE_URL", "http://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("IHOUSE_GUEST_TOKEN_SECRET", "test-guest-secret-long-enough-32b")

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from main import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)

TENANT_A = "dev-tenant"
PROP_ID = "prop-owner-001"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _query_chain(rows: list | None = None):
    q = MagicMock()
    for m in ("select", "eq", "gte", "lte", "lt", "neq", "in_", "is_",
              "limit", "order", "insert", "update", "upsert", "delete"):
        setattr(q, m, MagicMock(return_value=q))
    q.execute.return_value = MagicMock(data=rows if rows is not None else [])
    return q


def _owner_access_row(owner_id: str = TENANT_A, property_id: str = PROP_ID,
                       role: str = "owner", **overrides) -> dict:
    base = {
        "id": "access-001",
        "tenant_id": TENANT_A,
        "owner_id": owner_id,
        "property_id": property_id,
        "role": role,
        "granted_by": TENANT_A,
        "granted_at": "2026-03-12T00:00:00Z",
        "revoked_at": None,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Group A — Guest Portal Booking Overview
# ---------------------------------------------------------------------------

class TestGroupAGuestBookingOverview:
    """Test GET /guest/booking/{booking_ref} with stub lookup."""

    def test_a1_valid_token_returns_200_with_booking(self):
        """GET /guest/booking/DEMO-001 returns full booking view."""
        r = client.get(
            "/guest/booking/DEMO-001",
            headers={"x-guest-token": "valid-token-abc"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["booking_ref"] == "DEMO-001"
        assert body["property_name"] == "Villa Serenity"

    def test_a2_response_has_all_required_fields(self):
        """Booking view contains all guest-facing fields."""
        r = client.get(
            "/guest/booking/DEMO-001",
            headers={"x-guest-token": "valid-token"},
        )
        body = r.json()
        required = [
            "booking_ref", "property_name", "property_address",
            "check_in_date", "check_out_date", "check_in_time",
            "check_out_time", "status", "guest_name", "nights",
            "wifi_name", "wifi_password", "access_code",
            "house_rules", "emergency_contact",
        ]
        for key in required:
            assert key in body, f"Missing key: {key}"

    def test_a3_nights_is_correct(self):
        """Nights calculation matches check-in/check-out dates."""
        r = client.get(
            "/guest/booking/DEMO-001",
            headers={"x-guest-token": "valid-token"},
        )
        body = r.json()
        assert body["nights"] == 5  # 03-15 to 03-20

    def test_a4_house_rules_is_list(self):
        """House rules is returned as a list of strings."""
        r = client.get(
            "/guest/booking/DEMO-001",
            headers={"x-guest-token": "valid-token"},
        )
        body = r.json()
        assert isinstance(body["house_rules"], list)
        assert len(body["house_rules"]) == 3
        assert "No smoking" in body["house_rules"][0]


# ---------------------------------------------------------------------------
# Group B — Guest Portal Sub-Endpoints (WiFi, Rules)
# ---------------------------------------------------------------------------

class TestGroupBGuestSubEndpoints:

    def test_b1_wifi_returns_200_with_credentials(self):
        """GET /guest/booking/DEMO-001/wifi returns WiFi name and password."""
        r = client.get(
            "/guest/booking/DEMO-001/wifi",
            headers={"x-guest-token": "valid-token"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["wifi_name"] == "VillaSerenity_5G"
        assert body["wifi_password"] == "sunny2026"

    def test_b2_rules_returns_200_with_list(self):
        """GET /guest/booking/DEMO-001/rules returns house rules."""
        r = client.get(
            "/guest/booking/DEMO-001/rules",
            headers={"x-guest-token": "valid-token"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["booking_ref"] == "DEMO-001"
        assert isinstance(body["house_rules"], list)
        assert len(body["house_rules"]) >= 1

    def test_b3_wifi_for_unknown_booking_returns_404(self):
        """GET /guest/booking/UNKNOWN/wifi returns 404."""
        r = client.get(
            "/guest/booking/NONEXISTENT-999/wifi",
            headers={"x-guest-token": "valid-token"},
        )
        assert r.status_code == 404

    def test_b4_rules_for_unknown_booking_returns_404(self):
        """GET /guest/booking/UNKNOWN/rules returns 404."""
        r = client.get(
            "/guest/booking/NONEXISTENT-999/rules",
            headers={"x-guest-token": "valid-token"},
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Group C — Guest Portal Auth Guards
# ---------------------------------------------------------------------------

class TestGroupCGuestAuthGuards:

    def test_c1_invalid_token_returns_401(self):
        """Token starting with INVALID triggers 401."""
        r = client.get(
            "/guest/booking/DEMO-001",
            headers={"x-guest-token": "INVALID-bad-token"},
        )
        assert r.status_code == 401

    def test_c2_missing_token_header_returns_422(self):
        """Missing X-Guest-Token header returns 422."""
        r = client.get("/guest/booking/DEMO-001")
        assert r.status_code == 422

    def test_c3_empty_token_returns_401(self):
        """Empty string token is invalid → 401."""
        r = client.get(
            "/guest/booking/DEMO-001",
            headers={"x-guest-token": ""},
        )
        assert r.status_code == 401

    def test_c4_unknown_booking_returns_404(self):
        """Valid token but unknown booking → 404."""
        r = client.get(
            "/guest/booking/UNKNOWN-BOOKING",
            headers={"x-guest-token": "valid-token-xyz"},
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Group D — Owner Portal List Properties
# ---------------------------------------------------------------------------

class TestGroupDOwnerListProperties:

    def test_d1_list_with_properties_returns_200(self):
        """GET /owner/portal returns owner's accessible properties."""
        access_rows = [_owner_access_row()]
        with patch("api.owner_portal_router._get_db") as mock_db:
            db = MagicMock()
            db.table.return_value = _query_chain(access_rows)
            mock_db.return_value = db
            r = client.get("/owner/portal")
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 1
        assert body["properties"][0]["property_id"] == PROP_ID

    def test_d2_list_empty_returns_200_with_zero(self):
        """GET /owner/portal returns empty when owner has no access."""
        with patch("api.owner_portal_router._get_db") as mock_db:
            db = MagicMock()
            db.table.return_value = _query_chain([])
            mock_db.return_value = db
            r = client.get("/owner/portal")
        assert r.status_code == 200
        assert r.json()["count"] == 0

    def test_d3_properties_include_role_field(self):
        """Each property includes the owner's role (owner/viewer)."""
        access_rows = [_owner_access_row(role="viewer")]
        with patch("api.owner_portal_router._get_db") as mock_db:
            db = MagicMock()
            db.table.return_value = _query_chain(access_rows)
            mock_db.return_value = db
            r = client.get("/owner/portal")
        assert r.json()["properties"][0]["role"] == "viewer"


# ---------------------------------------------------------------------------
# Group E — Owner Portal Property Summary
# ---------------------------------------------------------------------------

class TestGroupEOwnerPropertySummary:

    def _make_summary_db(self, has_access=True, role="owner"):
        """Build mock DB for property summary endpoint."""
        db = MagicMock()
        access_row = _owner_access_row(role=role) if has_access else None

        def _table_side_effect(name: str):
            if name == "owner_portal_access":
                if has_access:
                    return _query_chain([access_row])
                return _query_chain([])
            if name == "booking_state":
                bookings = [
                    {"booking_id": "bk-1", "status": "confirmed",
                     "check_in_date": "2026-09-01", "check_out_date": "2026-09-05",
                     "source": "bookingcom", "booking_ref": "BK-001",
                     "property_id": PROP_ID},
                ]
                return _query_chain(bookings)
            if name == "booking_financial_facts":
                facts = [
                    {"booking_id": "bk-1", "gross_revenue": 1000.0,
                     "net_to_property": 900.0, "management_fee": 50.0,
                     "ota_commission": 100.0},
                ]
                return _query_chain(facts)
            return _query_chain([])

        db.table.side_effect = _table_side_effect
        return db

    def test_e1_owner_sees_full_summary(self):
        """GET /owner/portal/{id}/summary returns all data for owner role."""
        db = self._make_summary_db(has_access=True, role="owner")
        with patch("api.owner_portal_router._get_db", return_value=db):
            r = client.get(f"/owner/portal/{PROP_ID}/summary")
        assert r.status_code == 200
        body = r.json()
        assert body["property_id"] == PROP_ID
        assert body["role"] == "owner"
        assert "booking_counts" in body
        assert "upcoming_bookings" in body
        assert "occupancy" in body
        assert "financials" in body  # owner sees financials

    def test_e2_viewer_sees_no_financials(self):
        """GET /owner/portal/{id}/summary hides financials for viewer role."""
        db = self._make_summary_db(has_access=True, role="viewer")
        with patch("api.owner_portal_router._get_db", return_value=db):
            r = client.get(f"/owner/portal/{PROP_ID}/summary")
        assert r.status_code == 200
        body = r.json()
        assert body["role"] == "viewer"
        assert "financials" not in body

    def test_e3_no_access_returns_403(self):
        """GET /owner/portal/{id}/summary returns 403 without access."""
        db = self._make_summary_db(has_access=False)
        with patch("api.owner_portal_router._get_db", return_value=db):
            r = client.get(f"/owner/portal/{PROP_ID}/summary")
        assert r.status_code == 403

    def test_e4_booking_counts_present(self):
        """Summary includes booking count breakdown by status."""
        db = self._make_summary_db()
        with patch("api.owner_portal_router._get_db", return_value=db):
            r = client.get(f"/owner/portal/{PROP_ID}/summary")
        body = r.json()
        counts = body["booking_counts"]
        assert "total" in counts
        assert "confirmed" in counts

    def test_e5_occupancy_data_present(self):
        """Summary includes occupancy rate calculation."""
        db = self._make_summary_db()
        with patch("api.owner_portal_router._get_db", return_value=db):
            r = client.get(f"/owner/portal/{PROP_ID}/summary")
        body = r.json()
        occ = body["occupancy"]
        assert "occupancy_pct" in occ
        assert "period_days" in occ


# ---------------------------------------------------------------------------
# Group F — Admin Grant/Revoke Access
# ---------------------------------------------------------------------------

class TestGroupFAdminGrantRevoke:

    def test_f1_grant_access_returns_201(self):
        """POST /admin/owner-access grants access and returns 201."""
        row = _owner_access_row()
        with patch("api.owner_portal_router._get_db") as mock_db:
            db = MagicMock()
            db.table.return_value = _query_chain([row])
            mock_db.return_value = db
            r = client.post(
                "/admin/owner-access",
                json={"owner_id": TENANT_A, "property_id": PROP_ID, "role": "owner"},
            )
        assert r.status_code == 201
        assert r.json()["granted"] is True

    def test_f2_grant_invalid_role_returns_422(self):
        """POST /admin/owner-access rejects invalid role."""
        with patch("api.owner_portal_router._get_db") as mock_db:
            db = MagicMock()
            db.table.return_value = _query_chain([])
            mock_db.return_value = db
            with patch("services.guest_token.grant_owner_access",
                       side_effect=ValueError("Invalid role 'superadmin'")):
                r = client.post(
                    "/admin/owner-access",
                    json={"owner_id": TENANT_A, "property_id": PROP_ID, "role": "superadmin"},
                )
        assert r.status_code == 422

    def test_f3_grant_duplicate_returns_422(self):
        """POST /admin/owner-access rejects duplicate grant."""
        with patch("api.owner_portal_router._get_db") as mock_db, \
             patch("api.owner_portal_router.grant_owner_access",
                   side_effect=ValueError("already has access")):
            mock_db.return_value = MagicMock()
            r = client.post(
                "/admin/owner-access",
                json={"owner_id": TENANT_A, "property_id": PROP_ID, "role": "owner"},
            )
        assert r.status_code == 422

    def test_f4_revoke_access_returns_200(self):
        """DELETE /admin/owner-access/{owner_id}/{property_id} revokes access."""
        with patch("api.owner_portal_router._get_db") as mock_db:
            db = MagicMock()
            chain = _query_chain([{"id": "a1", "revoked_at": "2026-03-12T10:00:00Z"}])
            db.table.return_value = chain
            mock_db.return_value = db
            r = client.delete(f"/admin/owner-access/{TENANT_A}/{PROP_ID}")
        assert r.status_code == 200
        assert r.json()["revoked"] is True

    def test_f5_revoke_nonexistent_returns_404(self):
        """DELETE /admin/owner-access with no matching record returns 404."""
        with patch("api.owner_portal_router._get_db") as mock_db:
            db = MagicMock()
            chain = _query_chain([])
            db.table.return_value = chain
            mock_db.return_value = db
            r = client.delete(f"/admin/owner-access/unknown-owner/{PROP_ID}")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Group G — Owner Portal Access Guards
# ---------------------------------------------------------------------------

class TestGroupGOwnerAccessGuards:

    def test_g1_unauthenticated_owner_portal_returns_error(self):
        """GET /owner/portal without valid JWT returns non-200."""
        with patch.dict(os.environ, {"IHOUSE_DEV_MODE": ""}):
            r = client.get("/owner/portal")
        # Without dev-mode and no JWT, should fail (401/403/503 depending on env)
        assert r.status_code != 200

    def test_g2_grant_access_missing_fields_returns_422(self):
        """POST /admin/owner-access with missing fields returns 422."""
        r = client.post("/admin/owner-access", json={})
        assert r.status_code == 422

    def test_g3_revoke_body_is_path_params_only(self):
        """DELETE /admin/owner-access uses path params, no body needed."""
        with patch("api.owner_portal_router._get_db") as mock_db:
            db = MagicMock()
            db.table.return_value = _query_chain([{"id": "a1", "revoked_at": "now"}])
            mock_db.return_value = db
            r = client.delete(f"/admin/owner-access/{TENANT_A}/{PROP_ID}")
        assert r.status_code == 200
