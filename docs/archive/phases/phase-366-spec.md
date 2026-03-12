# Phase 366 — Rate Limiter Hardening & Per-Endpoint Control

**Status:** Closed  
**Date Closed:** 2026-03-12

## Goal

Add tiered rate-limiting for sensitive endpoints and monitoring stats.

## Files Modified

| File | Change |
|------|--------|
| `src/api/rate_limiter.py` | MODIFIED — Added strict tier (20 RPM), `stats()` method, `rate_limit_strict` dependency |

## Features

1. **Strict Tier** — Separate InMemoryRateLimiter at 20 RPM for brute-force-sensitive endpoints
2. **Stats Method** — `stats()` returns per-tenant active request counts for monitoring
3. **Dual Dependency** — `rate_limit` (60 RPM default) + `rate_limit_strict` (20 RPM)

## Result

Tests: **38 rate limiter tests passed**. No regressions.
