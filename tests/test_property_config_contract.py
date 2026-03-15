"""
Phase 801 — Property Config Composite Endpoint Contract Tests

Tests for:
    GET /admin/property-config/{property_id}  — single property + channels
    GET /admin/property-config                — all properties + channels

Contract:
-----------------------------------------------------------------------
GET single:
  - 200 with property + channels when property exists
  - 200 with property + empty channels when no mappings
  - 404 when property not found
  - Response shape: { property: {...}, channels: { count, mappings: [...] } }
  - property has correct keys
  - channels.mappings entries have correct keys
  - Tenant isolation (only own tenant rows)
  - 500 on DB error
  - Auth required (403)

GET list:
  - 200 with all properties + channels
  - 200 with empty list when no properties
  - Response shape: { tenant_id, count, properties: [...] }
  - Each property entry has { property, channels } structure
  - Channel grouping correct (right channels to right property)
  - 500 on DB error
  - Auth required (403)
-----------------------------------------------------------------------
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.property_config_router import router

_app = FastAPI()
_app.include_router(router)
_client = TestClient(_app, raise_server_exceptions=False)

_TENANT = "tenant-phase-801"
_PROP_1 = "phangan-villa-01"
_PROP_2 = "samui-resort-02"


# ---------------------------------------------------------------------------
# DB mock helpers
# ---------------------------------------------------------------------------

def _prop_row(
    property_id: str = _PROP_1,
    tenant_id: str = _TENANT,
    display_name: str = "Sunset Villa Koh Phangan",
    timezone: str = "Asia/Bangkok",
    base_currency: str = "THB",
    status: str = "approved",
) -> dict:
    return {
        "property_id": property_id,
        "tenant_id": tenant_id,
        "display_name": display_name,
        "timezone": timezone,
        "base_currency": base_currency,
        "status": status,
        "property_type": None,
        "city": None,
        "country": None,
        "max_guests": None,
        "bedrooms": None,
        "beds": None,
        "bathrooms": None,
        "address": None,
        "created_at": "2026-03-15T12:00:00Z",
        "updated_at": "2026-03-15T12:00:00Z",
    }


def _chan_row(
    id: int = 1,
    property_id: str = _PROP_1,
    provider: str = "bookingcom",
    external_id: str = "bcom_phangan01",
    inventory_type: str = "single_unit",
    sync_mode: str = "api_first",
    enabled: bool = True,
) -> dict:
    return {
        "id": id,
        "tenant_id": _TENANT,
        "property_id": property_id,
        "provider": provider,
        "external_id": external_id,
        "inventory_type": inventory_type,
        "sync_mode": sync_mode,
        "enabled": enabled,
        "created_at": "2026-03-15T12:00:00Z",
        "updated_at": "2026-03-15T12:00:00Z",
    }


def _mock_db_two_tables(
    prop_rows: list[dict],
    chan_rows: list[dict],
) -> MagicMock:
    """Mock a Supabase client that supports two sequential table calls."""
    db = MagicMock()

    # Build property result
    prop_result = MagicMock()
    prop_result.data = prop_rows

    # Build channel result
    chan_result = MagicMock()
    chan_result.data = chan_rows

    # Track call count to return different mocks per table() call
    call_count = {"n": 0}
    original_table = db.table

    def table_side_effect(name: str) -> MagicMock:
        call_count["n"] += 1
        mock_table = MagicMock()
        if name == "properties":
            # Chain: select → eq → eq → limit → execute (single)
            # Chain: select → eq → order → execute (list)
            chain = mock_table.select.return_value
            chain.eq.return_value.eq.return_value.limit.return_value.execute.return_value = prop_result
            chain.eq.return_value.order.return_value.execute.return_value = prop_result
        elif name == "property_channel_map":
            chain = mock_table.select.return_value
            chain.eq.return_value.eq.return_value.order.return_value.execute.return_value = chan_result
            chain.eq.return_value.order.return_value.execute.return_value = chan_result
        return mock_table

    db.table = MagicMock(side_effect=table_side_effect)
    return db


def _override(tenant: str = _TENANT):
    from api.auth import jwt_auth
    _app.dependency_overrides[jwt_auth] = lambda: tenant


def _clear():
    _app.dependency_overrides.clear()


def _get_single(property_id: str, db: Any, tenant: str = _TENANT) -> Any:
    _override(tenant)
    with patch("api.property_config_router._get_supabase_client", return_value=db):
        r = _client.get(f"/admin/property-config/{property_id}")
    _clear()
    return r


def _get_list(db: Any, tenant: str = _TENANT) -> Any:
    _override(tenant)
    with patch("api.property_config_router._get_supabase_client", return_value=db):
        r = _client.get("/admin/property-config")
    _clear()
    return r


# ===========================================================================
# GET SINGLE TESTS
# ===========================================================================

def test_get_single_200_with_channels():
    channels = [
        _chan_row(id=1, provider="bookingcom"),
        _chan_row(id=2, provider="airbnb", external_id="abnb_phangan01"),
    ]
    db = _mock_db_two_tables([_prop_row()], channels)
    r = _get_single(_PROP_1, db)
    assert r.status_code == 200
    body = r.json()
    assert "property" in body
    assert "channels" in body
    assert body["property"]["property_id"] == _PROP_1
    assert body["channels"]["count"] == 2
    assert len(body["channels"]["mappings"]) == 2


def test_get_single_200_empty_channels():
    db = _mock_db_two_tables([_prop_row()], [])
    r = _get_single(_PROP_1, db)
    assert r.status_code == 200
    body = r.json()
    assert body["channels"]["count"] == 0
    assert body["channels"]["mappings"] == []


def test_get_single_404_not_found():
    db = _mock_db_two_tables([], [])
    r = _get_single("nonexistent-prop", db)
    assert r.status_code == 404


def test_get_single_property_keys():
    db = _mock_db_two_tables([_prop_row()], [])
    r = _get_single(_PROP_1, db)
    prop = r.json()["property"]
    expected = {
        "property_id", "tenant_id", "display_name", "timezone",
        "base_currency", "status", "property_type", "city", "country",
        "max_guests", "bedrooms", "beds", "bathrooms", "address",
        "created_at", "updated_at",
    }
    assert set(prop.keys()) == expected


def test_get_single_channel_keys():
    db = _mock_db_two_tables([_prop_row()], [_chan_row()])
    r = _get_single(_PROP_1, db)
    mapping = r.json()["channels"]["mappings"][0]
    expected = {
        "id", "provider", "external_id", "inventory_type",
        "sync_mode", "enabled", "created_at", "updated_at",
    }
    assert set(mapping.keys()) == expected


def test_get_single_response_shape():
    db = _mock_db_two_tables([_prop_row()], [_chan_row()])
    r = _get_single(_PROP_1, db)
    body = r.json()
    assert set(body.keys()) == {"property", "channels"}
    assert set(body["channels"].keys()) == {"count", "mappings"}


def test_get_single_500_on_db_error():
    db = MagicMock()
    db.table.side_effect = RuntimeError("DB down")
    r = _get_single(_PROP_1, db)
    assert r.status_code == 500


# ===========================================================================
# GET LIST TESTS
# ===========================================================================

def test_get_list_200_with_properties():
    props = [
        _prop_row(property_id=_PROP_1),
        _prop_row(property_id=_PROP_2, display_name="Ocean View Resort Samui"),
    ]
    channels = [
        _chan_row(id=1, property_id=_PROP_1, provider="bookingcom"),
        _chan_row(id=2, property_id=_PROP_1, provider="airbnb", external_id="abnb_01"),
        _chan_row(id=3, property_id=_PROP_2, provider="expedia", external_id="exp_02"),
    ]
    db = _mock_db_two_tables(props, channels)
    r = _get_list(db)
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 2
    assert len(body["properties"]) == 2


def test_get_list_200_empty():
    db = _mock_db_two_tables([], [])
    r = _get_list(db)
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 0
    assert body["properties"] == []


def test_get_list_response_keys():
    db = _mock_db_two_tables([_prop_row()], [])
    r = _get_list(db)
    assert set(r.json().keys()) == {"tenant_id", "count", "properties"}


def test_get_list_each_entry_structure():
    db = _mock_db_two_tables([_prop_row()], [_chan_row()])
    r = _get_list(db)
    entry = r.json()["properties"][0]
    assert set(entry.keys()) == {"property", "channels"}
    assert "count" in entry["channels"]
    assert "mappings" in entry["channels"]


def test_get_list_channel_grouping():
    """Channels are grouped to the correct property."""
    props = [
        _prop_row(property_id=_PROP_1),
        _prop_row(property_id=_PROP_2, display_name="Samui"),
    ]
    channels = [
        _chan_row(id=1, property_id=_PROP_1, provider="bookingcom"),
        _chan_row(id=2, property_id=_PROP_1, provider="airbnb", external_id="a01"),
        _chan_row(id=3, property_id=_PROP_2, provider="expedia", external_id="e02"),
    ]
    db = _mock_db_two_tables(props, channels)
    r = _get_list(db)
    entries = r.json()["properties"]

    # Find prop1 and prop2 entries
    p1 = next(e for e in entries if e["property"]["property_id"] == _PROP_1)
    p2 = next(e for e in entries if e["property"]["property_id"] == _PROP_2)

    assert p1["channels"]["count"] == 2
    assert p2["channels"]["count"] == 1


def test_get_list_tenant_id_in_response():
    db = _mock_db_two_tables([], [])
    r = _get_list(db, tenant="my-tenant-xyz")
    assert r.json()["tenant_id"] == "my-tenant-xyz"


def test_get_list_500_on_db_error():
    db = MagicMock()
    db.table.side_effect = RuntimeError("DB down")
    r = _get_list(db)
    assert r.status_code == 500


# ===========================================================================
# AUTH TESTS
# ===========================================================================

def test_all_endpoints_403_no_jwt():
    with patch.dict("os.environ", {"IHOUSE_JWT_SECRET": "test-secret", "IHOUSE_DEV_MODE": "false"}):
        r1 = _client.get(f"/admin/property-config/{_PROP_1}")
        r2 = _client.get("/admin/property-config")
    assert r1.status_code == 403
    assert r2.status_code == 403
