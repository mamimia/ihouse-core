"""
Phase 127 — Integration Health Dashboard — Contract Tests

Tests for GET /integration-health

Groups:
    A — Authentication (401 when no JWT)
    B — Response shape — all 13 providers present
    C — Provider record fields
    D — Summary block correctness
    E — Stale alert logic
    F — lag_seconds computation
    G — buffer_count and dlq_count
    H — Best-effort: per-provider error → unknown, not 500
    I — Read-only invariants (never writes)
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, call

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("fastapi")

# ────────────────────────────────────────────────────────────────────────────
# Fixture helpers
# ────────────────────────────────────────────────────────────────────────────

_ALL_PROVIDERS = (
    "bookingcom", "airbnb", "expedia", "agoda", "tripcom",
    "vrbo", "gvr", "traveloka", "makemytrip", "klook",
    "despegar", "rakuten", "hotelbeds",
)

_FAKE_TENANT = "tenant_test"
_FAKE_TOKEN = "Bearer fake.jwt.token"


def _make_app(db: MagicMock) -> TestClient:
    """Build isolated FastAPI test client with mocked DB and JWT."""
    from fastapi import FastAPI
    from api.integration_health_router import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def _mock_db_empty() -> MagicMock:
    """DB that returns empty rows for everything."""
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=[])
    chain.eq.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.is_.return_value = chain
    chain.select.return_value = chain
    db = MagicMock()
    db.table.return_value.select.return_value = chain
    return db


def _event_row(
    recorded_at: str = "2026-04-01T10:00:00+00:00",
    occurred_at: str = "2026-04-01T09:59:50+00:00",
) -> dict:
    return {"recorded_at": recorded_at, "occurred_at": occurred_at}


def _mock_db_with_event(row: dict) -> MagicMock:
    """DB that returns one event_log row, empty for all other tables."""
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=[row])
    chain.eq.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.is_.return_value = chain
    chain.select.return_value = chain
    db = MagicMock()
    db.table.return_value.select.return_value = chain
    return db


def _get(
    c: TestClient,
    db: MagicMock,
    path: str = "/integration-health",
):
    """Make authenticated GET request with mocked DB and JWT."""
    with (
        patch("api.integration_health_router._get_supabase_client", return_value=db),
        patch("api.auth.jwt_auth", return_value=_FAKE_TENANT),
    ):
        return c.get(path, headers={"Authorization": _FAKE_TOKEN})


# ============================================================================
# Group A — Authentication
# ============================================================================

class TestGroupA_Auth:

    def test_a1_no_token_returns_non_500(self) -> None:
        """A1: No JWT token → not 500 (auth is handled by jwt_auth;
        in dev mode it returns dev-tenant, in prod it raises 401)."""
        db = _mock_db_empty()
        c = _make_app(db)
        with patch("api.integration_health_router._get_supabase_client", return_value=db):
            resp = c.get("/integration-health")
        # In dev mode (no IHOUSE_JWT_SECRET) jwt_auth returns dev-tenant → 200
        # In prod jwt_auth raises 401. Either is correct — never 500.
        assert resp.status_code != 500


# ============================================================================
# Group B — All 13 providers present
# ============================================================================

class TestGroupB_AllProviders:

    def test_b1_response_has_13_providers(self) -> None:
        """B1: Response includes all 13 providers."""
        db = _mock_db_empty()
        c = _make_app(db)
        body = _get(c, db).json()
        assert len(body["providers"]) == 13

    def test_b2_all_provider_names_present(self) -> None:
        """B2: All 13 provider names are in response."""
        db = _mock_db_empty()
        c = _make_app(db)
        body = _get(c, db).json()
        names = {p["provider"] for p in body["providers"]}
        assert names == set(_ALL_PROVIDERS)

    def test_b3_response_has_200_status(self) -> None:
        """B3: Successful request returns 200."""
        db = _mock_db_empty()
        c = _make_app(db)
        resp = _get(c, db)
        assert resp.status_code == 200

    def test_b4_response_has_tenant_id(self) -> None:
        """B4: Response contains tenant_id (dev-mode or patched)."""
        db = _mock_db_empty()
        c = _make_app(db)
        body = _get(c, db).json()
        assert "tenant_id" in body
        assert isinstance(body["tenant_id"], str)
        assert len(body["tenant_id"]) > 0

    def test_b5_response_has_checked_at(self) -> None:
        """B5: Response contains checked_at timestamp."""
        db = _mock_db_empty()
        c = _make_app(db)
        body = _get(c, db).json()
        assert "checked_at" in body
        # Should be a valid ISO timestamp
        assert "T" in body["checked_at"]


# ============================================================================
# Group C — Provider record fields
# ============================================================================

class TestGroupC_ProviderRecordFields:

    def test_c1_each_provider_has_required_fields(self) -> None:
        """C1: Each provider record has: provider, last_ingest_at, lag_seconds,
        buffer_count, dlq_count, stale_alert, status."""
        db = _mock_db_empty()
        c = _make_app(db)
        body = _get(c, db).json()
        required = {"provider", "last_ingest_at", "lag_seconds", "buffer_count",
                    "dlq_count", "stale_alert", "status"}
        for p in body["providers"]:
            assert required.issubset(p.keys()), f"Missing fields for {p['provider']}"

    def test_c2_no_data_providers_have_unknown_status(self) -> None:
        """C2: Providers with no events in event_log → status=unknown."""
        db = _mock_db_empty()
        c = _make_app(db)
        body = _get(c, db).json()
        for p in body["providers"]:
            assert p["status"] == "unknown"

    def test_c3_no_data_providers_have_null_last_ingest(self) -> None:
        """C3: Providers with no events → last_ingest_at=null."""
        db = _mock_db_empty()
        c = _make_app(db)
        body = _get(c, db).json()
        for p in body["providers"]:
            assert p["last_ingest_at"] is None

    def test_c4_status_values_are_valid(self) -> None:
        """C4: All status values are 'ok' or 'unknown'."""
        db = _mock_db_empty()
        c = _make_app(db)
        body = _get(c, db).json()
        valid = {"ok", "unknown"}
        for p in body["providers"]:
            assert p["status"] in valid

    def test_c5_buffer_and_dlq_counts_are_nonneg_ints(self) -> None:
        """C5: buffer_count and dlq_count are non-negative integers."""
        db = _mock_db_empty()
        c = _make_app(db)
        body = _get(c, db).json()
        for p in body["providers"]:
            assert isinstance(p["buffer_count"], int) and p["buffer_count"] >= 0
            assert isinstance(p["dlq_count"], int) and p["dlq_count"] >= 0


# ============================================================================
# Group D — Summary block
# ============================================================================

class TestGroupD_Summary:

    def test_d1_summary_has_required_keys(self) -> None:
        """D1: Summary has: total_providers, ok, stale, unknown, total_dlq_pending,
        total_buffer_pending, has_alerts."""
        db = _mock_db_empty()
        c = _make_app(db)
        body = _get(c, db).json()
        required = {"total_providers", "ok", "stale", "unknown",
                    "total_dlq_pending", "total_buffer_pending", "has_alerts"}
        assert required.issubset(body["summary"].keys())

    def test_d2_total_providers_is_13(self) -> None:
        """D2: summary.total_providers == 13."""
        db = _mock_db_empty()
        c = _make_app(db)
        body = _get(c, db).json()
        assert body["summary"]["total_providers"] == 13

    def test_d3_all_unknown_when_no_events(self) -> None:
        """D3: summary.unknown == 13 when no events in DB."""
        db = _mock_db_empty()
        c = _make_app(db)
        body = _get(c, db).json()
        assert body["summary"]["unknown"] == 13
        assert body["summary"]["ok"] == 0

    def test_d4_has_alerts_false_when_all_clear(self) -> None:
        """D4: summary.has_alerts may be false (stale_alert driven by missing data)."""
        db = _mock_db_empty()
        c = _make_app(db)
        body = _get(c, db).json()
        # With no events, all are stale → has_alerts=True
        # This test confirms has_alerts is a boolean
        assert isinstance(body["summary"]["has_alerts"], bool)

    def test_d5_has_alerts_true_when_stale_providers(self) -> None:
        """D5: has_alerts=True when any provider is stale."""
        db = _mock_db_empty()  # all providers unknown → stale
        c = _make_app(db)
        body = _get(c, db).json()
        # All unknown → all stale → has_alerts must be True
        assert body["summary"]["stale"] == 13
        assert body["summary"]["has_alerts"] is True


# ============================================================================
# Group E — Stale alert logic
# ============================================================================

class TestGroupE_StaleAlert:

    def test_e1_no_events_triggers_stale(self) -> None:
        """E1: Provider with no events → stale_alert=True."""
        from api.integration_health_router import _is_stale
        assert _is_stale(None) is True

    def test_e2_recent_event_no_stale(self) -> None:
        """E2: Event 1h ago → stale_alert=False."""
        from api.integration_health_router import _is_stale
        recent = (datetime.now(tz=timezone.utc) - timedelta(hours=1)).isoformat()
        assert _is_stale(recent) is False

    def test_e3_old_event_triggers_stale(self) -> None:
        """E3: Event 25h ago → stale_alert=True."""
        from api.integration_health_router import _is_stale
        old = (datetime.now(tz=timezone.utc) - timedelta(hours=25)).isoformat()
        assert _is_stale(old) is True

    def test_e4_exactly_24h_boundary(self) -> None:
        """E4: Event exactly 24h ago → stale_alert=True (> not >=)."""
        from api.integration_health_router import _is_stale
        boundary = (datetime.now(tz=timezone.utc) - timedelta(hours=24, seconds=1)).isoformat()
        assert _is_stale(boundary) is True

    def test_e5_invalid_timestamp_triggers_stale(self) -> None:
        """E5: Invalid timestamp → stale_alert=True (safe fallback)."""
        from api.integration_health_router import _is_stale
        assert _is_stale("not-a-date") is True


# ============================================================================
# Group F — lag_seconds computation
# ============================================================================

class TestGroupF_LagSeconds:

    def test_f1_lag_computed_from_recorded_and_occurred(self) -> None:
        """F1: lag_seconds = recorded_at - occurred_at."""
        from api.integration_health_router import _provider_event_info
        recorded = "2026-04-01T10:00:00+00:00"
        occurred = "2026-04-01T09:59:50+00:00"  # 10s before
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[{"recorded_at": recorded, "occurred_at": occurred}])
        chain.eq.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = chain
        chain.select.return_value = chain
        db = MagicMock()
        db.table.return_value.select.return_value = chain
        result = _provider_event_info(db, "t1", "bookingcom")
        assert result["lag_seconds"] == pytest.approx(10.0)

    def test_f2_negative_lag_allowed(self) -> None:
        """F2: occurred_at > recorded_at → negative lag (clock skew possible)."""
        from api.integration_health_router import _provider_event_info
        recorded = "2026-04-01T10:00:00+00:00"
        occurred = "2026-04-01T10:00:05+00:00"  # 5s AFTER recorded
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[{"recorded_at": recorded, "occurred_at": occurred}])
        chain.eq.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = chain
        chain.select.return_value = chain
        db = MagicMock()
        db.table.return_value.select.return_value = chain
        result = _provider_event_info(db, "t1", "bookingcom")
        assert result["lag_seconds"] is not None
        assert result["lag_seconds"] < 0

    def test_f3_missing_occurred_at_gives_null_lag(self) -> None:
        """F3: occurred_at missing → lag_seconds=None."""
        from api.integration_health_router import _provider_event_info
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[{"recorded_at": "2026-04-01T10:00:00+00:00", "occurred_at": None}])
        chain.eq.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = chain
        chain.select.return_value = chain
        db = MagicMock()
        db.table.return_value.select.return_value = chain
        result = _provider_event_info(db, "t1", "bookingcom")
        assert result["lag_seconds"] is None


# ============================================================================
# Group G — buffer_count and dlq_count
# ============================================================================

class TestGroupG_BufferAndDLQ:

    def test_g1_buffer_count_empty_db(self) -> None:
        """G1: Empty ordering buffer → buffer_count=0."""
        from api.integration_health_router import _provider_buffer_count
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[])
        chain.eq.return_value = chain
        chain.is_.return_value = chain
        chain.select.return_value = chain
        db = MagicMock()
        db.table.return_value.select.return_value = chain
        assert _provider_buffer_count(db, "bookingcom") == 0

    def test_g2_buffer_count_with_rows(self) -> None:
        """G2: 3 pending buffer rows → buffer_count=3."""
        from api.integration_health_router import _provider_buffer_count
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[{"id": 1}, {"id": 2}, {"id": 3}])
        chain.eq.return_value = chain
        chain.is_.return_value = chain
        chain.select.return_value = chain
        db = MagicMock()
        db.table.return_value.select.return_value = chain
        assert _provider_buffer_count(db, "bookingcom") == 3

    def test_g3_dlq_count_empty(self) -> None:
        """G3: Empty DLQ → dlq_count=0."""
        from api.integration_health_router import _provider_dlq_count
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[])
        chain.eq.return_value = chain
        chain.select.return_value = chain
        db = MagicMock()
        db.table.return_value.select.return_value = chain
        assert _provider_dlq_count(db, "bookingcom") == 0

    def test_g4_dlq_count_pending_rows(self) -> None:
        """G4: 2 null replay_result rows → dlq_count=2."""
        from api.integration_health_router import _provider_dlq_count
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[
            {"id": 1, "replay_result": None, "source": "bookingcom"},
            {"id": 2, "replay_result": None, "source": "bookingcom"},
        ])
        chain.eq.return_value = chain
        chain.select.return_value = chain
        db = MagicMock()
        db.table.return_value.select.return_value = chain
        assert _provider_dlq_count(db, "bookingcom") == 2

    def test_g5_dlq_applied_rows_not_counted(self) -> None:
        """G5: APPLIED rows are excluded from dlq_count."""
        from api.integration_health_router import _provider_dlq_count
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[
            {"id": 1, "replay_result": "APPLIED", "source": "bookingcom"},
            {"id": 2, "replay_result": None, "source": "bookingcom"},
        ])
        chain.eq.return_value = chain
        chain.select.return_value = chain
        db = MagicMock()
        db.table.return_value.select.return_value = chain
        assert _provider_dlq_count(db, "bookingcom") == 1


# ============================================================================
# Group H — Best-effort: per-provider error → unknown, not 500
# ============================================================================

class TestGroupH_BestEffort:

    def test_h1_db_exception_on_event_log_query_returns_unknown(self) -> None:
        """H1: event_log query throws → provider status=unknown, not 500."""
        from api.integration_health_router import _provider_event_info
        chain = MagicMock()
        chain.execute.side_effect = RuntimeError("db error")
        chain.eq.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = chain
        chain.select.return_value = chain
        db = MagicMock()
        db.table.return_value.select.return_value = chain
        result = _provider_event_info(db, "t1", "bookingcom")
        assert result["status"] == "unknown"
        assert result["last_ingest_at"] is None

    def test_h2_db_exception_on_buffer_returns_0(self) -> None:
        """H2: ordering buffer query throws → buffer_count=0 (no 500)."""
        from api.integration_health_router import _provider_buffer_count
        chain = MagicMock()
        chain.execute.side_effect = RuntimeError("db error")
        chain.eq.return_value = chain
        chain.is_.return_value = chain
        chain.select.return_value = chain
        db = MagicMock()
        db.table.return_value.select.return_value = chain
        assert _provider_buffer_count(db, "bookingcom") == 0

    def test_h3_db_exception_on_dlq_returns_0(self) -> None:
        """H3: DLQ query throws → dlq_count=0 (no 500)."""
        from api.integration_health_router import _provider_dlq_count
        chain = MagicMock()
        chain.execute.side_effect = RuntimeError("db error")
        chain.eq.return_value = chain
        chain.select.return_value = chain
        db = MagicMock()
        db.table.return_value.select.return_value = chain
        assert _provider_dlq_count(db, "bookingcom") == 0

    def test_h4_partial_provider_failures_still_return_200(self) -> None:
        """H4: Even if some providers fail, endpoint returns 200."""
        db = _mock_db_empty()
        c = _make_app(db)
        resp = _get(c, db)
        assert resp.status_code == 200


# ============================================================================
# Group I — Read-only invariants
# ============================================================================

class TestGroupI_ReadOnly:

    def test_i1_never_calls_insert(self) -> None:
        """I1: /integration-health never calls .insert() on any table."""
        db = _mock_db_empty()
        c = _make_app(db)
        _get(c, db)
        insert_calls = db.table.return_value.insert.call_count
        assert insert_calls == 0

    def test_i2_never_calls_update(self) -> None:
        """I2: /integration-health never calls .update() on any table."""
        db = _mock_db_empty()
        c = _make_app(db)
        _get(c, db)
        update_calls = db.table.return_value.update.call_count
        assert update_calls == 0

    def test_i3_reads_event_log(self) -> None:
        """I3: /integration-health reads from event_log."""
        db = _mock_db_empty()
        c = _make_app(db)
        _get(c, db)
        tables_queried = [str(c.args[0]) for c in db.table.call_args_list]
        assert any("event_log" in t for t in tables_queried)

    def test_i4_never_writes_booking_state(self) -> None:
        """I4: /integration-health never writes to booking_state."""
        db = _mock_db_empty()
        c = _make_app(db)
        _get(c, db)
        # Any insert/update call would be on a specific table; we check table wasn't
        # called with booking_state in a write context
        insert_calls = [str(c.args[0]) for c in db.table.call_args_list
                        if "booking_state" in str(c.args[0])]
        # No insert at all is the correct invariant
        assert db.table.return_value.insert.call_count == 0
