"""
Phase 192 — Contract tests: Guests Router

Groups:
  A — POST /guests: create, full_name required, empty full_name → 400
  B — GET  /guests: list returns tenant guests, empty → []
  C — GET  /guests/{id}: found → 200, unknown → 404, cross-tenant → 404
  D — PATCH /guests/{id}: partial update, blanked full_name → 400, unknown → 404
  E — Tenant isolation: guest from tenant-A not visible to tenant-B

Phase 979 — Fixed: tests now pass identity= dict (matching JWT shape) instead
of the removed tenant_id= kwarg. Added role='admin' to satisfy role guard.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _identity(tenant="t1", role="admin", user_id="test-user"):
    return {"tenant_id": tenant, "role": role, "user_id": user_id}


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.table.return_value = db
    db.select.return_value = db
    db.insert.return_value = db
    db.update.return_value = db
    db.eq.return_value = db
    db.order.return_value = db
    db.limit.return_value = db
    db.execute.return_value = MagicMock(data=[])
    return db


def _guest(gid=None, tenant="t1", full_name="Alice Smith", email="alice@ex.com"):
    return {
        "id": gid or str(uuid.uuid4()),
        "tenant_id": tenant,
        "full_name": full_name,
        "email": email,
        "phone": None,
        "nationality": None,
        "passport_no": None,
        "notes": None,
        "document_type": None,
        "passport_expiry": None,
        "date_of_birth": None,
        "document_photo_url": None,
        "whatsapp": None,
        "line_id": None,
        "telegram": None,
        "preferred_channel": None,
        "created_at": "2026-03-10T00:00:00Z",
        "updated_at": "2026-03-10T00:00:00Z",
    }


# ---------------------------------------------------------------------------
# Group A — POST /guests
# ---------------------------------------------------------------------------

class TestGroupA_CreateGuest:

    def test_a1_create_returns_201(self, mock_db):
        g = _guest()
        mock_db.execute.return_value = MagicMock(data=[g])
        from api.guests_router import create_guest
        result = asyncio.run(create_guest(
            body={"full_name": "Alice Smith", "email": "alice@ex.com"},
            identity=_identity(), client=mock_db,
        ))
        assert result.status_code == 201

    def test_a2_create_response_has_expected_fields(self, mock_db):
        g = _guest()
        mock_db.execute.return_value = MagicMock(data=[g])
        from api.guests_router import create_guest
        result = asyncio.run(create_guest(
            body={"full_name": "Alice Smith"},
            identity=_identity(), client=mock_db,
        ))
        data = json.loads(result.body)
        assert data["full_name"] == "Alice Smith"
        assert data["tenant_id"] == "t1"
        assert "id" in data

    def test_a3_missing_full_name_returns_400(self, mock_db):
        from api.guests_router import create_guest
        result = asyncio.run(create_guest(
            body={}, identity=_identity(), client=mock_db,
        ))
        assert result.status_code == 400

    def test_a4_empty_full_name_returns_400(self, mock_db):
        from api.guests_router import create_guest
        result = asyncio.run(create_guest(
            body={"full_name": "   "}, identity=_identity(), client=mock_db,
        ))
        assert result.status_code == 400

    def test_a5_optional_fields_accepted(self, mock_db):
        g = _guest()
        mock_db.execute.return_value = MagicMock(data=[g])
        from api.guests_router import create_guest
        result = asyncio.run(create_guest(
            body={
                "full_name": "Bob",
                "phone": "+66 81 000 0000",
                "nationality": "TH",
                "notes": "VIP",
            },
            identity=_identity(), client=mock_db,
        ))
        assert result.status_code == 201


# ---------------------------------------------------------------------------
# Group B — GET /guests (list)
# ---------------------------------------------------------------------------

class TestGroupB_ListGuests:

    def test_b1_list_returns_200(self, mock_db):
        mock_db.execute.return_value = MagicMock(data=[_guest()])
        from api.guests_router import list_guests
        result = asyncio.run(list_guests(identity=_identity(), client=mock_db))
        assert result.status_code == 200

    def test_b2_empty_returns_empty_list(self, mock_db):
        mock_db.execute.return_value = MagicMock(data=[])
        from api.guests_router import list_guests
        result = asyncio.run(list_guests(identity=_identity(), client=mock_db))
        data = json.loads(result.body)
        assert data["guests"] == []
        assert data["count"] == 0

    def test_b3_search_filters_by_name(self, mock_db):
        mock_db.execute.return_value = MagicMock(data=[
            _guest(full_name="Alice Smith", email="alice@ex.com"),
            _guest(full_name="Bob Jones", email="bob@ex.com"),
        ])
        from api.guests_router import list_guests
        result = asyncio.run(list_guests(search="alice", identity=_identity(), client=mock_db))
        data = json.loads(result.body)
        assert data["count"] == 1
        assert data["guests"][0]["full_name"] == "Alice Smith"

    def test_b4_invalid_limit_returns_400(self, mock_db):
        from api.guests_router import list_guests
        result = asyncio.run(list_guests(limit=999, identity=_identity(), client=mock_db))
        assert result.status_code == 400


# ---------------------------------------------------------------------------
# Group C — GET /guests/{id}
# ---------------------------------------------------------------------------

class TestGroupC_GetGuest:

    def test_c1_known_id_returns_200(self, mock_db):
        gid = str(uuid.uuid4())
        mock_db.execute.return_value = MagicMock(data=[_guest(gid=gid)])
        from api.guests_router import get_guest
        result = asyncio.run(get_guest(guest_id=gid, identity=_identity(), client=mock_db))
        assert result.status_code == 200

    def test_c2_unknown_id_returns_404(self, mock_db):
        mock_db.execute.return_value = MagicMock(data=[])
        from api.guests_router import get_guest
        result = asyncio.run(get_guest(guest_id=str(uuid.uuid4()), identity=_identity(), client=mock_db))
        assert result.status_code == 404

    def test_c3_cross_tenant_returns_404(self, mock_db):
        # DB returns empty because tenant_id filter excludes the row
        mock_db.execute.return_value = MagicMock(data=[])
        from api.guests_router import get_guest
        result = asyncio.run(get_guest(guest_id=str(uuid.uuid4()), identity=_identity(tenant="t2"), client=mock_db))
        assert result.status_code == 404


# ---------------------------------------------------------------------------
# Group D — PATCH /guests/{id}
# ---------------------------------------------------------------------------

class TestGroupD_PatchGuest:

    def test_d1_patch_returns_200(self, mock_db):
        gid = str(uuid.uuid4())
        updated = _guest(gid=gid, full_name="Alice Updated")
        # First call = existence check, second = update
        mock_db.execute.side_effect = [
            MagicMock(data=[_guest(gid=gid)]),
            MagicMock(data=[updated]),
        ]
        from api.guests_router import patch_guest
        result = asyncio.run(patch_guest(
            guest_id=gid,
            body={"full_name": "Alice Updated"},
            identity=_identity(), client=mock_db,
        ))
        assert result.status_code == 200

    def test_d2_patch_partial_doesnt_touch_unset_fields(self, mock_db):
        gid = str(uuid.uuid4())
        original = _guest(gid=gid, email="keep@me.com")
        mock_db.execute.side_effect = [
            MagicMock(data=[original]),
            MagicMock(data=[original]),
        ]
        from api.guests_router import patch_guest
        result = asyncio.run(patch_guest(
            guest_id=gid,
            body={"notes": "Updated note"},
            identity=_identity(), client=mock_db,
        ))
        data = json.loads(result.body)
        # email field must still be present in the returned row
        assert data["email"] == "keep@me.com"

    def test_d3_blank_full_name_returns_400(self, mock_db):
        from api.guests_router import patch_guest
        result = asyncio.run(patch_guest(
            guest_id=str(uuid.uuid4()),
            body={"full_name": ""},
            identity=_identity(), client=mock_db,
        ))
        assert result.status_code == 400

    def test_d4_empty_body_returns_400(self, mock_db):
        from api.guests_router import patch_guest
        result = asyncio.run(patch_guest(
            guest_id=str(uuid.uuid4()),
            body={},
            identity=_identity(), client=mock_db,
        ))
        assert result.status_code == 400

    def test_d5_unknown_id_returns_404(self, mock_db):
        mock_db.execute.return_value = MagicMock(data=[])
        from api.guests_router import patch_guest
        result = asyncio.run(patch_guest(
            guest_id=str(uuid.uuid4()),
            body={"notes": "x"},
            identity=_identity(), client=mock_db,
        ))
        assert result.status_code == 404


# ---------------------------------------------------------------------------
# Group E — Tenant isolation
# ---------------------------------------------------------------------------

class TestGroupE_TenantIsolation:

    def test_e1_list_scoped_to_tenant(self, mock_db):
        """GET /guests for tenant-B should not return tenant-A's guests."""
        mock_db.execute.return_value = MagicMock(data=[])
        from api.guests_router import list_guests
        result = asyncio.run(list_guests(identity=_identity(tenant="t-b"), client=mock_db))
        data = json.loads(result.body)
        assert data["guests"] == []
