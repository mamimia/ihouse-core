"""
Phase 138 — Outbound Executor Contract Tests

Two test suites:
  1. Service layer (outbound_executor.py) — covers execute_sync_plan logic
  2. HTTP router (outbound_executor_router.py) — covers request/response contract

SERVICE LAYER CONTRACTS:
-----------------------------------------------------------------------
  execute_sync_plan:
    - empty actions → empty report
    - all-skip actions → skip_count correct, ok=0, failed=0
    - api_first action → ok_count=1, status=dry_run
    - ical_fallback action → ok_count=1, status=dry_run
    - mixed actions (api_first + ical + skip) → counts correct
    - fail-isolated: one action exception doesn't prevent others
    - dry_run=True when all non-skip results are dry_run
    - dry_run=False when no non-skip results exist (all skipped)
    - custom adapter override works
    - ExecutionResult fields propagated correctly
    - report total_actions == len(actions)
  serialise_report:
    - top-level keys correct
    - results list serialisable
    - result has all expected fields

HTTP ROUTER CONTRACTS (POST /internal/sync/execute):
-----------------------------------------------------------------------
  200:
    - booking found, channels → report returned
    - booking found, no channels → empty report
    - report has all top-level keys
    - report.results has correct shape
    - dry_run flag present
    - skip_count correct for disabled channels
  400:
    - missing booking_id
    - empty booking_id
  403:
    - JWT missing
  404:
    - booking not found
  500:
    - DB error
-----------------------------------------------------------------------
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.outbound_executor_router import router
from services.outbound_executor import (
    ExecutionReport,
    ExecutionResult,
    execute_sync_plan,
    serialise_report,
)
from services.outbound_sync_trigger import SyncAction

_app = FastAPI()
_app.include_router(router)
_client = TestClient(_app, raise_server_exceptions=False)

_TENANT  = "tenant-phase-138"
_BOOKING = "bk-phase138-001"
_PROP    = "prop-villa-beta"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _action(
    provider: str = "airbnb",
    external_id: str = "HZ138",
    strategy: str = "api_first",
    reason: str = "test reason",
    tier: str = "A",
    rate_limit: int = 120,
) -> SyncAction:
    return SyncAction(
        booking_id=_BOOKING,
        property_id=_PROP,
        provider=provider,
        external_id=external_id,
        strategy=strategy,
        reason=reason,
        tier=tier,
        rate_limit=rate_limit,
    )


def _mock_db(booking_rows: list, channel_rows: list, registry_rows: list) -> MagicMock:
    db = MagicMock()
    booking_result  = MagicMock(); booking_result.data  = booking_rows
    channel_result  = MagicMock(); channel_result.data  = channel_rows
    registry_result = MagicMock(); registry_result.data = registry_rows

    booking_table = MagicMock()
    (
        booking_table.select.return_value
        .eq.return_value.eq.return_value
        .limit.return_value.execute.return_value
    ) = booking_result

    channel_table = MagicMock()
    (
        channel_table.select.return_value
        .eq.return_value.eq.return_value
        .execute.return_value
    ) = channel_result

    registry_table = MagicMock()
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
    with patch("api.outbound_executor_router._get_supabase_client", return_value=db):
        r = _client.post("/internal/sync/execute", json=body)
    _clear()
    return r


def _channel(provider: str, sync_mode: str = "api_first", enabled: bool = True) -> dict:
    return {
        "provider": provider, "external_id": f"{provider}-ext-001",
        "sync_mode": sync_mode, "enabled": enabled,
        "tenant_id": _TENANT, "property_id": _PROP,
    }


def _reg(provider: str, tier: str = "A", supports_api_write: bool = True,
         supports_ical_push: bool = False, supports_ical_pull: bool = True) -> dict:
    return {
        "provider": provider, "tier": tier,
        "supports_api_write": supports_api_write,
        "supports_ical_push": supports_ical_push,
        "supports_ical_pull": supports_ical_pull,
        "rate_limit_per_min": 60,
    }


# ===========================================================================
# SERVICE LAYER TESTS
# ===========================================================================

def test_service_empty_actions():
    report = execute_sync_plan(_BOOKING, _PROP, _TENANT, [])
    assert report.total_actions == 0
    assert report.ok_count == 0
    assert report.failed_count == 0
    assert report.skip_count == 0
    assert report.results == []


def test_service_all_skip():
    actions = [
        _action(strategy="skip", reason="disabled"),
        _action(provider="vrbo", strategy="skip", reason="tier D"),
    ]
    report = execute_sync_plan(_BOOKING, _PROP, _TENANT, actions)
    assert report.skip_count == 2
    assert report.ok_count == 0
    assert report.failed_count == 0
    assert all(r.status == "skipped" for r in report.results)


def test_service_api_first_dry_run():
    actions = [_action(strategy="api_first")]
    report = execute_sync_plan(_BOOKING, _PROP, _TENANT, actions)
    assert report.ok_count == 1
    assert report.results[0].status == "dry_run"
    assert report.results[0].strategy == "api_first"


def test_service_ical_fallback_dry_run():
    actions = [_action(strategy="ical_fallback", tier="B", rate_limit=10)]
    report = execute_sync_plan(_BOOKING, _PROP, _TENANT, actions)
    assert report.ok_count == 1
    assert report.results[0].status == "dry_run"
    assert report.results[0].strategy == "ical_fallback"


def test_service_mixed_actions():
    actions = [
        _action(provider="airbnb", strategy="api_first"),
        _action(provider="hotelbeds", strategy="ical_fallback", tier="B"),
        _action(provider="direct", strategy="skip", reason="tier D"),
    ]
    report = execute_sync_plan(_BOOKING, _PROP, _TENANT, actions)
    assert report.total_actions == 3
    assert report.ok_count == 2
    assert report.skip_count == 1
    assert report.failed_count == 0


def test_service_fail_isolated():
    """One failing adapter doesn't block other actions."""
    class FailingAdapter:
        @staticmethod
        def send(provider, external_id, booking_id, rate_limit):
            raise RuntimeError("network down")

    actions = [
        _action(provider="airbnb",  strategy="api_first"),
        _action(provider="vrbo",    strategy="api_first"),
    ]
    report = execute_sync_plan(
        _BOOKING, _PROP, _TENANT, actions,
        api_adapter=FailingAdapter,
    )
    assert report.total_actions == 2
    assert report.failed_count == 2
    assert report.ok_count == 0
    assert all(r.status == "failed" for r in report.results)


