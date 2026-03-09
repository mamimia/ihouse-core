"""
Phase 135 — Property-Channel Mapping Foundation Contract Tests

Tests for:
    POST   /admin/properties/{property_id}/channels
    GET    /admin/properties/{property_id}/channels
    PATCH  /admin/properties/{property_id}/channels/{provider}
    DELETE /admin/properties/{property_id}/channels/{provider}

Contract:
-----------------------------------------------------------------------
POST:
  - 201 on successful registration
  - Required fields: provider, external_id
  - 400 when provider missing
  - 400 when external_id missing
  - 400 when provider empty string
  - 400 when external_id empty string
  - 400 on invalid inventory_type
  - 400 on invalid sync_mode
  - 400 when enabled is not boolean
  - 409 on duplicate (tenant, property_id, provider)
  - Defaults: inventory_type=single_unit, sync_mode=api_first, enabled=true
  - tenant_id set from JWT (not from body)
  - property_id set from path (not from body)
  - Response: full formatted mapping object
  - 500 on DB error

GET:
  - 200 with mappings list
  - Empty mappings list (not 404) when no mappings
  - Response: {property_id, tenant_id, count, mappings}
  - count matches len(mappings)
  - Tenant isolation (only own tenant rows)
  - 500 on DB error

PATCH:
  - 200 on successful update
  - Partial update: only provided fields changed
  - 400 on invalid sync_mode
  - 400 on invalid inventory_type
  - 400 when enabled is not boolean
  - 400 when body is empty
  - 404 when mapping not found
  - 500 on DB error
  - tenant_id enforced from JWT (can't update other tenant)

DELETE:
  - 200 on successful removal
  - Response: {deleted, property_id, provider, tenant_id}
  - 404 when mapping not found
  - 500 on DB error

Auth:
  - 403 when JWT missing (all endpoints)
-----------------------------------------------------------------------
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.channel_map_router import router

_app = FastAPI()
_app.include_router(router)
_client = TestClient(_app, raise_server_exceptions=False)

_TENANT = "tenant-phase-135"
_PROP   = "prop-villa-alpha"
_PROV   = "airbnb"


# ---------------------------------------------------------------------------
# DB mock helpers
# ---------------------------------------------------------------------------

def _mock_db_insert(returned_rows: list[dict]) -> MagicMock:
    db = MagicMock()
    result = MagicMock(); result.data = returned_rows
    db.table.return_value.insert.return_value.execute.return_value = result
    return db


def _mock_db_select(rows: list[dict]) -> MagicMock:
    db = MagicMock()
    result = MagicMock(); result.data = rows
    (
        db.table.return_value
        .select.return_value
        .eq.return_value
        .eq.return_value
        .order.return_value
        .execute.return_value
    ) = result
    return db


def _mock_db_update(rows: list[dict]) -> MagicMock:
    db = MagicMock()
    result = MagicMock(); result.data = rows
    (
        db.table.return_value
        .update.return_value
        .eq.return_value
        .eq.return_value
        .eq.return_value
        .execute.return_value
    ) = result
    return db


def _mock_db_delete(rows: list[dict]) -> MagicMock:
    db = MagicMock()
    result = MagicMock(); result.data = rows
    (
        db.table.return_value
        .delete.return_value
        .eq.return_value
        .eq.return_value
        .eq.return_value
        .execute.return_value
    ) = result
    return db


def _row(
    id: int = 1,
    tenant_id: str = _TENANT,
    property_id: str = _PROP,
    provider: str = _PROV,
    external_id: str = "HZ12345",
    inventory_type: str = "single_unit",
    sync_mode: str = "api_first",
    enabled: bool = True,
    created_at: str = "2026-03-09T20:00:00Z",
    updated_at: str = "2026-03-09T20:00:00Z",
) -> dict:
    return {
        "id": id, "tenant_id": tenant_id, "property_id": property_id,
        "provider": provider, "external_id": external_id,
        "inventory_type": inventory_type, "sync_mode": sync_mode,
        "enabled": enabled, "created_at": created_at, "updated_at": updated_at,
    }


def _override(tenant: str = _TENANT):
    from api.auth import jwt_auth
    _app.dependency_overrides[jwt_auth] = lambda: tenant


def _clear():
    _app.dependency_overrides.clear()


def _post(body: dict, db: Any, tenant: str = _TENANT) -> Any:
    _override(tenant)
    with patch("api.channel_map_router._get_supabase_client", return_value=db):
        r = _client.post(f"/admin/properties/{_PROP}/channels", json=body)
    _clear()
    return r


def _get(db: Any, tenant: str = _TENANT, prop: str = _PROP) -> Any:
    _override(tenant)
    with patch("api.channel_map_router._get_supabase_client", return_value=db):
        r = _client.get(f"/admin/properties/{prop}/channels")
    _clear()
    return r


def _patch(provider: str, body: dict, db: Any, tenant: str = _TENANT) -> Any:
    _override(tenant)
    with patch("api.channel_map_router._get_supabase_client", return_value=db):
        r = _client.patch(f"/admin/properties/{_PROP}/channels/{provider}", json=body)
    _clear()
    return r


def _delete(provider: str, db: Any, tenant: str = _TENANT) -> Any:
    _override(tenant)
    with patch("api.channel_map_router._get_supabase_client", return_value=db):
        r = _client.delete(f"/admin/properties/{_PROP}/channels/{provider}")
    _clear()
    return r


# ===========================================================================
# POST TESTS
# ===========================================================================

def test_post_201_basic():
    db = _mock_db_insert([_row()])
    r = _post({"provider": "airbnb", "external_id": "HZ12345"}, db)
    assert r.status_code == 201
    assert r.json()["provider"] == "airbnb"
    assert r.json()["external_id"] == "HZ12345"


def test_post_201_defaults_applied():
    db = _mock_db_insert([_row()])
    r = _post({"provider": "airbnb", "external_id": "HZ12345"}, db)
    body = r.json()
    assert body["inventory_type"] == "single_unit"
    assert body["sync_mode"] == "api_first"
    assert body["enabled"] is True


def test_post_201_custom_fields():
    db = _mock_db_insert([_row(inventory_type="multi_unit", sync_mode="ical_fallback", enabled=False)])
    r = _post({
        "provider": "vrbo",
        "external_id": "V9999",
        "inventory_type": "multi_unit",
        "sync_mode": "ical_fallback",
        "enabled": False,
    }, db)
    assert r.status_code == 201
    assert r.json()["inventory_type"] == "multi_unit"
    assert r.json()["sync_mode"] == "ical_fallback"
    assert r.json()["enabled"] is False


def test_post_400_missing_provider():
    db = _mock_db_insert([])
    r = _post({"external_id": "HZ12345"}, db)
    assert r.status_code == 400


def test_post_400_missing_external_id():
    db = _mock_db_insert([])
    r = _post({"provider": "airbnb"}, db)
    assert r.status_code == 400


def test_post_400_empty_provider():
    db = _mock_db_insert([])
    r = _post({"provider": "  ", "external_id": "HZ12345"}, db)
    assert r.status_code == 400


def test_post_400_empty_external_id():
    db = _mock_db_insert([])
    r = _post({"provider": "airbnb", "external_id": ""}, db)
    assert r.status_code == 400


def test_post_400_invalid_inventory_type():
    db = _mock_db_insert([])
    r = _post({"provider": "airbnb", "external_id": "HZ1", "inventory_type": "bad_type"}, db)
    assert r.status_code == 400


def test_post_400_invalid_sync_mode():
    db = _mock_db_insert([])
    r = _post({"provider": "airbnb", "external_id": "HZ1", "sync_mode": "auto_magic"}, db)
    assert r.status_code == 400


def test_post_400_enabled_not_bool():
    db = _mock_db_insert([])
    r = _post({"provider": "airbnb", "external_id": "HZ1", "enabled": "yes"}, db)
    assert r.status_code == 400


def test_post_409_on_duplicate():
    db = MagicMock()
    db.table.return_value.insert.return_value.execute.side_effect = Exception(
        "duplicate key value violates unique constraint 23505"
    )
    r = _post({"provider": "airbnb", "external_id": "HZ12345"}, db)
    assert r.status_code == 409


def test_post_tenant_id_from_jwt():
    db = _mock_db_insert([_row(tenant_id="jwt-tenant-001")])
    r = _post({"provider": "airbnb", "external_id": "HZ1"}, db, tenant="jwt-tenant-001")
    assert r.json()["tenant_id"] == "jwt-tenant-001"


def test_post_500_on_db_error():
    db = MagicMock()
    db.table.return_value.insert.return_value.execute.side_effect = RuntimeError("DB down")
    r = _post({"provider": "airbnb", "external_id": "HZ1"}, db)
    assert r.status_code == 500


def test_post_response_has_all_keys():
    db = _mock_db_insert([_row()])
    r = _post({"provider": "airbnb", "external_id": "HZ1"}, db)
    expected = {"id", "tenant_id", "property_id", "provider", "external_id",
                "inventory_type", "sync_mode", "enabled", "created_at", "updated_at"}
    assert set(r.json().keys()) == expected


def test_post_valid_inventory_types():
    for it in ("single_unit", "multi_unit", "shared"):
        db = _mock_db_insert([_row(inventory_type=it)])
        r = _post({"provider": "airbnb", "external_id": "X", "inventory_type": it}, db)
        assert r.status_code == 201


def test_post_valid_sync_modes():
    for sm in ("api_first", "ical_fallback", "disabled"):
        db = _mock_db_insert([_row(sync_mode=sm)])
        r = _post({"provider": "airbnb", "external_id": "X", "sync_mode": sm}, db)
        assert r.status_code == 201


# ===========================================================================
# GET TESTS
# ===========================================================================

def test_get_200_with_mappings():
    rows = [_row(id=1), _row(id=2, provider="vrbo", external_id="V9")]
    db = _mock_db_select(rows)
    r = _get(db)
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 2
    assert len(body["mappings"]) == 2


def test_get_200_empty_list():
    db = _mock_db_select([])
    r = _get(db)
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 0
    assert body["mappings"] == []


def test_get_response_keys():
    db = _mock_db_select([_row()])
    r = _get(db)
    assert set(r.json().keys()) == {"property_id", "tenant_id", "count", "mappings"}


def test_get_count_matches_mappings():
    rows = [_row(id=i, provider=f"p{i}") for i in range(1, 4)]
    db = _mock_db_select(rows)
    r = _get(db)
    body = r.json()
    assert body["count"] == len(body["mappings"]) == 3


def test_get_property_id_in_response():
    db = _mock_db_select([_row()])
    r = _get(db, prop="my-special-prop")
    assert r.json()["property_id"] == "my-special-prop"


def test_get_tenant_id_in_response():
    db = _mock_db_select([_row(tenant_id="my-tenant-XYZ")])
    r = _get(db, tenant="my-tenant-XYZ")
    assert r.json()["tenant_id"] == "my-tenant-XYZ"


def test_get_500_on_db_error():
    db = MagicMock()
    db.table.side_effect = RuntimeError("DB down")
    r = _get(db)
    assert r.status_code == 500


def test_get_mapping_entry_keys():
    db = _mock_db_select([_row()])
    r = _get(db)
    mapping = r.json()["mappings"][0]
    expected = {"id", "tenant_id", "property_id", "provider", "external_id",
                "inventory_type", "sync_mode", "enabled", "created_at", "updated_at"}
    assert set(mapping.keys()) == expected


def test_get_sync_mode_propagated():
    db = _mock_db_select([_row(sync_mode="ical_fallback")])
    r = _get(db)
    assert r.json()["mappings"][0]["sync_mode"] == "ical_fallback"


def test_get_enabled_false_propagated():
    db = _mock_db_select([_row(enabled=False)])
    r = _get(db)
    assert r.json()["mappings"][0]["enabled"] is False


# ===========================================================================
# PATCH TESTS
# ===========================================================================

def test_patch_200_sync_mode():
    db = _mock_db_update([_row(sync_mode="ical_fallback")])
    r = _patch("airbnb", {"sync_mode": "ical_fallback"}, db)
    assert r.status_code == 200
    assert r.json()["sync_mode"] == "ical_fallback"


def test_patch_200_enabled_false():
    db = _mock_db_update([_row(enabled=False)])
    r = _patch("airbnb", {"enabled": False}, db)
    assert r.status_code == 200
    assert r.json()["enabled"] is False


def test_patch_200_external_id():
    db = _mock_db_update([_row(external_id="NEW-ID-999")])
    r = _patch("airbnb", {"external_id": "NEW-ID-999"}, db)
    assert r.status_code == 200
    assert r.json()["external_id"] == "NEW-ID-999"


def test_patch_200_inventory_type_multi_unit():
    db = _mock_db_update([_row(inventory_type="multi_unit")])
    r = _patch("airbnb", {"inventory_type": "multi_unit"}, db)
    assert r.status_code == 200


def test_patch_400_invalid_sync_mode():
    db = _mock_db_update([])
    r = _patch("airbnb", {"sync_mode": "bad_val"}, db)
    assert r.status_code == 400


def test_patch_400_invalid_inventory_type():
    db = _mock_db_update([])
    r = _patch("airbnb", {"inventory_type": "penthouse"}, db)
    assert r.status_code == 400


def test_patch_400_enabled_not_bool():
    db = _mock_db_update([])
    r = _patch("airbnb", {"enabled": "true"}, db)
    assert r.status_code == 400


def test_patch_400_empty_body():
    db = _mock_db_update([])
    r = _patch("airbnb", {}, db)
    assert r.status_code == 400


def test_patch_400_empty_external_id():
    db = _mock_db_update([])
    r = _patch("airbnb", {"external_id": ""}, db)
    assert r.status_code == 400


def test_patch_404_not_found():
    db = _mock_db_update([])
    r = _patch("nonexistent-provider", {"sync_mode": "disabled"}, db)
    assert r.status_code == 404


def test_patch_500_on_db_error():
    db = MagicMock()
    db.table.side_effect = RuntimeError("DB down")
    r = _patch("airbnb", {"enabled": False}, db)
    assert r.status_code == 500


def test_patch_sync_mode_disabled_works():
    db = _mock_db_update([_row(sync_mode="disabled")])
    r = _patch("airbnb", {"sync_mode": "disabled"}, db)
    assert r.status_code == 200
    assert r.json()["sync_mode"] == "disabled"


# ===========================================================================
# DELETE TESTS
# ===========================================================================

def test_delete_200_success():
    db = _mock_db_delete([_row()])
    r = _delete("airbnb", db)
    assert r.status_code == 200
    body = r.json()
    assert body["deleted"] is True
    assert body["provider"] == "airbnb"


def test_delete_response_keys():
    db = _mock_db_delete([_row()])
    r = _delete("airbnb", db)
    assert set(r.json().keys()) == {"deleted", "property_id", "provider", "tenant_id"}


def test_delete_404_not_found():
    db = _mock_db_delete([])
    r = _delete("nonexistent-prov", db)
    assert r.status_code == 404


def test_delete_500_on_db_error():
    db = MagicMock()
    db.table.side_effect = RuntimeError("DB down")
    r = _delete("airbnb", db)
    assert r.status_code == 500


def test_delete_property_id_in_response():
    db = _mock_db_delete([_row()])
    r = _delete("airbnb", db)
    assert r.json()["property_id"] == _PROP


def test_delete_tenant_id_in_response():
    db = _mock_db_delete([_row()])
    r = _delete("airbnb", db)
    assert r.json()["tenant_id"] == _TENANT


# ===========================================================================
# AUTH TESTS
# ===========================================================================

def test_all_endpoints_403_no_jwt():
    with patch.dict("os.environ", {"IHOUSE_JWT_SECRET": "test-secret"}):
        r1 = _client.post(f"/admin/properties/{_PROP}/channels", json={})
        r2 = _client.get(f"/admin/properties/{_PROP}/channels")
        r3 = _client.patch(f"/admin/properties/{_PROP}/channels/airbnb", json={})
        r4 = _client.delete(f"/admin/properties/{_PROP}/channels/airbnb")
    assert r1.status_code == 403
    assert r2.status_code == 403
    assert r3.status_code == 403
    assert r4.status_code == 403


def test_post_method_guard():
    _override()
    r = _client.put(f"/admin/properties/{_PROP}/channels")
    _clear()
    assert r.status_code == 405
