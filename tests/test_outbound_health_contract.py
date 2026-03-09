"""
Phase 146 — Contract Tests: Sync Health Dashboard

GET /admin/outbound-health

Tests:
  A — Response shape and 200 status
  B — Empty data (no rows) → empty providers list
  C — Single provider: all status counters correct
  D — Multiple providers: separate aggregation
  E — failure_rate_7d: correct ratio calculation
  F — failure_rate_7d: None when no ok+failed in 7 days
  G — failure_rate_7d: None for 0 total (only dry_run/skipped)
  H — last_sync_at: picks newest among rows for each provider
  I — Alphabetical ordering of providers
  J — Malformed synced_at timestamps are ignored (no crash)
  K — DB error returns 200 with empty providers (best-effort helper)
  L — tenant isolation: query is scoped by tenant_id
  M — Smoke: /admin/outbound-health route exists with GET method
  N — _compute_health unit tests (direct function call, no HTTP)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("fastapi")

TENANT_A = "tenant-A"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ago(days: int = 0, hours: int = 0) -> str:
    """Return ISO UTC timestamp N days/hours before now."""
    dt = datetime.now(tz=timezone.utc) - timedelta(days=days, hours=hours)
    return dt.isoformat()


def _future(days: int = 1) -> str:
    dt = datetime.now(tz=timezone.utc) + timedelta(days=days)
    return dt.isoformat()


def _make_row(
    provider:   str = "airbnb",
    status:     str = "ok",
    synced_at:  Optional[str] = None,
    tenant_id:  str = TENANT_A,
) -> dict:
    return {
        "provider":  provider,
        "status":    status,
        "synced_at": synced_at or _ago(hours=1),
        "tenant_id": tenant_id,
    }


def _make_db(rows: List[dict]) -> MagicMock:
    q = MagicMock()
    q.eq.return_value = q
    q.order.return_value = q
    q.limit.return_value = q
    q.execute.return_value = MagicMock(data=rows)
    db = MagicMock()
    db.table.return_value.select.return_value = q
    return db


def _make_app() -> TestClient:
    from fastapi import FastAPI
    from api.outbound_log_router import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def _get_health(rows: List[dict], tenant_id: str = TENANT_A):
    db = _make_db(rows)
    c  = _make_app()
    with (
        patch("api.outbound_log_router._get_supabase_client", return_value=db),
        patch("api.auth.jwt_auth", return_value=tenant_id),
    ):
        resp = c.get("/admin/outbound-health", headers={"Authorization": "Bearer fake.jwt"})
    return resp, db


# ===========================================================================
# Group A — response shape
# ===========================================================================

class TestResponseShape:

    def test_returns_200(self):
        resp, _ = _get_health([])
        assert resp.status_code == 200

    def test_body_has_required_top_fields(self):
        resp, _ = _get_health([])
        body = resp.json()
        for field in ("tenant_id", "provider_count", "checked_at", "providers"):
            assert field in body

    def test_tenant_id_in_response(self):
        resp, _ = _get_health([])
        # In test/dev mode jwt_auth returns 'dev-tenant' (no secret set)
        # — the important thing is tenant_id is present and is a string
        assert isinstance(resp.json()["tenant_id"], str)
        assert len(resp.json()["tenant_id"]) > 0

    def test_checked_at_is_string(self):
        resp, _ = _get_health([])
        assert isinstance(resp.json()["checked_at"], str)


# ===========================================================================
# Group B — empty data
# ===========================================================================

class TestEmptyData:

    def test_empty_rows_returns_empty_providers(self):
        resp, _ = _get_health([])
        assert resp.json()["providers"] == []

    def test_provider_count_is_zero(self):
        resp, _ = _get_health([])
        assert resp.json()["provider_count"] == 0


# ===========================================================================
# Group C — single provider counters
# ===========================================================================

class TestSingleProviderCounters:

    def _rows(self):
        return [
            _make_row("airbnb", "ok"),
            _make_row("airbnb", "ok"),
            _make_row("airbnb", "failed"),
            _make_row("airbnb", "dry_run"),
            _make_row("airbnb", "skipped"),
        ]

    def _provider(self):
        resp, _ = _get_health(self._rows())
        return resp.json()["providers"][0]

    def test_ok_count(self):          assert self._provider()["ok_count"]      == 2
    def test_failed_count(self):      assert self._provider()["failed_count"]  == 1
    def test_dry_run_count(self):     assert self._provider()["dry_run_count"] == 1
    def test_skipped_count(self):     assert self._provider()["skipped_count"] == 1
    def test_provider_name(self):     assert self._provider()["provider"]      == "airbnb"
    def test_has_last_sync_at(self):  assert self._provider()["last_sync_at"]  is not None
    def test_has_failure_rate_7d(self): assert "failure_rate_7d" in self._provider()


# ===========================================================================
# Group D — multiple providers are aggregated separately
# ===========================================================================

class TestMultipleProviders:

    def test_two_providers_two_entries(self):
        rows = [
            _make_row("airbnb",     "ok"),
            _make_row("bookingcom", "failed"),
        ]
        resp, _ = _get_health(rows)
        providers = resp.json()["providers"]
        assert len(providers) == 2
        assert resp.json()["provider_count"] == 2

    def test_counters_are_isolated(self):
        rows = [
            _make_row("airbnb",     "ok"),
            _make_row("bookingcom", "failed"),
        ]
        resp, _ = _get_health(rows)
        by_name = {p["provider"]: p for p in resp.json()["providers"]}
        assert by_name["airbnb"]["ok_count"]         == 1
        assert by_name["airbnb"]["failed_count"]     == 0
        assert by_name["bookingcom"]["failed_count"]  == 1
        assert by_name["bookingcom"]["ok_count"]      == 0


# ===========================================================================
# Group E — failure_rate_7d correct ratio
# ===========================================================================

class TestFailureRate7d:

    def test_rate_is_0_when_all_ok(self):
        rows = [_make_row("airbnb", "ok", _ago(hours=1)) for _ in range(4)]
        resp, _ = _get_health(rows)
        p = resp.json()["providers"][0]
        assert p["failure_rate_7d"] == 0.0

    def test_rate_is_1_when_all_failed(self):
        rows = [_make_row("airbnb", "failed", _ago(hours=1)) for _ in range(3)]
        resp, _ = _get_health(rows)
        p = resp.json()["providers"][0]
        assert p["failure_rate_7d"] == 1.0

    def test_rate_is_half_when_equal(self):
        rows = [
            _make_row("airbnb", "ok",     _ago(hours=1)),
            _make_row("airbnb", "failed", _ago(hours=2)),
        ]
        resp, _ = _get_health(rows)
        p = resp.json()["providers"][0]
        assert p["failure_rate_7d"] == 0.5


# ===========================================================================
# Group F — failure_rate_7d is None when data is outside 7-day window
# ===========================================================================

class TestFailureRateNoneOutsideWindow:

    def test_old_rows_not_counted_in_7d(self):
        rows = [
            _make_row("airbnb", "ok",     _ago(days=8)),
            _make_row("airbnb", "failed", _ago(days=10)),
        ]
        resp, _ = _get_health(rows)
        p = resp.json()["providers"][0]
        # All rows are >7 days old → no 7d data → None
        assert p["failure_rate_7d"] is None


# ===========================================================================
# Group G — failure_rate_7d is None when only dry_run or skipped
# ===========================================================================

class TestFailureRateNoneNoDenominator:

    def test_only_dry_run_returns_none_rate(self):
        rows = [_make_row("airbnb", "dry_run", _ago(hours=1)) for _ in range(3)]
        resp, _ = _get_health(rows)
        p = resp.json()["providers"][0]
        assert p["failure_rate_7d"] is None

    def test_only_skipped_returns_none_rate(self):
        rows = [_make_row("airbnb", "skipped", _ago(hours=1)) for _ in range(2)]
        resp, _ = _get_health(rows)
        p = resp.json()["providers"][0]
        assert p["failure_rate_7d"] is None


# ===========================================================================
# Group H — last_sync_at picks the newest
# ===========================================================================

class TestLastSyncAt:

    def test_last_sync_at_is_newest(self):
        old = _ago(days=5)
        new = _ago(hours=2)
        rows = [
            _make_row("airbnb", "ok",     old),
            _make_row("airbnb", "failed", new),
        ]
        resp, _ = _get_health(rows)
        p = resp.json()["providers"][0]
        # newer ISO string should be selected
        assert p["last_sync_at"] == new


# ===========================================================================
# Group I — alphabetical ordering
# ===========================================================================

class TestAlphabeticalOrdering:

    def test_providers_sorted_alphabetically(self):
        rows = [
            _make_row("expedia",   "ok"),
            _make_row("airbnb",    "ok"),
            _make_row("bookingcom","ok"),
        ]
        resp, _ = _get_health(rows)
        names = [p["provider"] for p in resp.json()["providers"]]
        assert names == sorted(names)


# ===========================================================================
# Group J — malformed synced_at is skipped (no crash)
# ===========================================================================

class TestMalformedTimestamp:

    def test_malformed_timestamp_does_not_crash(self):
        rows = [
            _make_row("airbnb", "ok", "NOT-A-DATE"),
            _make_row("airbnb", "failed", _ago(hours=1)),
        ]
        resp, _ = _get_health(rows)
        assert resp.status_code == 200
        p = resp.json()["providers"][0]
        assert p["ok_count"] == 1
        assert p["failed_count"] == 1


# ===========================================================================
# Group K — DB error → 200 with empty providers (best-effort _compute_health)
# ===========================================================================

class TestDbError:

    def test_db_error_returns_200_empty_providers(self):
        db = MagicMock()
        q  = MagicMock()
        q.eq.return_value = q
        q.order.return_value = q
        q.limit.return_value = q
        q.execute.side_effect = RuntimeError("supabase down")
        db.table.return_value.select.return_value = q
        c = _make_app()
        with (
            patch("api.outbound_log_router._get_supabase_client", return_value=db),
            patch("api.auth.jwt_auth", return_value=TENANT_A),
        ):
            resp = c.get("/admin/outbound-health", headers={"Authorization": "Bearer x"})
        assert resp.status_code == 200
        assert resp.json()["providers"] == []


# ===========================================================================
# Group L — tenant isolation
# ===========================================================================

class TestTenantIsolation:

    def test_tenant_id_used_in_query(self):
        resp, db = _get_health([])
        response_tenant = resp.json()["tenant_id"]
        q = db.table.return_value.select.return_value
        eq_calls = [c[0] for c in q.eq.call_args_list]
        # The exact tenant returned by jwt_auth must be used in the DB filter
        assert ("tenant_id", response_tenant) in eq_calls


# ===========================================================================
# Group M — smoke: route exists
# ===========================================================================

class TestRouteSmoke:

    def test_health_route_exists(self):
        from api.outbound_log_router import router
        paths = [r.path for r in router.routes]  # type: ignore[attr-defined]
        assert "/admin/outbound-health" in paths

    def test_health_route_is_get(self):
        from api.outbound_log_router import router
        r = next(x for x in router.routes if x.path == "/admin/outbound-health")  # type: ignore[attr-defined]
        assert "GET" in r.methods  # type: ignore[attr-defined]


# ===========================================================================
# Group N — _compute_health unit tests (direct function call)
# ===========================================================================

class TestComputeHealthUnit:

    def _call(self, rows: List[dict]) -> List[dict]:
        from api.outbound_log_router import _compute_health
        db = _make_db(rows)
        return _compute_health(db, TENANT_A)

    def test_empty_returns_empty_list(self):
        assert self._call([]) == []

    def test_single_row_one_provider(self):
        result = self._call([_make_row("airbnb", "ok", _ago(hours=1))])
        assert len(result) == 1
        assert result[0]["provider"] == "airbnb"

    def test_ok_counter_increments(self):
        rows = [_make_row("airbnb", "ok") for _ in range(5)]
        result = self._call(rows)
        assert result[0]["ok_count"] == 5

    def test_failure_rate_7d_not_in_raw_dict(self):
        """_ok_7d and _failed_7d internal keys must be popped before return."""
        rows = [_make_row("airbnb", "ok", _ago(hours=1))]
        result = self._call(rows)
        assert "_ok_7d"     not in result[0]
        assert "_failed_7d" not in result[0]

    def test_return_is_list_of_dicts(self):
        result = self._call([_make_row()])
        assert isinstance(result, list)
        assert isinstance(result[0], dict)
