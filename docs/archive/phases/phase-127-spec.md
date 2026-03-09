# Phase 127 — Integration Health Dashboard

**Status:** Closed
**Prerequisite:** Phase 126 (Availability Projection)
**Date Closed:** 2026-03-09

## Goal

Comprehensive per-provider integration health view for **all 13 OTA providers**.
Enhancement over Phase 82's `/admin/health/providers` (was: 5 providers, last_ingest only).

Sourced from `future-improvements.md`:
> Integration Health Dashboard (priority: high)
> Per-provider: last successful ingest, occurred_at vs recorded_at lag,
> buffer counts, DLQ counts, reject counts, stale provider alerts.

## Endpoint

```
GET /integration-health
```

JWT Bearer required.

### Response Shape
```json
{
  "tenant_id": "...",
  "checked_at": "2026-03-09T...",
  "providers": [
    {
      "provider": "bookingcom",
      "last_ingest_at": "2026-04-01T10:00:00+00:00",
      "lag_seconds": 10.0,
      "buffer_count": 0,
      "dlq_count": 0,
      "stale_alert": false,
      "status": "ok"
    },
    ...
  ],
  "summary": {
    "total_providers": 13,
    "ok": 11,
    "stale": 2,
    "unknown": 0,
    "total_dlq_pending": 0,
    "total_buffer_pending": 0,
    "has_alerts": true
  }
}
```

## Design Decisions

- **All 13 providers** (Phase 82 had only 5 hardcoded).
- **lag_seconds:** `recorded_at - occurred_at` — detects delayed processing.
- **stale_alert:** True when no events in last **24h** or no events at all.
- **Best-effort per provider:** query error → `status=unknown`, not 500.
- Reads: `event_log` (tenant-scoped), `ota_ordering_buffer` (global), `ota_dead_letter` (global).
- Zero write-path changes. JWT auth required.

## Files Changed

| File | Change |
|------|--------|
| `src/api/integration_health_router.py` | NEW — GET /integration-health |
| `src/main.py` | MODIFIED — register router + OpenAPI tag |
| `tests/test_integration_health_router_contract.py` | NEW — 37 tests |

## Result

**3166 tests pass** (2 pre-existing SQLite skips).
No DB schema changes. Zero write-path changes.
