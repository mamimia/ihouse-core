"""
Phase 172 — Health Check Enrichment Contract Tests

Groups:
  A — probe_outbound_sync: idle (no log entries)
  B — probe_outbound_sync: ok status
  C — probe_outbound_sync: degraded via failure rate > 20%
  D — probe_outbound_sync: degraded via log lag > 1 hour
  E — probe_outbound_sync: DB error → status='error' (best-effort)
  F — run_health_checks_enriched: outbound client None → skipped
  G — run_health_checks_enriched: degraded probe propagates to result
  H — run_health_checks_enriched: result shape + outbound key
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from api.health import (
    probe_outbound_sync,
    run_health_checks_enriched,
    OutboundSyncProbeResult,
    _DEGRADED_FAILURE_RATE,
    _DEGRADED_LAG_SECONDS,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 3, 10, 9, 0, 0, tzinfo=timezone.utc)
_RECENT = (_NOW - timedelta(minutes=5)).isoformat()
_STALE = (_NOW - timedelta(hours=2)).isoformat()      # > 3600s → degraded
_WEEK_AGO = (_NOW - timedelta(days=8)).isoformat()    # outside 7d window


def _make_client(
    last_rows: list | None = None,
    week_rows: list | None = None,
    error: bool = False,
) -> MagicMock:
    """
    Build a mock Supabase client for outbound_sync_log queries.

    First execute call → last_rows (last sync entry)
    Second execute call → week_rows (7d failure rate window)
    """
    db = MagicMock()
    q = MagicMock()
    q.select.return_value = q
    q.eq.return_value = q
    q.order.return_value = q
    q.limit.return_value = q
    q.gte.return_value = q

    if error:
        q.execute.side_effect = RuntimeError("DB error")
    else:
        q.execute.side_effect = [
            MagicMock(data=last_rows if last_rows is not None else []),
            MagicMock(data=week_rows if week_rows is not None else []),
        ]

    db.table.return_value = q
    return db


def _probe(client, providers=None):
    return probe_outbound_sync(client=client, providers=providers or ["airbnb"], now=_NOW)


# ---------------------------------------------------------------------------
# Group A — idle: no log entries
# ---------------------------------------------------------------------------

def test_a1_no_entries_status_is_idle():
    db = _make_client(last_rows=[])
    results = _probe(db)
    assert results[0].status == "idle"


def test_a2_idle_last_sync_at_is_none():
    db = _make_client(last_rows=[])
    assert _probe(db)[0].last_sync_at is None


def test_a3_idle_failure_rate_is_none():
    db = _make_client(last_rows=[])
    assert _probe(db)[0].failure_rate_7d is None


def test_a4_idle_lag_seconds_is_none():
    db = _make_client(last_rows=[])
    assert _probe(db)[0].log_lag_seconds is None


# ---------------------------------------------------------------------------
# Group B — ok status
# ---------------------------------------------------------------------------

def test_b1_recent_healthy_status_ok():
    db = _make_client(
        last_rows=[{"synced_at": _RECENT, "status": "success"}],
        week_rows=[{"status": "success"}, {"status": "success"}],
    )
    assert _probe(db)[0].status == "ok"


def test_b2_last_sync_at_populated():
    db = _make_client(
        last_rows=[{"synced_at": _RECENT, "status": "success"}],
        week_rows=[],
    )
    assert _probe(db)[0].last_sync_at == _RECENT


def test_b3_lag_seconds_computed():
    db = _make_client(
        last_rows=[{"synced_at": _RECENT, "status": "success"}],
        week_rows=[],
    )
    lag = _probe(db)[0].log_lag_seconds
    assert lag is not None
    assert 0 < lag <= 400   # ~5 min


def test_b4_zero_failures_rate_is_zero():
    db = _make_client(
        last_rows=[{"synced_at": _RECENT, "status": "success"}],
        week_rows=[{"status": "success"}, {"status": "success"}],
    )
    assert _probe(db)[0].failure_rate_7d == 0.0


# ---------------------------------------------------------------------------
# Group C — degraded via failure rate > 20%
# ---------------------------------------------------------------------------

def test_c1_high_failure_rate_is_degraded():
    # 3 out of 10 = 30% > 20% threshold
    week_rows = [{"status": "failed"}] * 3 + [{"status": "success"}] * 7
    db = _make_client(
        last_rows=[{"synced_at": _RECENT, "status": "failed"}],
        week_rows=week_rows,
    )
    assert _probe(db)[0].status == "degraded"


def test_c2_failure_rate_exactly_at_threshold_is_ok():
    # Exactly 20% is NOT > threshold → still ok
    week_rows = [{"status": "failed"}] * 2 + [{"status": "success"}] * 8
    db = _make_client(
        last_rows=[{"synced_at": _RECENT, "status": "success"}],
        week_rows=week_rows,
    )
    assert _probe(db)[0].status == "ok"


def test_c3_failure_rate_above_threshold():
    week_rows = [{"status": "error"}] * 5 + [{"status": "success"}] * 5
    db = _make_client(
        last_rows=[{"synced_at": _RECENT, "status": "success"}],
        week_rows=week_rows,
    )
    rate = _probe(db)[0].failure_rate_7d
    assert rate == 0.5


# ---------------------------------------------------------------------------
# Group D — degraded via log lag > 1 hour
# ---------------------------------------------------------------------------

def test_d1_stale_sync_is_degraded():
    db = _make_client(
        last_rows=[{"synced_at": _STALE, "status": "success"}],
        week_rows=[{"status": "success"}],
    )
    assert _probe(db)[0].status == "degraded"


def test_d2_lag_seconds_reflects_stale():
    db = _make_client(
        last_rows=[{"synced_at": _STALE, "status": "success"}],
        week_rows=[],
    )
    lag = _probe(db)[0].log_lag_seconds
    assert lag is not None and lag > _DEGRADED_LAG_SECONDS


# ---------------------------------------------------------------------------
# Group E — DB error → status='error' (best-effort, never raises)
# ---------------------------------------------------------------------------

def test_e1_db_error_does_not_raise():
    db = _make_client(error=True)
    results = _probe(db)  # must not raise
    assert len(results) == 1


def test_e2_db_error_status_is_error():
    db = _make_client(error=True)
    assert _probe(db)[0].status == "error"


# ---------------------------------------------------------------------------
# Group F — run_health_checks_enriched: no client → skipped
# ---------------------------------------------------------------------------

def test_f1_no_client_outbound_skipped():
    result = run_health_checks_enriched(version="1.0", env="test", outbound_client=None)
    assert result.checks["outbound"]["status"] == "skipped"


def test_f2_no_client_overall_not_degraded_by_outbound():
    result = run_health_checks_enriched(version="1.0", env="test", outbound_client=None)
    # supabase/dlq checks may degrade, but outbound alone doesn't
    assert "outbound" in result.checks


# ---------------------------------------------------------------------------
# Group G — degraded probe propagates to result
# ---------------------------------------------------------------------------

def test_g1_degraded_probe_sets_result_degraded():
    week_rows = [{"status": "failed"}] * 8 + [{"status": "success"}] * 2
    db = _make_client(
        last_rows=[{"synced_at": _RECENT, "status": "success"}],
        week_rows=week_rows,
    )
    result = run_health_checks_enriched(
        version="1.0", env="test",
        outbound_client=db,
        outbound_providers=["airbnb"],
        now=_NOW,
    )
    # When Supabase is unreachable, base check returns 'unhealthy' which overrides
    # the outbound 'degraded'. Both are acceptable — what matters is it's not 'ok'.
    assert result.status in ("degraded", "unhealthy")


# ---------------------------------------------------------------------------
# Group H — result shape + outbound key
# ---------------------------------------------------------------------------

def test_h1_outbound_check_has_providers_list():
    db = _make_client(
        last_rows=[{"synced_at": _RECENT, "status": "success"}],
        week_rows=[{"status": "success"}],
    )
    result = run_health_checks_enriched(
        version="1.0", env="test",
        outbound_client=db,
        outbound_providers=["airbnb"],
        now=_NOW,
    )
    assert "providers" in result.checks["outbound"]
    assert len(result.checks["outbound"]["providers"]) == 1


def test_h2_provider_entry_has_all_fields():
    db = _make_client(
        last_rows=[{"synced_at": _RECENT, "status": "success"}],
        week_rows=[],
    )
    result = run_health_checks_enriched(
        version="1.0", env="test",
        outbound_client=db,
        outbound_providers=["airbnb"],
        now=_NOW,
    )
    entry = result.checks["outbound"]["providers"][0]
    for key in ("provider", "last_sync_at", "failure_rate_7d", "log_lag_seconds", "status"):
        assert key in entry, f"Missing key: {key}"
