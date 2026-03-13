"""
Phase 396 — Property Admin Approval Dashboard Contract Tests

Tests for:
    GET    /admin/properties                   — list with filters
    GET    /admin/properties/{id}              — detail + channels
    POST   /admin/properties/{id}/approve      — pending → approved
    POST   /admin/properties/{id}/reject       — pending → rejected
    POST   /admin/properties/{id}/archive      — approved → archived
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import main

_TENANT = "tenant-admin-test"


def _make_client() -> TestClient:
    return TestClient(main.app)


def _auth_header() -> dict:
    return {"Authorization": "Bearer mock-token"}


# ---------------------------------------------------------------------------
# DB mock factory
# ---------------------------------------------------------------------------

class _MockResult:
    def __init__(self, data=None, count=None):
        self.data = data or []
        self.count = count or 0


class _MockTable:
    """Minimal mock of supabase table query builder."""

    def __init__(self, rows=None):
        self._rows = rows or []
        self._result = _MockResult(data=self._rows, count=len(self._rows))

    def select(self, *a, **kw):
        return self

    def eq(self, *a, **kw):
        return self

    def ilike(self, *a, **kw):
        return self

    def limit(self, *a):
        return self

    def offset(self, *a):
        return self

    def order(self, *a, **kw):
        return self

    def insert(self, data):
        self._rows = [data]
        self._result = _MockResult(data=self._rows)
        return self

    def update(self, data):
        # Merge update into first row
        updated = {**(self._rows[0] if self._rows else {}), **data}
        self._rows = [updated]
        self._result = _MockResult(data=self._rows)
        return self

    def execute(self):
        return self._result


class _MockDB:
    def __init__(self, tables: dict):
        self._tables = tables

    def table(self, name: str):
        return self._tables.get(name, _MockTable())


# ---------------------------------------------------------------------------
# Property fixtures
# ---------------------------------------------------------------------------

_PENDING_PROPERTY = {
    "property_id": "prop-001",
    "tenant_id": _TENANT,
    "display_name": "Sunset Villa",
    "timezone": "Asia/Bangkok",
    "base_currency": "THB",
    "property_type": "villa",
    "city": "Phuket",
    "country": "Thailand",
    "max_guests": 6,
    "bedrooms": 3,
    "beds": 4,
    "bathrooms": 2.0,
    "address": "123 Beach Road",
    "description": "Beachfront villa",
    "source_url": "https://airbnb.com/rooms/12345",
    "source_platform": "airbnb",
    "status": "pending",
    "approved_at": None,
    "approved_by": None,
    "archived_at": None,
    "archived_by": None,
    "created_at": "2026-03-13T10:00:00",
}

_APPROVED_PROPERTY = {**_PENDING_PROPERTY, "status": "approved", "approved_at": "2026-03-13T12:00:00", "approved_by": _TENANT}
_REJECTED_PROPERTY = {**_PENDING_PROPERTY, "status": "rejected"}
_ARCHIVED_PROPERTY = {**_APPROVED_PROPERTY, "status": "archived", "archived_at": "2026-03-13T14:00:00", "archived_by": _TENANT}


def _db_with_property(prop: dict) -> _MockDB:
    return _MockDB({
        "properties": _MockTable([prop]),
        "channel_map": _MockTable([{"provider": "airbnb", "external_channel_id": "AB-001", "active": True, "source_url": None}]),
        "admin_audit_log": _MockTable([]),
    })


def _empty_db() -> _MockDB:
    return _MockDB({
        "properties": _MockTable([]),
        "channel_map": _MockTable([]),
        "admin_audit_log": _MockTable([]),
    })


# ===========================================================================
# GET /admin/properties — list
# ===========================================================================

class TestListProperties:

    def test_returns_200_with_empty_list(self):
        with patch("api.property_admin_router._get_supabase_client", return_value=_empty_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.get("/admin/properties", headers=_auth_header())
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 0
        assert body["properties"] == []
        assert "status_summary" in body

    def test_returns_properties_list(self):
        db = _db_with_property(_PENDING_PROPERTY)
        with patch("api.property_admin_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.get("/admin/properties", headers=_auth_header())
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] >= 1
        assert body["properties"][0]["property_id"] == "prop-001"

    def test_invalid_status_filter_returns_400(self):
        with patch("api.property_admin_router._get_supabase_client", return_value=_empty_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.get("/admin/properties?status=bogus", headers=_auth_header())
        assert resp.status_code == 400

    def test_status_filter_accepted(self):
        db = _db_with_property(_PENDING_PROPERTY)
        with patch("api.property_admin_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.get("/admin/properties?status=pending", headers=_auth_header())
        assert resp.status_code == 200

    def test_has_status_summary(self):
        db = _db_with_property(_PENDING_PROPERTY)
        with patch("api.property_admin_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.get("/admin/properties", headers=_auth_header())
        body = resp.json()
        assert "pending" in body["status_summary"]
        assert "approved" in body["status_summary"]

    def test_dev_tenant_no_auth(self):
        with patch("api.property_admin_router._get_supabase_client", return_value=_empty_db()):
            client = _make_client()
            resp = client.get("/admin/properties")
        assert resp.status_code == 200


# ===========================================================================
# GET /admin/properties/{id} — detail
# ===========================================================================

class TestPropertyDetail:

    def test_returns_property_with_channels(self):
        db = _db_with_property(_PENDING_PROPERTY)
        with patch("api.property_admin_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.get("/admin/properties/prop-001", headers=_auth_header())
        assert resp.status_code == 200
        body = resp.json()
        assert body["property_id"] == "prop-001"
        assert "channels" in body
        assert body["channels"][0]["provider"] == "airbnb"

    def test_returns_404_for_unknown_property(self):
        with patch("api.property_admin_router._get_supabase_client", return_value=_empty_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.get("/admin/properties/prop-unknown", headers=_auth_header())
        assert resp.status_code == 404

    def test_includes_lifecycle_fields(self):
        db = _db_with_property(_APPROVED_PROPERTY)
        with patch("api.property_admin_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.get("/admin/properties/prop-001", headers=_auth_header())
        body = resp.json()
        assert body["status"] == "approved"
        assert body["approved_at"] is not None


# ===========================================================================
# POST /admin/properties/{id}/approve
# ===========================================================================

class TestApproveProperty:

    def test_approve_pending_returns_200(self):
        db = _db_with_property(_PENDING_PROPERTY)
        with patch("api.property_admin_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.post("/admin/properties/prop-001/approve", headers=_auth_header())
        assert resp.status_code == 200
        body = resp.json()
        assert body["previous_status"] == "pending"
        assert body["status"] == "approved"

    def test_approve_already_approved_returns_409(self):
        db = _db_with_property(_APPROVED_PROPERTY)
        with patch("api.property_admin_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.post("/admin/properties/prop-001/approve", headers=_auth_header())
        assert resp.status_code == 409

    def test_approve_rejected_returns_409(self):
        db = _db_with_property(_REJECTED_PROPERTY)
        with patch("api.property_admin_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.post("/admin/properties/prop-001/approve", headers=_auth_header())
        assert resp.status_code == 409

    def test_approve_unknown_returns_404(self):
        with patch("api.property_admin_router._get_supabase_client", return_value=_empty_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.post("/admin/properties/prop-unknown/approve", headers=_auth_header())
        assert resp.status_code == 404

    def test_approve_returns_detail_object(self):
        db = _db_with_property(_PENDING_PROPERTY)
        with patch("api.property_admin_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.post("/admin/properties/prop-001/approve", headers=_auth_header())
        body = resp.json()
        assert "detail" in body
        assert body["detail"]["property_id"] == "prop-001"


# ===========================================================================
# POST /admin/properties/{id}/reject
# ===========================================================================

class TestRejectProperty:

    def test_reject_pending_returns_200(self):
        db = _db_with_property(_PENDING_PROPERTY)
        with patch("api.property_admin_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.post("/admin/properties/prop-001/reject", headers=_auth_header())
        assert resp.status_code == 200
        body = resp.json()
        assert body["previous_status"] == "pending"
        assert body["status"] == "rejected"

    def test_reject_approved_returns_409(self):
        db = _db_with_property(_APPROVED_PROPERTY)
        with patch("api.property_admin_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.post("/admin/properties/prop-001/reject", headers=_auth_header())
        assert resp.status_code == 409

    def test_reject_unknown_returns_404(self):
        with patch("api.property_admin_router._get_supabase_client", return_value=_empty_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.post("/admin/properties/prop-unknown/reject", headers=_auth_header())
        assert resp.status_code == 404


# ===========================================================================
# PATCH /admin/properties/{id} — edit
# ===========================================================================

class TestPatchProperty:

    def test_patch_pending_returns_200(self):
        db = _db_with_property(_PENDING_PROPERTY)
        with patch("api.property_admin_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.patch(
                "/admin/properties/prop-001",
                json={"display_name": "Updated Villa", "city": "Bangkok"},
                headers=_auth_header(),
            )
        assert resp.status_code == 200
        body = resp.json()
        assert "updated_fields" in body
        assert "display_name" in body["updated_fields"]

    def test_patch_approved_returns_200(self):
        db = _db_with_property(_APPROVED_PROPERTY)
        with patch("api.property_admin_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.patch(
                "/admin/properties/prop-001",
                json={"city": "Chiang Mai"},
                headers=_auth_header(),
            )
        assert resp.status_code == 200

    def test_patch_rejected_returns_409(self):
        db = _db_with_property(_REJECTED_PROPERTY)
        with patch("api.property_admin_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.patch(
                "/admin/properties/prop-001",
                json={"city": "Bangkok"},
                headers=_auth_header(),
            )
        assert resp.status_code == 409

    def test_patch_archived_returns_409(self):
        db = _db_with_property(_ARCHIVED_PROPERTY)
        with patch("api.property_admin_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.patch(
                "/admin/properties/prop-001",
                json={"city": "Bangkok"},
                headers=_auth_header(),
            )
        assert resp.status_code == 409

    def test_patch_no_valid_fields_returns_400(self):
        db = _db_with_property(_PENDING_PROPERTY)
        with patch("api.property_admin_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.patch(
                "/admin/properties/prop-001",
                json={"status": "approved", "tenant_id": "evil"},
                headers=_auth_header(),
            )
        assert resp.status_code == 400

    def test_patch_unknown_returns_404(self):
        with patch("api.property_admin_router._get_supabase_client", return_value=_empty_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.patch(
                "/admin/properties/prop-unknown",
                json={"city": "Bangkok"},
                headers=_auth_header(),
            )
        assert resp.status_code == 404

    def test_patch_filters_immutable_fields(self):
        db = _db_with_property(_PENDING_PROPERTY)
        with patch("api.property_admin_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.patch(
                "/admin/properties/prop-001",
                json={"display_name": "Safe Name", "property_id": "evil-id", "status": "approved"},
                headers=_auth_header(),
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["updated_fields"] == ["display_name"]


# ===========================================================================
# POST /admin/properties/{id}/archive
# ===========================================================================

class TestArchiveProperty:

    def test_archive_approved_returns_200(self):
        db = _db_with_property(_APPROVED_PROPERTY)
        with patch("api.property_admin_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.post("/admin/properties/prop-001/archive", headers=_auth_header())
        assert resp.status_code == 200
        body = resp.json()
        assert body["previous_status"] == "approved"
        assert body["status"] == "archived"

    def test_archive_pending_returns_409(self):
        db = _db_with_property(_PENDING_PROPERTY)
        with patch("api.property_admin_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.post("/admin/properties/prop-001/archive", headers=_auth_header())
        assert resp.status_code == 409

    def test_archive_already_archived_returns_409(self):
        db = _db_with_property(_ARCHIVED_PROPERTY)
        with patch("api.property_admin_router._get_supabase_client", return_value=db), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.post("/admin/properties/prop-001/archive", headers=_auth_header())
        assert resp.status_code == 409

    def test_archive_unknown_returns_404(self):
        with patch("api.property_admin_router._get_supabase_client", return_value=_empty_db()), \
             patch("api.auth.jwt_auth", return_value=_TENANT):
            client = _make_client()
            resp = client.post("/admin/properties/prop-unknown/archive", headers=_auth_header())
        assert resp.status_code == 404
