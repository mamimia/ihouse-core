# Phase 141 — Rate-Limit Enforcement

**Status:** Closed  
**Closed:** 2026-03-10  
**Tests added:** 22  
**Total tests after:** 3609 passing (2 pre-existing SQLite guard failures, unrelated, unchanged)

## Goal

Honour `rate_limit` (calls/minute) from `SyncAction` in all 4 outbound adapters.
The `rate_limit` parameter was already present on every `send()`/`push()` signature
but was silently ignored. Phase 141 enforces it via a shared throttle helper.

## Changes

| File | Change |
|------|--------|
| `src/adapters/outbound/__init__.py` | MODIFIED — added `_throttle(rate_limit)` helper |
| `src/adapters/outbound/airbnb_adapter.py` | MODIFIED — imports `_throttle`, called before `httpx.post()` |
| `src/adapters/outbound/bookingcom_adapter.py` | MODIFIED — same pattern |
| `src/adapters/outbound/expedia_vrbo_adapter.py` | MODIFIED — same pattern |
| `src/adapters/outbound/ical_push_adapter.py` | MODIFIED — `_throttle` before `httpx.put()` |
| `tests/test_rate_limit_enforcement_contract.py` | NEW — 22 contract tests |

## `_throttle()` Design

```python
def _throttle(rate_limit: int) -> None:
    if os.environ.get("IHOUSE_THROTTLE_DISABLED", "false").lower() == "true":
        return   # test opt-out
    if rate_limit <= 0:
        _throttle_logger.warning("rate_limit=%d is non-positive — throttle skipped", rate_limit)
        return   # best-effort: never block forever on misconfiguration
    time.sleep(60.0 / rate_limit)
```

- **Single implementation** in `__init__.py` — new adapters cannot miss it.
- **`IHOUSE_THROTTLE_DISABLED=true`** — test opt-out; no real sleeps in tests.
- **`rate_limit <= 0`** — warning + best-effort continue instead of blocking forever.
- **Dry-run gate is checked first** in every adapter — throttle is never reached in dry-run mode.

## Test Summary

| Group | Tests | What |
|-------|-------|------|
| A — `_throttle()` unit | 8 | Arithmetic (60→1.0s, 120→0.5s, 30→2.0s), zero/negative, disabled flag |
| B — Airbnb | 5 | Throttle called + duration correct; dry-run bypass (3 variants) |
| C — BookingCom | 2 | Throttle called; dry-run bypass |
| D — Expedia/VRBO | 3 | Throttle for expedia + vrbo separately; dry-run bypass |
| E — iCal | 4 | Throttle for hotelbeds (10rpm=6s) + tripadvisor (20rpm=3s); dry-run bypass |

## Invariants Preserved

- `apply_envelope` is the only canonical write authority — unchanged.
- `rate_limit` enforced on **outbound** path only; inbound pipeline unaffected.
- Dry-run mode (missing credentials / `IHOUSE_DRY_RUN=true` / `dry_run=True`) never throttles.
- No DB schema changes. No migrations. No router changes.

## Next Phase

Phase 142 — Retry + Exponential Backoff in Adapters
