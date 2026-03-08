# Phase 40 — DLQ Observability

## Status

Active

## Depends On

Phase 39 — DLQ Controlled Replay

## Objective

Introduce a read-only inspection layer for `ota_dead_letter` so operators can understand pending rejections, replay history, and rejection breakdown — without any new write paths.

## Scope

### 1. Supabase SQL view: `ota_dlq_summary`

Groups rejection counts by `event_type` and `rejection_code`.

```sql
CREATE OR REPLACE VIEW public.ota_dlq_summary AS
SELECT
  event_type,
  rejection_code,
  COUNT(*)                                               AS total,
  COUNT(*) FILTER (WHERE replayed_at IS NULL)            AS pending,
  COUNT(*) FILTER (WHERE replayed_at IS NOT NULL)        AS replayed
FROM public.ota_dead_letter
GROUP BY event_type, rejection_code
ORDER BY pending DESC, total DESC;
```

### 2. Python utility: `src/adapters/ota/dlq_inspector.py`

```
get_pending_count()        → int
get_replayed_count()       → int
get_rejection_breakdown()  → list[dict]  (event_type, rejection_code, total, pending, replayed)
```

All functions are read-only. No writes.

### 3. Contract tests

- `get_pending_count` returns correct count given mocked rows
- `get_replayed_count` returns correct count given mocked rows
- `get_rejection_breakdown` groups correctly and sorts by pending desc
- all functions handle empty DLQ gracefully (return 0 or [])

## Constraints

- No new write paths
- No booking_state reads
- No alerting infrastructure (Phase 41)
- Functions must be independently testable without live Supabase

## Completion Conditions

Phase 40 is complete when:
- `ota_dlq_summary` view exists in Supabase
- `dlq_inspector.py` implements all three functions
- contract tests pass
- all existing tests still pass
