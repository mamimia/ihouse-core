# Phase 138 — Outbound Executor
**Spec version:** 1.0
**Status:** Closed ✅
**Date:** 2026-03-10

---

## Objective

Phase 138 is the **dispatch layer** of the Outbound Sync system.

It receives the `sync_plan` produced by Phase 137 and dispatches each
non-skip action to the appropriate adapter. Phase 138 ships with
**stub (dry-run) adapters** — real OTA API calls come in Phase 139.

## New Files

| File | Role |
|------|------|
| `src/services/outbound_executor.py` | Execution service — fail-isolated dispatch, dry-run stubs |
| `src/api/outbound_executor_router.py` | HTTP router — combines plan (137) + execute (138) |

## Endpoint

```
POST /internal/sync/execute
Body: { "booking_id": "bk-airbnb-HZ001" }
Auth: JWT required

200 → execution_report
404 → booking not found
400 → booking_id missing/empty
403 → JWT missing
500 → DB error
```

## Adapter Stubs (Phase 138)

| Adapter | Strategy | Status returned |
|---------|----------|----------------|
| `ApiFirstAdapter.send()` | api_first | `dry_run` |
| `ICalAdapter.push()` | ical_fallback | `dry_run` |

Both stubs log the intent and return `dry_run`. Real calls in Phase 139.

## ExecutionReport Schema

```json
{
    "booking_id":    "bk-airbnb-HZ001",
    "property_id":   "prop-villa-alpha",
    "tenant_id":     "tenant-001",
    "total_actions": 3,
    "ok_count":      1,
    "failed_count":  0,
    "skip_count":    2,
    "dry_run":       true,
    "results": [
        {
            "provider":    "airbnb",
            "external_id": "HZ12345",
            "strategy":    "api_first",
            "status":      "dry_run",
            "http_status": null,
            "message":     "[Phase 138 stub] api_first dispatched..."
        }
    ]
}
```

## Invariants

- **Fail-isolated:** one adapter failure does not prevent other actions from running.
- **Read-only on booking tables:** never writes to booking_state or event_log.
- **apply_envelope untouched:** outbound config only.
- **dry_run=True** when all non-skip results are dry_run status.

## Test Results

30/30 contract tests passing ✅  
Full suite: 3533 passed, 2 failed (pre-existing SQLite guards), 3 skipped.
