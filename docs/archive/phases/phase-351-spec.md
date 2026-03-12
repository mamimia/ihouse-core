# Phase 351 — Performance Baseline + Rate Limiting Validation

**Closed:** 2026-03-12
**Category:** ⚡ Performance / Testing
**Test file:** `tests/test_performance_baseline_p351.py`

## Summary

Concurrency, thread-safety, and performance baseline tests for the
per-tenant sliding-window rate limiter, health check engine, and
outbound sync health probes. Exercises behaviors not covered by
existing contract tests (thread isolation, window expiry timing,
throughput under 1000 req/s).

## Tests Added: 23

### Group A — Concurrent Rate Limiting (6 tests)
- 10 threads → exactly 5 pass (5 × 429), multi-tenant isolation under load,
  no cross-contamination, burst throughput (<500ms for 100 reqs), dev bypass
  under 50 concurrent threads, fresh bucket for new tenants

### Group B — Rate Limiter Edge Cases (5 tests)
- retry_after_seconds ≥ 1, error code RATE_LIMIT_EXCEEDED, window expiry,
  rpm=1 sentinel, bucket eviction on check

### Group C — Health Check Timing Baseline (4 tests)
- run_health_checks completes <1s without SUPABASE_URL, version/env fields,
  checks dict, valid status string

### Group D — Outbound Sync Probe Baselines (4 tests)
- idle → idle, healthy → ok/0.0 failure rate, >20% failures → degraded, DB error → error

### Group E — Throttle + Retry Fast-Path (4 tests)
- THROTTLE_DISABLED instant (<0.1s), RETRY_DISABLED calls fn once,
  retry returns fn result, 1000-req benchmark (<1s)

## System Numbers

| Metric | Before | After |
|--------|--------|-------|
| Tests collected | 7,000 | 7,023 |
| Test files | 234 | 235 |
| New tests | — | 23 |