def test_service_dry_run_true_when_all_dry():
    actions = [_action(strategy="api_first")]
    report = execute_sync_plan(_BOOKING, _PROP, _TENANT, actions)
    assert report.dry_run is True


def test_service_dry_run_false_when_all_skipped():
    actions = [_action(strategy="skip")]
    report = execute_sync_plan(_BOOKING, _PROP, _TENANT, actions)
    assert report.dry_run is False


def test_service_total_actions_equals_input():
    actions = [_action(strategy=s) for s in ["api_first", "ical_fallback", "skip"]]
    report = execute_sync_plan(_BOOKING, _PROP, _TENANT, actions)
    assert report.total_actions == 3


def test_service_result_fields_populated():
    actions = [_action(provider="airbnb", external_id="HZ-999", strategy="api_first")]
    report = execute_sync_plan(_BOOKING, _PROP, _TENANT, actions)
    r = report.results[0]
    assert r.provider == "airbnb"
    assert r.external_id == "HZ-999"
    assert r.strategy == "api_first"
    assert r.message  # non-empty


def test_service_skip_reason_propagated():
    actions = [_action(strategy="skip", reason="channel disabled")]
    report = execute_sync_plan(_BOOKING, _PROP, _TENANT, actions)
    assert "channel disabled" in report.results[0].message


def test_service_custom_adapter_used():
    class FakeAdapter:
        called = False
        @classmethod
        def send(cls, provider, external_id, booking_id, rate_limit):
            cls.called = True
            return ExecutionResult(provider, external_id, "api_first", "ok", 200, "ok from fake")

    actions = [_action(strategy="api_first")]
    report = execute_sync_plan(_BOOKING, _PROP, _TENANT, actions, api_adapter=FakeAdapter)
    assert FakeAdapter.called
    assert report.results[0].status == "ok"


def test_service_report_booking_id():
    report = execute_sync_plan(_BOOKING, _PROP, _TENANT, [])
    assert report.booking_id == _BOOKING


def test_service_report_tenant_id():
    report = execute_sync_plan(_BOOKING, _PROP, _TENANT, [])
    assert report.tenant_id == _TENANT


# ---- serialise_report ----

def test_serialise_top_level_keys():
    report = execute_sync_plan(_BOOKING, _PROP, _TENANT, [])
    s = serialise_report(report)
    assert set(s.keys()) == {
        "booking_id", "property_id", "tenant_id",
        "total_actions", "ok_count", "failed_count", "skip_count",
        "dry_run", "results"
    }


