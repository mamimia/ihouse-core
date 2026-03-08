# Phase 62 — Per-Tenant Rate Limiting

**Status:** Closed  
**Date:** 2026-03-08  
**Tests:** 313 passed, 2 skipped  

## Objective

Add the final defensive layer: per-tenant rate limiting keyed by verified JWT tenant_id.

## Files Changed

| File | Change |
|------|--------|
| `src/api/rate_limiter.py` | **NEW** — `InMemoryRateLimiter`, `rate_limit` Depends |
| `src/api/webhooks.py` | Added `_: None = Depends(rate_limit)` |
| `tests/test_rate_limiter.py` | **NEW** — 6 contract tests |

## Key Decisions

- Sliding window (deque + monotonic timestamps), per-tenant threading.Lock
- `IHOUSE_RATE_LIMIT_RPM=0` → dev bypass (same pattern as JWT/signature dev-modes)
- Module-level singleton (shared across requests in same process)
- Interface abstracted — Redis swap requires only changing the backend class
- `Retry-After` response header set on all 429s

## HTTP API Layer Summary (Phases 58–62)

| Phase | Feature |
|-------|---------|
| 58 | `POST /webhooks/{provider}` — signature verify + validate + ingest |
| 59 | `src/main.py` — FastAPI entrypoint, `GET /health` |
| 60 | Request logging middleware (X-Request-ID, duration, status) |
| 61 | JWT auth — tenant_id from verified sub claim |
| 62 | Per-tenant rate limiting (sliding window, 429 + Retry-After) |
