# Phase 142 — Retry + Exponential Backoff

**Status:** Closed  
**Closed:** 2026-03-10  
**Tests added:** 28  
**Total tests after:** 3637 passing (2 pre-existing SQLite guard failures, unrelated, unchanged)

## Goal

On 5xx or network error, each outbound adapter retries the HTTP call up to
3 times with exponential backoff before returning `status=failed`.

Before Phase 142, any transient 5xx or flaky connection immediately returned
`failed` — causing unnecessary sync failures that require manual replay.

## Changes

| File | Change |
|------|--------|
| `src/adapters/outbound/__init__.py` | MODIFIED — added `_retry_with_backoff(fn, max_retries=3)` helper |
| `src/adapters/outbound/airbnb_adapter.py` | MODIFIED — `_do_req()` closure wrapped by `_retry_with_backoff` |
| `src/adapters/outbound/bookingcom_adapter.py` | MODIFIED — same pattern |
| `src/adapters/outbound/expedia_vrbo_adapter.py` | MODIFIED — same pattern |
| `src/adapters/outbound/ical_push_adapter.py` | MODIFIED — same pattern (httpx.put path) |
| `tests/test_adapter_retry_contract.py` | NEW — 28 contract tests |

## `_retry_with_backoff()` Design

```python
def _retry_with_backoff(fn: Callable[[], T], max_retries: int = 3) -> T:
    if os.environ.get("IHOUSE_RETRY_DISABLED", "false").lower() == "true":
        return fn()
    for attempt in range(max_retries + 1):
        if attempt > 0:
            delay = min(4.0 ** (attempt - 1), 30.0)
            time.sleep(delay)        # 1s → 4s → 16s (capped 30s)
        try:
            result = fn()
            if result.http_status is not None and result.http_status >= 500:
                if attempt < max_retries:
                    continue         # retry 5xx
            return result            # 2xx / 4xx / None → return immediately
        except Exception as exc:
            if attempt < max_retries:
                continue             # retry transient exceptions
            raise
    return result  # 5xx exhausted
```

- **Single implementation** in `__init__.py` — new adapters cannot miss it.
- **`IHOUSE_RETRY_DISABLED=true`** — test opt-out; no real retries/sleeps in tests.
- **4xx not retried** — client errors (bad key, wrong URL) are terminal.
- **None http_status not retried** — dry-run code path, nothing to retry.
- **`_throttle()` called once before retry loop** — rate-limit pacing per `send()` call.
- **Max delay 30s** — prevents extreme waits if max_retries ever increases.
- **4-item mock needed** for max_retries=3 tests (4 total attempts: 0,1,2,3).

## Adapter Wiring Pattern

```python
_throttle(rate_limit)

def _do_req() -> AdapterResult:
    resp = httpx.post(url, json=payload, headers=headers, timeout=10)
    if resp.status_code in (200, 201, 204):
        return AdapterResult(..., status="ok", ...)
    return AdapterResult(..., status="failed", http_status=resp.status_code, ...)

return _retry_with_backoff(_do_req)
```

The outer `except Exception` block (already present) catches the re-raise
from `_retry_with_backoff` when all retries are exhausted via exception path.

## Test Summary

| Group | Tests | What |
|-------|-------|------|
| A — `_retry_with_backoff()` unit | 10 | Immediate OK; 1x5xx→retry; 2x5xx→retry; 4x5xx exhausted; exc then OK; 3x exc raises; 4xx not retried; IHOUSE_RETRY_DISABLED; cap at 30s; None not retried |
| B — Airbnb | 6 | 2x5xx→ok (sleeps [1,4]); 4x5xx→failed; 4xx no retry; 200 no retry; exc→retry; dry-run no retry |
| C — BookingCom | 3 | 1x5xx→ok; 4x5xx→failed; dry-run |
| D — Expedia/VRBO | 4 | Expedia 1x5xx→ok; VRBO 1x5xx→ok; 4x5xx→failed; dry-run |
| E — iCal | 5 | Hotelbeds 1x5xx→ok; TripAdvisor 1x5xx→ok; 4x5xx→failed; dry-run; exc→retry |

## Invariants Preserved

- `apply_envelope` is the only canonical write authority — unchanged.
- Dry-run gate checked first in every adapter — retry never reached in dry-run.
- Throttle is called once per `send()`/`push()` call, not per retry attempt.
- No DB schema changes. No migrations. No router changes.

## Next Phase

Phase 143 — Idempotency Key on Outbound Requests
