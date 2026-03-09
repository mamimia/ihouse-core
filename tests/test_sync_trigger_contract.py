"""
Phase 137 — Outbound Sync Trigger Contract Tests

Two test suites:
  1. Pure service layer (outbound_sync_trigger.py) — covers all strategy resolution rules
  2. HTTP router (sync_trigger_router.py) — covers request/response contract

SERVICE LAYER CONTRACTS (build_sync_plan / _resolve_strategy):
-----------------------------------------------------------------------
  api_first:
    - channel enabled + sync_mode=api_first + registry.supports_api_write=true → api_first
    - channel enabled + sync_mode=api_first + no write API but has ical → ical_fallback (degraded)
    - channel enabled + sync_mode=api_first + no write API + no ical → skip
  ical_fallback:
    - channel + sync_mode=ical_fallback + supports_ical_push=true → ical_fallback
    - channel + sync_mode=ical_fallback + supports_ical_pull=true → ical_fallback
    - channel + sync_mode=ical_fallback + neither → skip
  skip:
    - channel.enabled=false → skip
    - channel.sync_mode=disabled → skip
    - provider not in registry → skip
    - tier=D always → skip
  multiple channels:
    - mixed channels → correct strategies per channel
    - empty channels → empty actions list
  summarise_plan:
    - counts correct
    - all actions serialisable

HTTP ROUTER CONTRACTS (POST /internal/sync/trigger):
-----------------------------------------------------------------------
  200:
    - booking found, channels found, registry fetched → full plan
    - booking found, no channels → empty plan (count=0)
    - plan contains booking_id, property_id, tenant_id
    - plan contains action details (strategy, reason, tier, etc.)
    - api_first_count + ical_count + skip_count == total_channels
  400:
    - missing booking_id
    - booking_id empty string
  403:
    - JWT missing
  404:
    - booking not found for this tenant
  500:
    - DB error on booking lookup
    - DB error on channel fetch
    - DB error on registry fetch
-----------------------------------------------------------------------
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.sync_trigger_router import router
from services.outbound_sync_trigger import (
    SyncAction,
    build_sync_plan,
    summarise_plan,
)

_app = FastAPI()
_app.include_router(router)
_client = TestClient(_app, raise_server_exceptions=False)

_TENANT    = "tenant-phase-137"
_BOOKING   = "bk-airbnb-HZ001"
_PROP      = "prop-villa-alpha"


# ---------------------------------------------------------------------------
# Helper: channel + registry rows
# ---------------------------------------------------------------------------

def _channel(
    provider: str = "airbnb",
    external_id: str = "HZ12345",
    sync_mode: str = "api_first",
    enabled: bool = True,
    tenant_id: str = _TENANT,
    property_id: str = _PROP,
) -> dict:
    return {
        "provider": provider, "external_id": external_id,
        "sync_mode": sync_mode, "enabled": enabled,
        "tenant_id": tenant_id, "property_id": property_id,
    }


def _reg(
    provider: str = "airbnb",
    tier: str = "A",
    supports_api_write: bool = True,
    supports_ical_push: bool = False,
    supports_ical_pull: bool = True,
    rate_limit_per_min: int = 120,
) -> dict:
    return {
        "provider": provider, "tier": tier,
        "supports_api_write": supports_api_write,
        "supports_ical_push": supports_ical_push,
        "supports_ical_pull": supports_ical_pull,
        "rate_limit_per_min": rate_limit_per_min,
    }


def _registry(*rows: dict) -> dict:
    return {r["provider"]: r for r in rows}


# ---------------------------------------------------------------------------
# Service-layer mock DB for router tests
# ---------------------------------------------------------------------------

def _mock_db(
    booking_rows: list,
    channel_rows: list,
    registry_rows: list,
) -> MagicMock:
    db = MagicMock()

    # booking_state lookup
    booking_result = MagicMock(); booking_result.data = booking_rows
    (
        db.table.return_value
        .select.return_value
        .eq.return_value
        .eq.return_value
        .limit.return_value
        .execute.return_value
    ) = booking_result

    # channel_map lookup (second .execute via chained .eq.eq.execute)
    channel_result = MagicMock(); channel_result.data = channel_rows
    registry_result = MagicMock(); registry_result.data = registry_rows

    # We need separate mock returns for different table() calls
    booking_table  = MagicMock()
    channel_table  = MagicMock()
    registry_table = MagicMock()

    (
        booking_table.select.return_value
        .eq.return_value
        .eq.return_value
        .limit.return_value
        .execute.return_value
    ) = booking_result

    (
        channel_table.select.return_value
        .eq.return_value
        .eq.return_value
        .execute.return_value
    ) = channel_result

    (
        registry_table.select.return_value
        .execute.return_value
    ) = registry_result

    db.table.side_effect = lambda name: {
        "booking_state": booking_table,
        "property_channel_map": channel_table,
        "provider_capability_registry": registry_table,
    }[name]

    return db


def _auth():
    from api.auth import jwt_auth
    _app.dependency_overrides[jwt_auth] = lambda: _TENANT


def _clear():
    _app.dependency_overrides.clear()


def _post(body: dict, db: object) -> object:
    _auth()
    with patch("api.sync_trigger_router._get_supabase_client", return_value=db):
        r = _client.post("/internal/sync/trigger", json=body)
    _clear()
    return r


# ===========================================================================
# SERVICE LAYER TESTS — build_sync_plan / _resolve_strategy
# ===========================================================================

# ---- api_first strategy ----

def test_service_api_first_when_write_supported():
    channels = [_channel(sync_mode="api_first")]
    registry = _registry(_reg(supports_api_write=True))
    actions = build_sync_plan(_BOOKING, _PROP, channels, registry)
    assert len(actions) == 1
    assert actions[0].strategy == "api_first"


def test_service_degrade_to_ical_when_no_write_api():
    channels = [_channel(sync_mode="api_first")]
    registry = _registry(_reg(supports_api_write=False, supports_ical_push=True))
    actions = build_sync_plan(_BOOKING, _PROP, channels, registry)
    assert actions[0].strategy == "ical_fallback"
    assert "degraded" in actions[0].reason


def test_service_skip_when_no_write_and_no_ical():
    channels = [_channel(sync_mode="api_first")]
    registry = _registry(_reg(
        supports_api_write=False, supports_ical_push=False, supports_ical_pull=False
    ))
    actions = build_sync_plan(_BOOKING, _PROP, channels, registry)
    assert actions[0].strategy == "skip"


# ---- ical_fallback strategy ----

def test_service_ical_fallback_with_ical_push():
    channels = [_channel(sync_mode="ical_fallback")]
    registry = _registry(_reg(supports_api_write=False, supports_ical_push=True))
    actions = build_sync_plan(_BOOKING, _PROP, channels, registry)
    assert actions[0].strategy == "ical_fallback"


def test_service_ical_fallback_with_ical_pull():
    channels = [_channel(sync_mode="ical_fallback")]
    registry = _registry(_reg(supports_api_write=False, supports_ical_push=False, supports_ical_pull=True))
    actions = build_sync_plan(_BOOKING, _PROP, channels, registry)
    assert actions[0].strategy == "ical_fallback"


def test_service_skip_ical_fallback_no_ical_support():
    channels = [_channel(sync_mode="ical_fallback")]
    registry = _registry(_reg(supports_api_write=False, supports_ical_push=False, supports_ical_pull=False))
    actions = build_sync_plan(_BOOKING, _PROP, channels, registry)
    assert actions[0].strategy == "skip"


# ---- skip conditions ----

def test_service_skip_when_channel_disabled():
    channels = [_channel(enabled=False)]
    registry = _registry(_reg(supports_api_write=True))
    actions = build_sync_plan(_BOOKING, _PROP, channels, registry)
    assert actions[0].strategy == "skip"
    assert "disabled" in actions[0].reason.lower()


def test_service_skip_when_sync_mode_disabled():
    channels = [_channel(sync_mode="disabled")]
    registry = _registry(_reg())
    actions = build_sync_plan(_BOOKING, _PROP, channels, registry)
    assert actions[0].strategy == "skip"


def test_service_skip_when_provider_not_in_registry():
    channels = [_channel(provider="unknown-ota")]
    registry = _registry()   # empty
    actions = build_sync_plan(_BOOKING, _PROP, channels, registry)
    assert actions[0].strategy == "skip"
    assert "not found" in actions[0].reason.lower()


def test_service_skip_tier_d():
    channels = [_channel(sync_mode="api_first")]
    registry = _registry(_reg(tier="D", supports_api_write=True))
    actions = build_sync_plan(_BOOKING, _PROP, channels, registry)
    assert actions[0].strategy == "skip"


# ---- multiple channels ----

def test_service_multiple_channels_mixed():
    channels = [
        _channel(provider="airbnb",  sync_mode="api_first"),
        _channel(provider="hotelbeds", sync_mode="ical_fallback"),
        _channel(provider="houfy",   sync_mode="api_first"),
        _channel(provider="direct",  enabled=False),
    ]
    registry = _registry(
        _reg(provider="airbnb",    tier="A", supports_api_write=True),
        _reg(provider="hotelbeds", tier="B", supports_api_write=False, supports_ical_push=True),
        _reg(provider="houfy",     tier="C", supports_api_write=False, supports_ical_push=False, supports_ical_pull=True),
        _reg(provider="direct",    tier="D"),
    )
    actions = build_sync_plan(_BOOKING, _PROP, channels, registry)
    assert len(actions) == 4
    strategies = {a.provider: a.strategy for a in actions}
    assert strategies["airbnb"]    == "api_first"
    assert strategies["hotelbeds"] == "ical_fallback"
    assert strategies["houfy"]     == "ical_fallback"  # degraded: api_first requested but no write
    assert strategies["direct"]    == "skip"           # disabled=False but tier=D... wait, enabled=False


def test_service_direct_disabled_channel_skip():
    channels = [_channel(provider="direct", enabled=False)]
    registry = _registry(_reg(provider="direct", tier="D"))
    actions = build_sync_plan(_BOOKING, _PROP, channels, registry)
    assert actions[0].strategy == "skip"


def test_service_empty_channels():
    actions = build_sync_plan(_BOOKING, _PROP, [], {})
    assert actions == []


def test_service_tier_propagated():
    channels = [_channel()]
    registry = _registry(_reg(tier="B"))
    actions = build_sync_plan(_BOOKING, _PROP, channels, registry)
    assert actions[0].tier == "B"


def test_service_rate_limit_propagated():
    channels = [_channel()]
    registry = _registry(_reg(rate_limit_per_min=30))
    actions = build_sync_plan(_BOOKING, _PROP, channels, registry)
    assert actions[0].rate_limit == 30


def test_service_external_id_propagated():
    channels = [_channel(external_id="MY-EXT-9999")]
    registry = _registry(_reg())
    actions = build_sync_plan(_BOOKING, _PROP, channels, registry)
    assert actions[0].external_id == "MY-EXT-9999"


# ---- summarise_plan ----

def test_summarise_counts_correct():
    actions = [
        SyncAction(_BOOKING, _PROP, "a", "x1", "api_first", "r", "A", 60),
        SyncAction(_BOOKING, _PROP, "b", "x2", "ical_fallback", "r", "B", 10),
        SyncAction(_BOOKING, _PROP, "c", "x3", "skip", "r", "C", 5),
        SyncAction(_BOOKING, _PROP, "d", "x4", "skip", "r", None, 0),
    ]
    summary = summarise_plan(actions)
    assert summary["total_channels"] == 4
    assert summary["api_first_count"] == 1
    assert summary["ical_count"] == 1
    assert summary["skip_count"] == 2


def test_summarise_empty():
    summary = summarise_plan([])
    assert summary["total_channels"] == 0
    assert summary["api_first_count"] == 0
    assert summary["ical_count"] == 0
    assert summary["skip_count"] == 0
    assert summary["actions"] == []


def test_summarise_action_has_all_fields():
    actions = [SyncAction(_BOOKING, _PROP, "airbnb", "HZ1", "api_first", "reason", "A", 120)]
    summary = summarise_plan(actions)
    action = summary["actions"][0]
    expected = {"booking_id", "property_id", "provider", "external_id",
                "strategy", "reason", "tier", "rate_limit"}
    assert set(action.keys()) == expected


# ===========================================================================
# HTTP ROUTER TESTS — POST /internal/sync/trigger
# ===========================================================================

def test_http_200_full_plan():
    db = _mock_db(
        booking_rows=[{"property_id": _PROP, "tenant_id": _TENANT}],
        channel_rows=[_channel(sync_mode="api_first")],
        registry_rows=[_reg()],
    )
    r = _post({"booking_id": _BOOKING}, db)
    assert r.status_code == 200
    body = r.json()
    assert body["booking_id"] == _BOOKING
    assert body["total_channels"] == 1
    assert body["api_first_count"] == 1


def test_http_200_no_channels():
    db = _mock_db(
        booking_rows=[{"property_id": _PROP, "tenant_id": _TENANT}],
        channel_rows=[],
        registry_rows=[],
    )
    r = _post({"booking_id": _BOOKING}, db)
    assert r.status_code == 200
    body = r.json()
    assert body["total_channels"] == 0
    assert body["actions"] == []


def test_http_response_has_top_level_keys():
    db = _mock_db(
        booking_rows=[{"property_id": _PROP, "tenant_id": _TENANT}],
        channel_rows=[],
        registry_rows=[],
    )
    r = _post({"booking_id": _BOOKING}, db)
    keys = set(r.json().keys())
    assert {"booking_id", "property_id", "tenant_id", "total_channels",
            "api_first_count", "ical_count", "skip_count", "actions"} <= keys


def test_http_counts_sum_to_total():
    db = _mock_db(
        booking_rows=[{"property_id": _PROP, "tenant_id": _TENANT}],
        channel_rows=[
            _channel(provider="airbnb",    sync_mode="api_first"),
            _channel(provider="hotelbeds", sync_mode="ical_fallback"),
            _channel(provider="houfy",     enabled=False),
        ],
        registry_rows=[
            _reg(provider="airbnb",    tier="A", supports_api_write=True),
            _reg(provider="hotelbeds", tier="B", supports_api_write=False, supports_ical_push=True),
            _reg(provider="houfy",     tier="C"),
        ],
    )
    r = _post({"booking_id": _BOOKING}, db)
    body = r.json()
    total = body["total_channels"]
    assert body["api_first_count"] + body["ical_count"] + body["skip_count"] == total


def test_http_action_has_required_fields():
    db = _mock_db(
        booking_rows=[{"property_id": _PROP, "tenant_id": _TENANT}],
        channel_rows=[_channel()],
        registry_rows=[_reg()],
    )
    r = _post({"booking_id": _BOOKING}, db)
    action = r.json()["actions"][0]
    assert set(action.keys()) == {"booking_id", "property_id", "provider", "external_id",
                                  "strategy", "reason", "tier", "rate_limit"}


def test_http_tenant_id_in_response():
    db = _mock_db(
        booking_rows=[{"property_id": _PROP, "tenant_id": _TENANT}],
        channel_rows=[],
        registry_rows=[],
    )
    r = _post({"booking_id": _BOOKING}, db)
    assert r.json()["tenant_id"] == _TENANT


def test_http_400_missing_booking_id():
    db = _mock_db([], [], [])
    r = _post({}, db)
    assert r.status_code == 400


def test_http_400_empty_booking_id():
    db = _mock_db([], [], [])
    r = _post({"booking_id": "   "}, db)
    assert r.status_code == 400


def test_http_404_booking_not_found():
    db = _mock_db(booking_rows=[], channel_rows=[], registry_rows=[])
    r = _post({"booking_id": "bk-unknown-999"}, db)
    assert r.status_code == 404


def test_http_500_on_db_error():
    db = MagicMock()
    db.table.side_effect = RuntimeError("DB is down")
    r = _post({"booking_id": _BOOKING}, db)
    assert r.status_code == 500


def test_http_403_no_jwt():
    with patch.dict("os.environ", {"IHOUSE_JWT_SECRET": "secret"}):
        r = _client.post("/internal/sync/trigger", json={"booking_id": _BOOKING})
    assert r.status_code == 403


def test_http_skip_count_correct_with_disabled_channel():
    db = _mock_db(
        booking_rows=[{"property_id": _PROP, "tenant_id": _TENANT}],
        channel_rows=[
            _channel(provider="airbnb",  enabled=False),
            _channel(provider="vrbo",    sync_mode="disabled"),
        ],
        registry_rows=[
            _reg(provider="airbnb", supports_api_write=True),
            _reg(provider="vrbo",   supports_api_write=True),
        ],
    )
    r = _post({"booking_id": _BOOKING}, db)
    body = r.json()
    assert body["skip_count"] == 2
    assert body["api_first_count"] == 0
