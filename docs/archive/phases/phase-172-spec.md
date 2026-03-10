# Phase 172 — Health Check Enrichment

**Date closed:** 2026-03-10  
**Status:** ✅ Closed  
**Tests added:** 20 contract tests  
**Total after phase:** 4468 passing

## Goal

Extend `GET /health` to include outbound sync probe results per provider: last sync timestamp, 7-day failure rate, log lag, and a derived status (ok / degraded / idle / error).

## Deliverables

### Modified Files
- `src/api/health.py`:
  - `OutboundSyncProbeResult` dataclass: provider, last_sync_at (ISO string or None), failure_rate_7d (float 0.0–1.0 or None), log_lag_seconds (int or None), status ('ok'|'degraded'|'idle'|'error')
  - `probe_outbound_sync(client, providers, now)` — reads `outbound_sync_log` per provider; derives status: idle (no entries) / ok / degraded (>20% failure rate OR >3600s lag) / error (DB query failure). Best-effort, never raises. Injectable `now` for testing.
  - `run_health_checks_enriched(version, env, outbound_client, outbound_providers, now)` — wraps existing `run_health_checks()` + adds `checks['outbound']` with providers list. Propagates `degraded` to overall result status.
  - `_DEFAULT_PROVIDERS = ['airbnb', 'bookingcom', 'expedia', 'agoda', 'tripcom']`

### New Test Files
- `tests/test_health_enriched_contract.py` — 20 contract tests

## Key Design Decisions
- Degraded threshold: >20% failure rate OR >3600s lag since last sync
- `idle` status (no log entries) is information, not alert — new providers without activity show idle
- Entire probe is best-effort: if `outbound_sync_log` query fails, status='error' per provider, overall health unaffected (does not flip to unhealthy)
- Injectable `now` allows deterministic testing of 7-day window calculations

## Architecture Invariants Preserved
- `apply_envelope` is the only write authority to `booking_state` ✅
- Health probe is read-only — zero writes to any table ✅
