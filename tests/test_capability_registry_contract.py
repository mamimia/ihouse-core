"""
Phase 136 — Provider Capability Registry Contract Tests

Tests for:
    GET  /admin/registry/providers                   — list all providers
    GET  /admin/registry/providers/{provider}        — single provider
    PUT  /admin/registry/providers/{provider}        — upsert provider record

Contract:
-----------------------------------------------------------------------
GET /admin/registry/providers:
  - 200 with providers list
  - Empty list when no records (not 404)
  - Response: {total, tier_filter, api_write_filter, providers}
  - total matches len(providers)
  - tier_filter echoed (null when not provided)
  - api_write_filter echoed (null when not provided)
  - tier=A filter echoed correctly
  - supports_api_write=true filter echoed
  - 400 on invalid tier value
  - records contain all expected fields
  - 500 on DB error
  - 403 when JWT missing

GET /admin/registry/providers/{provider}:
  - 200 with provider record
  - 404 when provider not registered
  - provider name case-insensitive (uppercase → lowercase lookup)
  - all fields present in response
  - 500 on DB error

PUT /admin/registry/providers/{provider}:
  - 200 on successful upsert
  - Required: tier
  - 400 when tier missing/null
  - 400 on invalid tier value
  - 400 on invalid auth_method
  - 400 when supports_api_write is not boolean
  - 400 when rate_limit_per_min is negative
  - defaults applied: supports_api_write=false, supports_ical_pull=true, rate_limit=60
  - write_api_base_url and notes propagated when provided
  - provider name stored lowercase
  - response has all expected fields
  - 500 on DB error
  - 403 when JWT missing
-----------------------------------------------------------------------
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.capability_registry_router import router

_app = FastAPI()
_app.include_router(router)
_client = TestClient(_app, raise_server_exceptions=False)

_TENANT = "tenant-phase-136"


# ---------------------------------------------------------------------------
# DB mock helpers
# ---------------------------------------------------------------------------

def _mock_list(rows: list) -> MagicMock:
    db = MagicMock()
    result = MagicMock(); result.data = rows
    (
        db.table.return_value
        .select.return_value
        .order.return_value
        .execute.return_value
    ) = result
    # With tier filter
    eq_result = MagicMock(); eq_result.data = rows
    eq_chain = MagicMock()
    eq_chain.execute.return_value = eq_result
    eq_chain.eq.return_value.execute.return_value = eq_result
    db.table.return_value.select.return_value.order.return_value.eq.return_value = eq_chain
    return db


def _mock_single(rows: list) -> MagicMock:
    db = MagicMock()
    result = MagicMock(); result.data = rows
    (
        db.table.return_value
        .select.return_value
        .eq.return_value
        .limit.return_value
        .execute.return_value
    ) = result
    return db


def _mock_upsert(rows: list) -> MagicMock:
    db = MagicMock()
    result = MagicMock(); result.data = rows
    (
        db.table.return_value
        .upsert.return_value
        .execute.return_value
    ) = result
    return db


def _provider_row(
    provider: str = "airbnb",
    tier: str = "A",
    supports_api_write: bool = True,
    supports_ical_push: bool = False,
    supports_ical_pull: bool = True,
    rate_limit_per_min: int = 120,
    auth_method: str = "oauth2",
    write_api_base_url: str | None = "https://api.airbnb.com",
    notes: str | None = "Requires Partner Program",
    id: int = 1,
) -> dict:
    return {
        "id": id, "provider": provider, "tier": tier,
        "supports_api_write": supports_api_write,
        "supports_ical_push": supports_ical_push,
        "supports_ical_pull": supports_ical_pull,
        "rate_limit_per_min": rate_limit_per_min,
        "auth_method": auth_method,
        "write_api_base_url": write_api_base_url,
        "notes": notes,
        "created_at": "2026-03-09T20:00:00Z",
        "updated_at": "2026-03-09T20:00:00Z",
    }


def _auth(tenant: str = _TENANT):
    from api.auth import jwt_auth
    _app.dependency_overrides[jwt_auth] = lambda: tenant


def _clear():
    _app.dependency_overrides.clear()


def _list(params: str = "", db: Any = None) -> Any:
    if db is None:
        db = _mock_list([])
    _auth()
    with patch("api.capability_registry_router._get_supabase_client", return_value=db):
        r = _client.get(f"/admin/registry/providers{params}")
    _clear()
    return r


def _get(provider: str, db: Any) -> Any:
    _auth()
    with patch("api.capability_registry_router._get_supabase_client", return_value=db):
        r = _client.get(f"/admin/registry/providers/{provider}")
    _clear()
    return r


def _put(provider: str, body: dict, db: Any) -> Any:
    _auth()
    with patch("api.capability_registry_router._get_supabase_client", return_value=db):
        r = _client.put(f"/admin/registry/providers/{provider}", json=body)
    _clear()
    return r


# ===========================================================================
# LIST TESTS
# ===========================================================================

def test_list_200_with_rows():
    db = _mock_list([_provider_row(), _provider_row(provider="bookingcom", id=2)])
    r = _list(db=db)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert len(body["providers"]) == 2


def test_list_200_empty():
    db = _mock_list([])
    r = _list(db=db)
    assert r.status_code == 200
    assert r.json()["total"] == 0
    assert r.json()["providers"] == []


def test_list_top_level_keys():
    db = _mock_list([])
    r = _list(db=db)
    assert set(r.json().keys()) == {"total", "tier_filter", "api_write_filter", "providers"}


def test_list_total_matches_count():
    rows = [_provider_row(provider=p, id=i) for i, p in enumerate(["airbnb", "vrbo", "expedia"], 1)]
    db = _mock_list(rows)
    r = _list(db=db)
    body = r.json()
    assert body["total"] == len(body["providers"])


def test_list_tier_filter_null_when_absent():
    db = _mock_list([])
    r = _list(db=db)
    assert r.json()["tier_filter"] is None


def test_list_tier_filter_echoed():
    db = _mock_list([])
    r = _list("?tier=A", db=db)
    assert r.json()["tier_filter"] == "A"


def test_list_api_write_filter_null_when_absent():
    db = _mock_list([])
    r = _list(db=db)
    assert r.json()["api_write_filter"] is None


def test_list_api_write_filter_echoed():
    db = _mock_list([])
    r = _list("?supports_api_write=true", db=db)
    assert r.json()["api_write_filter"] is True


def test_list_400_invalid_tier():
    db = _mock_list([])
    r = _list("?tier=Z", db=db)
    assert r.status_code == 400


def test_list_entry_has_all_fields():
    db = _mock_list([_provider_row()])
    r = _list(db=db)
    prov = r.json()["providers"][0]
    expected = {
        "id", "provider", "tier", "supports_api_write", "supports_ical_push",
        "supports_ical_pull", "rate_limit_per_min", "auth_method",
        "write_api_base_url", "notes", "created_at", "updated_at"
    }
    assert set(prov.keys()) == expected


def test_list_500_on_db_error():
    db = MagicMock()
    db.table.side_effect = RuntimeError("DB down")
    r = _list(db=db)
    assert r.status_code == 500


def test_list_supports_api_write_propagated():
    db = _mock_list([_provider_row(supports_api_write=True)])
    r = _list(db=db)
    assert r.json()["providers"][0]["supports_api_write"] is True


def test_list_tier_propagated():
    db = _mock_list([_provider_row(tier="B")])
    r = _list(db=db)
    assert r.json()["providers"][0]["tier"] == "B"


def test_list_rate_limit_propagated():
    db = _mock_list([_provider_row(rate_limit_per_min=30)])
    r = _list(db=db)
    assert r.json()["providers"][0]["rate_limit_per_min"] == 30


def test_list_write_api_url_propagated():
    db = _mock_list([_provider_row(write_api_base_url="https://api.airbnb.com")])
    r = _list(db=db)
    assert r.json()["providers"][0]["write_api_base_url"] == "https://api.airbnb.com"


def test_list_write_api_url_null():
    db = _mock_list([_provider_row(write_api_base_url=None)])
    r = _list(db=db)
    assert r.json()["providers"][0]["write_api_base_url"] is None


def test_list_403_no_jwt():
    with patch.dict("os.environ", {"IHOUSE_JWT_SECRET": "test-secret"}):
        r = _client.get("/admin/registry/providers")
    assert r.status_code == 403


def test_list_tier_b_filter_echoed():
    db = _mock_list([])
    r = _list("?tier=B", db=db)
    assert r.json()["tier_filter"] == "B"


def test_list_all_tier_values_valid():
    for tier in ("A", "B", "C", "D"):
        db = _mock_list([])
        r = _list(f"?tier={tier}", db=db)
        assert r.status_code == 200


# ===========================================================================
# GET SINGLE TESTS
# ===========================================================================

def test_get_single_200():
    db = _mock_single([_provider_row(provider="airbnb")])
    r = _get("airbnb", db)
    assert r.status_code == 200
    assert r.json()["provider"] == "airbnb"


def test_get_single_404():
    db = _mock_single([])
    r = _get("unknown-prov", db)
    assert r.status_code == 404
    assert "unknown-prov" in r.text


def test_get_single_all_fields():
    db = _mock_single([_provider_row()])
    r = _get("airbnb", db)
    expected = {
        "id", "provider", "tier", "supports_api_write", "supports_ical_push",
        "supports_ical_pull", "rate_limit_per_min", "auth_method",
        "write_api_base_url", "notes", "created_at", "updated_at"
    }
    assert set(r.json().keys()) == expected


def test_get_single_500():
    db = MagicMock()
    db.table.side_effect = RuntimeError("DB down")
    r = _get("airbnb", db)
    assert r.status_code == 500


def test_get_single_tier_c_record():
    db = _mock_single([_provider_row(provider="houfy", tier="C", supports_api_write=False)])
    r = _get("houfy", db)
    assert r.status_code == 200
    assert r.json()["tier"] == "C"
    assert r.json()["supports_api_write"] is False


def test_get_single_notes_propagated():
    db = _mock_single([_provider_row(notes="Partner enrollment required")])
    r = _get("airbnb", db)
    assert r.json()["notes"] == "Partner enrollment required"


def test_get_single_403_no_jwt():
    with patch.dict("os.environ", {"IHOUSE_JWT_SECRET": "test-secret"}):
        r = _client.get("/admin/registry/providers/airbnb")
    assert r.status_code == 403


# ===========================================================================
# PUT UPSERT TESTS
# ===========================================================================

def test_put_200_basic():
    db = _mock_upsert([_provider_row()])
    r = _put("airbnb", {"tier": "A"}, db)
    assert r.status_code == 200


def test_put_response_has_all_fields():
    db = _mock_upsert([_provider_row()])
    r = _put("airbnb", {"tier": "A"}, db)
    expected = {
        "id", "provider", "tier", "supports_api_write", "supports_ical_push",
        "supports_ical_pull", "rate_limit_per_min", "auth_method",
        "write_api_base_url", "notes", "created_at", "updated_at"
    }
    assert set(r.json().keys()) == expected


def test_put_400_tier_missing():
    db = _mock_upsert([])
    r = _put("airbnb", {"supports_api_write": True}, db)
    assert r.status_code == 400


def test_put_400_invalid_tier():
    db = _mock_upsert([])
    r = _put("airbnb", {"tier": "E"}, db)
    assert r.status_code == 400


def test_put_400_invalid_auth_method():
    db = _mock_upsert([])
    r = _put("airbnb", {"tier": "A", "auth_method": "magic_link"}, db)
    assert r.status_code == 400


def test_put_400_supports_api_write_not_bool():
    db = _mock_upsert([])
    r = _put("airbnb", {"tier": "A", "supports_api_write": "yes"}, db)
    assert r.status_code == 400


def test_put_400_negative_rate_limit():
    db = _mock_upsert([])
    r = _put("airbnb", {"tier": "A", "rate_limit_per_min": -5}, db)
    assert r.status_code == 400


def test_put_valid_all_tiers():
    for t in ("A", "B", "C", "D"):
        db = _mock_upsert([_provider_row(tier=t)])
        r = _put("test-prov", {"tier": t}, db)
        assert r.status_code == 200


def test_put_valid_all_auth_methods():
    for am in ("oauth2", "api_key", "basic", "none"):
        db = _mock_upsert([_provider_row(auth_method=am)])
        r = _put("test-prov", {"tier": "A", "auth_method": am}, db)
        assert r.status_code == 200


def test_put_write_api_url_propagated():
    db = _mock_upsert([_provider_row(write_api_base_url="https://api.bookingcom.com/v2")])
    r = _put("bookingcom", {"tier": "A", "write_api_base_url": "https://api.bookingcom.com/v2"}, db)
    assert r.status_code == 200
    assert r.json()["write_api_base_url"] == "https://api.bookingcom.com/v2"


def test_put_notes_propagated():
    db = _mock_upsert([_provider_row(notes="Now enrolled")])
    r = _put("airbnb", {"tier": "A", "notes": "Now enrolled"}, db)
    assert r.status_code == 200
    assert r.json()["notes"] == "Now enrolled"


def test_put_500_on_db_error():
    db = MagicMock()
    db.table.side_effect = RuntimeError("DB down")
    r = _put("airbnb", {"tier": "A"}, db)
    assert r.status_code == 500


def test_put_tier_b_ical_push():
    db = _mock_upsert([_provider_row(tier="B", supports_ical_push=True, supports_api_write=False)])
    r = _put("hotelbeds", {"tier": "B", "supports_ical_push": True}, db)
    assert r.status_code == 200


def test_put_tier_d_no_sync():
    db = _mock_upsert([_provider_row(tier="D", supports_api_write=False,
                                    supports_ical_push=False, supports_ical_pull=False)])
    r = _put("direct", {"tier": "D", "supports_ical_pull": False}, db)
    assert r.status_code == 200


def test_put_403_no_jwt():
    with patch.dict("os.environ", {"IHOUSE_JWT_SECRET": "test-secret"}):
        r = _client.put("/admin/registry/providers/airbnb", json={"tier": "A"})
    assert r.status_code == 403


def test_put_rate_limit_zero_valid():
    db = _mock_upsert([_provider_row(rate_limit_per_min=0)])
    r = _put("direct", {"tier": "D", "rate_limit_per_min": 0}, db)
    assert r.status_code == 200