def test_serialise_result_fields():
    actions = [_action(strategy="api_first")]
    report = execute_sync_plan(_BOOKING, _PROP, _TENANT, actions)
    s = serialise_report(report)
    result = s["results"][0]
    assert set(result.keys()) == {
        "provider", "external_id", "strategy", "status", "http_status", "message"
    }


def test_serialise_dry_run_propagated():
    actions = [_action(strategy="api_first")]
    report = execute_sync_plan(_BOOKING, _PROP, _TENANT, actions)
    s = serialise_report(report)
    assert s["dry_run"] is True


# ===========================================================================
# HTTP ROUTER TESTS
# ===========================================================================

def test_http_200_full_report():
    db = _mock_db(
        booking_rows=[{"property_id": _PROP, "tenant_id": _TENANT}],
        channel_rows=[_channel("airbnb", "api_first")],
        registry_rows=[_reg("airbnb", "A", supports_api_write=True)],
    )
    r = _post({"booking_id": _BOOKING}, db)
    assert r.status_code == 200
    body = r.json()
    assert body["booking_id"] == _BOOKING
    assert body["total_actions"] == 1


def test_http_200_no_channels():
    db = _mock_db(
        booking_rows=[{"property_id": _PROP, "tenant_id": _TENANT}],
        channel_rows=[],
        registry_rows=[],
    )
    r = _post({"booking_id": _BOOKING}, db)
    assert r.status_code == 200
    assert r.json()["total_actions"] == 0
    assert r.json()["results"] == []


def test_http_top_level_keys():
    db = _mock_db(
        booking_rows=[{"property_id": _PROP, "tenant_id": _TENANT}],
        channel_rows=[],
        registry_rows=[],
    )
    r = _post({"booking_id": _BOOKING}, db)
    assert set(r.json().keys()) == {
        "booking_id", "property_id", "tenant_id",
        "total_actions", "ok_count", "failed_count", "skip_count",
        "dry_run", "results"
    }


def test_http_result_shape():
    db = _mock_db(
        booking_rows=[{"property_id": _PROP, "tenant_id": _TENANT}],
        channel_rows=[_channel("airbnb", "api_first")],
        registry_rows=[_reg("airbnb")],
    )
    r = _post({"booking_id": _BOOKING}, db)
    result = r.json()["results"][0]
    assert set(result.keys()) == {
        "provider", "external_id", "strategy", "status", "http_status", "message"
    }


def test_http_dry_run_flag_present():
    db = _mock_db(
        booking_rows=[{"property_id": _PROP, "tenant_id": _TENANT}],
        channel_rows=[_channel("airbnb")],
        registry_rows=[_reg("airbnb")],
    )
    r = _post({"booking_id": _BOOKING}, db)
    assert "dry_run" in r.json()


def test_http_skip_count_disabled_channel():
    db = _mock_db(
        booking_rows=[{"property_id": _PROP, "tenant_id": _TENANT}],
        channel_rows=[
            _channel("airbnb", "api_first", enabled=False),
            _channel("vrbo",   "disabled"),
        ],
        registry_rows=[_reg("airbnb"), _reg("vrbo")],
    )
    r = _post({"booking_id": _BOOKING}, db)
    body = r.json()
    assert body["skip_count"] == 2
    assert body["ok_count"] == 0


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
    r = _post({"booking_id": "unknown"}, db)
    assert r.status_code == 404


def test_http_500_on_db_error():
    db = MagicMock()
    db.table.side_effect = RuntimeError("DB down")
    r = _post({"booking_id": _BOOKING}, db)
    assert r.status_code == 500


def test_http_403_no_jwt():
    with patch.dict("os.environ", {"IHOUSE_JWT_SECRET": "test-secret"}):
        r = _client.post("/internal/sync/execute", json={"booking_id": _BOOKING})
    assert r.status_code == 403


def test_http_tenant_propagated():
    db = _mock_db(
        booking_rows=[{"property_id": _PROP, "tenant_id": _TENANT}],
        channel_rows=[],
        registry_rows=[],
    )
    r = _post({"booking_id": _BOOKING}, db)
    assert r.json()["tenant_id"] == _TENANT


def test_http_ical_channel_dispatched():
    db = _mock_db(
        booking_rows=[{"property_id": _PROP, "tenant_id": _TENANT}],
        channel_rows=[_channel("hotelbeds", "ical_fallback")],
        registry_rows=[_reg("hotelbeds", "B", supports_api_write=False, supports_ical_push=True)],
    )
    r = _post({"booking_id": _BOOKING}, db)
    body = r.json()
    assert body["ok_count"] == 1
    assert body["results"][0]["strategy"] == "ical_fallback"
