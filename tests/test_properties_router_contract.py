"""
Phase 156 — Contract Tests: Property Metadata Router

Tests:
  A — GET /properties: empty list, count=0
  B — GET /properties: returns all properties for tenant
  C — POST /properties: valid create → 201
  D — POST /properties: missing property_id → 400
  E — POST /properties: invalid base_currency → 400
  F — POST /properties: duplicate property_id → 409
  G — GET /properties/{property_id}: found → 200
  H — GET /properties/{property_id}: not found → 404
  I — GET /properties/{property_id}: tenant isolation (other tenant's property → 404)
  J — PATCH /properties/{property_id}: update display_name → 200
  K — PATCH /properties/{property_id}: update timezone → 200
  L — PATCH /properties/{property_id}: update base_currency → 200
  M — PATCH /properties/{property_id}: invalid currency → 400
  N — PATCH /properties/{property_id}: not found → 404
  O — PATCH /properties/{property_id}: empty body → 400
  P — _format_property: all fields present
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fastapi.testclient import TestClient

# We need a minimal FastAPI app, avoid loading main.py (which tries to connect to Supabase)
from fastapi import FastAPI
from api.properties_router import router, _format_property

_app = FastAPI()
_app.include_router(router)


# ---------------------------------------------------------------------------
# Auth helper — bypass jwt_auth for all tests
# ---------------------------------------------------------------------------

from api.auth import jwt_auth  # noqa: E402

def _override_auth():
    return "tenant-test"

_app.dependency_overrides[jwt_auth] = _override_auth
_client = TestClient(_app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Mock DB factory
# ---------------------------------------------------------------------------

def _mock_db(
    list_data: list | None = None,
    insert_data: list | None = None,
    update_data: list | None = None,
    raise_exc: Exception | None = None,
    raise_on: str = "execute",
):
    """
    Returns a mock Supabase-style client with chainable builder pattern.
    """
    def _make_result(data):
        m = MagicMock()
        m.data = data if data is not None else []
        return m

    db = MagicMock()

    # We need to handle both .select().eq()...execute() and .insert().execute() chains.
    # Use a universal chain mock:
    chain = MagicMock()

    if raise_exc is not None:
        chain.execute.side_effect = raise_exc
    else:
        # Default to returning list_data for selects, insert_data for inserts, etc.
        chain.execute.return_value = _make_result(list_data or [])

    # All table operations return the same chain
    chain.select.return_value = chain
    chain.insert.return_value = chain
    chain.update.return_value = chain
    chain.delete.return_value = chain
    chain.eq.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain

    db.table.return_value = chain
    return db, chain


def _make_property_row(
    property_id: str = "prop-001",
    tenant_id: str = "tenant-test",
    display_name: str = "Villa Test",
    timezone: str = "UTC",
    base_currency: str = "USD",
) -> dict:
    return {
        "id": 1,
        "property_id":   property_id,
        "tenant_id":     tenant_id,
        "display_name":  display_name,
        "timezone":      timezone,
        "base_currency": base_currency,
        "created_at":    "2025-01-01T00:00:00Z",
        "updated_at":    "2025-01-01T00:00:00Z",
    }


# ===========================================================================
# Group A — GET /properties: empty list
# ===========================================================================

class TestGroupA_ListEmpty:

    def test_a1_empty_returns_200(self, monkeypatch):
        db, _ = _mock_db(list_data=[])
        monkeypatch.setattr("api.properties_router._get_supabase_client", lambda: db)
        resp = _client.get("/properties")
        assert resp.status_code == 200

    def test_a2_empty_count_is_zero(self, monkeypatch):
        db, _ = _mock_db(list_data=[])
        monkeypatch.setattr("api.properties_router._get_supabase_client", lambda: db)
        data = _client.get("/properties").json()
        assert data["count"] == 0

    def test_a3_empty_properties_list(self, monkeypatch):
        db, _ = _mock_db(list_data=[])
        monkeypatch.setattr("api.properties_router._get_supabase_client", lambda: db)
        data = _client.get("/properties").json()
        assert data["properties"] == []

    def test_a4_tenant_id_in_response(self, monkeypatch):
        db, _ = _mock_db(list_data=[])
        monkeypatch.setattr("api.properties_router._get_supabase_client", lambda: db)
        data = _client.get("/properties").json()
        assert data["tenant_id"] == "tenant-test"


# ===========================================================================
# Group B — GET /properties: returns all properties
# ===========================================================================

class TestGroupB_ListProperties:

    def test_b1_returns_two_properties(self, monkeypatch):
        rows = [
            _make_property_row("prop-001"),
            _make_property_row("prop-002"),
        ]
        db, _ = _mock_db(list_data=rows)
        monkeypatch.setattr("api.properties_router._get_supabase_client", lambda: db)
        data = _client.get("/properties").json()
        assert data["count"] == 2
        assert len(data["properties"]) == 2

    def test_b2_property_fields_present(self, monkeypatch):
        db, _ = _mock_db(list_data=[_make_property_row()])
        monkeypatch.setattr("api.properties_router._get_supabase_client", lambda: db)
        prop = _client.get("/properties").json()["properties"][0]
        for field in ("property_id", "tenant_id", "display_name", "timezone", "base_currency"):
            assert field in prop


# ===========================================================================
# Group C — POST /properties: valid create → 201
# ===========================================================================

class TestGroupC_CreateProperty:

    def test_c1_creates_with_all_fields(self, monkeypatch):
        row = _make_property_row("prop-new", display_name="New Villa", timezone="Asia/Bangkok", base_currency="THB")
        db, chain = _mock_db()
        chain.execute.return_value = MagicMock(data=[row])
        monkeypatch.setattr("api.properties_router._get_supabase_client", lambda: db)
        resp = _client.post("/properties", json={
            "property_id":   "prop-new",
            "display_name":  "New Villa",
            "timezone":      "Asia/Bangkok",
            "base_currency": "THB",
        })
        assert resp.status_code == 201

    def test_c2_creates_with_only_property_id(self, monkeypatch):
        row = _make_property_row("prop-minimal")
        db, chain = _mock_db()
        chain.execute.return_value = MagicMock(data=[row])
        monkeypatch.setattr("api.properties_router._get_supabase_client", lambda: db)
        resp = _client.post("/properties", json={"property_id": "prop-minimal"})
        assert resp.status_code == 201

    def test_c3_response_has_property_id(self, monkeypatch):
        row = _make_property_row("prop-resp")
        db, chain = _mock_db()
        chain.execute.return_value = MagicMock(data=[row])
        monkeypatch.setattr("api.properties_router._get_supabase_client", lambda: db)
        data = _client.post("/properties", json={"property_id": "prop-resp"}).json()
        assert data["property_id"] == "prop-resp"


# ===========================================================================
# Group D — POST /properties: validation errors
# ===========================================================================

class TestGroupD_CreateValidation:

    def test_d1_missing_property_id_auto_generates(self, monkeypatch):
        """property_id is now auto-generated when absent → 201."""
        row = _make_property_row("KPG-500")
        db, chain = _mock_db()
        chain.execute.return_value = MagicMock(data=[row])
        # Auto-gen calls multiple queries (config + max id)
        monkeypatch.setattr("api.properties_router._get_supabase_client", lambda: db)
        resp = _client.post("/properties", json={"display_name": "No ID"})
        assert resp.status_code == 201

    def test_d2_whitespace_property_id_auto_generates(self, monkeypatch):
        """Whitespace-only property_id is treated as absent → auto-gen → 201."""
        row = _make_property_row("KPG-500")
        db, chain = _mock_db()
        chain.execute.return_value = MagicMock(data=[row])
        monkeypatch.setattr("api.properties_router._get_supabase_client", lambda: db)
        resp = _client.post("/properties", json={"property_id": "  "})
        assert resp.status_code == 201

    def test_d3_non_dict_body_returns_400(self, monkeypatch):
        db, _ = _mock_db()
        monkeypatch.setattr("api.properties_router._get_supabase_client", lambda: db)
        resp = _client.post("/properties", content=b"not-json", headers={"Content-Type": "application/json"})
        assert resp.status_code in (400, 422)


# ===========================================================================
# Group E — POST /properties: invalid base_currency
# ===========================================================================

class TestGroupE_InvalidCurrency:

    def test_e1_invalid_currency_returns_400(self, monkeypatch):
        db, _ = _mock_db()
        monkeypatch.setattr("api.properties_router._get_supabase_client", lambda: db)
        resp = _client.post("/properties", json={"property_id": "p1", "base_currency": "INVALID"})
        assert resp.status_code == 400

    def test_e2_error_message_mentions_currency(self, monkeypatch):
        db, _ = _mock_db()
        monkeypatch.setattr("api.properties_router._get_supabase_client", lambda: db)
        data = _client.post("/properties", json={"property_id": "p1", "base_currency": "XXX"}).json()
        assert "base_currency" in str(data).lower() or "currency" in str(data).lower()

    def test_e3_valid_currencies_accepted(self, monkeypatch):
        row = _make_property_row("p-eur", base_currency="EUR")
        db, chain = _mock_db()
        chain.execute.return_value = MagicMock(data=[row])
        monkeypatch.setattr("api.properties_router._get_supabase_client", lambda: db)
        resp = _client.post("/properties", json={"property_id": "p-eur", "base_currency": "EUR"})
        assert resp.status_code == 201


# ===========================================================================
# Group F — POST /properties: duplicate → 409
# ===========================================================================

class TestGroupF_Duplicate:

    def test_f1_duplicate_returns_409(self, monkeypatch):
        db, chain = _mock_db()
        chain.execute.side_effect = Exception("duplicate key value violates unique constraint 23505")
        monkeypatch.setattr("api.properties_router._get_supabase_client", lambda: db)
        resp = _client.post("/properties", json={"property_id": "prop-dup"})
        assert resp.status_code == 409


# ===========================================================================
# Group G — GET /properties/{property_id}: found
# ===========================================================================

class TestGroupG_GetProperty:

    def test_g1_found_returns_200(self, monkeypatch):
        row = _make_property_row("prop-g1")
        db, chain = _mock_db()
        chain.execute.return_value = MagicMock(data=[row])
        monkeypatch.setattr("api.properties_router._get_supabase_client", lambda: db)
        resp = _client.get("/properties/prop-g1")
        assert resp.status_code == 200

    def test_g2_response_has_correct_property_id(self, monkeypatch):
        row = _make_property_row("prop-g2")
        db, chain = _mock_db()
        chain.execute.return_value = MagicMock(data=[row])
        monkeypatch.setattr("api.properties_router._get_supabase_client", lambda: db)
        data = _client.get("/properties/prop-g2").json()
        assert data["property_id"] == "prop-g2"

    def test_g3_all_fields_in_response(self, monkeypatch):
        row = _make_property_row("prop-g3", display_name="My Villa", timezone="Asia/Tokyo", base_currency="JPY")
        db, chain = _mock_db()
        chain.execute.return_value = MagicMock(data=[row])
        monkeypatch.setattr("api.properties_router._get_supabase_client", lambda: db)
        data = _client.get("/properties/prop-g3").json()
        assert data["display_name"] == "My Villa"
        assert data["timezone"] == "Asia/Tokyo"
        assert data["base_currency"] == "JPY"


# ===========================================================================
# Group H — GET /properties/{property_id}: not found → 404
# ===========================================================================

class TestGroupH_GetNotFound:

    def test_h1_not_found_returns_404(self, monkeypatch):
        db, chain = _mock_db()
        chain.execute.return_value = MagicMock(data=[])
        monkeypatch.setattr("api.properties_router._get_supabase_client", lambda: db)
        resp = _client.get("/properties/does-not-exist")
        assert resp.status_code == 404


# ===========================================================================
# Group I — Tenant isolation
# ===========================================================================

class TestGroupI_TenantIsolation:

    def test_i1_get_other_tenant_property_returns_404(self, monkeypatch):
        # DB returns empty (other tenant's row not visible under tenant-test)
        db, chain = _mock_db()
        chain.execute.return_value = MagicMock(data=[])
        monkeypatch.setattr("api.properties_router._get_supabase_client", lambda: db)
        resp = _client.get("/properties/other-tenants-property")
        assert resp.status_code == 404


# ===========================================================================
# Group J — PATCH: update display_name
# ===========================================================================

class TestGroupJ_UpdateDisplayName:

    def test_j1_update_display_name_returns_200(self, monkeypatch):
        row = _make_property_row("prop-j1", display_name="Updated Name")
        db, chain = _mock_db()
        chain.execute.return_value = MagicMock(data=[row])
        monkeypatch.setattr("api.properties_router._get_supabase_client", lambda: db)
        resp = _client.patch("/properties/prop-j1", json={"display_name": "Updated Name"})
        assert resp.status_code == 200

    def test_j2_null_display_name_clears_field(self, monkeypatch):
        row = _make_property_row("prop-j2", display_name=None)
        db, chain = _mock_db()
        chain.execute.return_value = MagicMock(data=[row])
        monkeypatch.setattr("api.properties_router._get_supabase_client", lambda: db)
        resp = _client.patch("/properties/prop-j2", json={"display_name": None})
        assert resp.status_code == 200


# ===========================================================================
# Group K — PATCH: update timezone
# ===========================================================================

class TestGroupK_UpdateTimezone:

    def test_k1_update_timezone_returns_200(self, monkeypatch):
        row = _make_property_row("prop-k1", timezone="Europe/London")
        db, chain = _mock_db()
        chain.execute.return_value = MagicMock(data=[row])
        monkeypatch.setattr("api.properties_router._get_supabase_client", lambda: db)
        resp = _client.patch("/properties/prop-k1", json={"timezone": "Europe/London"})
        assert resp.status_code == 200

    def test_k2_empty_timezone_returns_400(self, monkeypatch):
        db, _ = _mock_db()
        monkeypatch.setattr("api.properties_router._get_supabase_client", lambda: db)
        resp = _client.patch("/properties/prop-k2", json={"timezone": ""})
        assert resp.status_code == 400


# ===========================================================================
# Group L — PATCH: update base_currency
# ===========================================================================

class TestGroupL_UpdateCurrency:

    def test_l1_update_currency_returns_200(self, monkeypatch):
        row = _make_property_row("prop-l1", base_currency="EUR")
        db, chain = _mock_db()
        chain.execute.return_value = MagicMock(data=[row])
        monkeypatch.setattr("api.properties_router._get_supabase_client", lambda: db)
        resp = _client.patch("/properties/prop-l1", json={"base_currency": "eur"})  # lowercase accepted
        assert resp.status_code == 200

    def test_l2_lowercase_currency_normalised(self, monkeypatch):
        row = _make_property_row("prop-l2", base_currency="GBP")
        db, chain = _mock_db()
        chain.execute.return_value = MagicMock(data=[row])
        monkeypatch.setattr("api.properties_router._get_supabase_client", lambda: db)
        resp = _client.patch("/properties/prop-l2", json={"base_currency": "gbp"})
        assert resp.status_code == 200


# ===========================================================================
# Group M — PATCH: invalid currency → 400
# ===========================================================================

class TestGroupM_PatchInvalidCurrency:

    def test_m1_invalid_currency_patch_returns_400(self, monkeypatch):
        db, _ = _mock_db()
        monkeypatch.setattr("api.properties_router._get_supabase_client", lambda: db)
        resp = _client.patch("/properties/prop-m1", json={"base_currency": "NOTREAL"})
        assert resp.status_code == 400


# ===========================================================================
# Group N — PATCH: not found → 404
# ===========================================================================

class TestGroupN_PatchNotFound:

    def test_n1_patch_not_found_returns_404(self, monkeypatch):
        db, chain = _mock_db()
        chain.execute.return_value = MagicMock(data=[])
        monkeypatch.setattr("api.properties_router._get_supabase_client", lambda: db)
        resp = _client.patch("/properties/does-not-exist", json={"display_name": "X"})
        assert resp.status_code == 404


# ===========================================================================
# Group O — PATCH: empty body → 400
# ===========================================================================

class TestGroupO_PatchEmptyBody:

    def test_o1_empty_body_returns_400(self, monkeypatch):
        db, _ = _mock_db()
        monkeypatch.setattr("api.properties_router._get_supabase_client", lambda: db)
        resp = _client.patch("/properties/prop-o1", json={})
        assert resp.status_code == 400

    def test_o2_no_valid_fields_returns_400(self, monkeypatch):
        db, _ = _mock_db()
        monkeypatch.setattr("api.properties_router._get_supabase_client", lambda: db)
        resp = _client.patch("/properties/prop-o2", json={"property_id": "immutable"})
        assert resp.status_code == 400


# ===========================================================================
# Group P — _format_property
# ===========================================================================

class TestGroupP_FormatProperty:

    def test_p1_all_fields_present(self):
        row = _make_property_row()
        fmt = _format_property(row)
        for field in ("id", "property_id", "tenant_id", "display_name",
                       "timezone", "base_currency", "created_at", "updated_at"):
            assert field in fmt

    def test_p2_missing_optional_fields_use_defaults(self):
        fmt = _format_property({"property_id": "p", "tenant_id": "t"})
        assert fmt["timezone"] == "UTC"
        assert fmt["base_currency"] == "USD"
        assert fmt["display_name"] is None
