# Phase 43 — booking_state Status Verification

## Status

Active

## Key Finding From Phase 42

Phase 42 claimed: "booking_state has no explicit status column."

Upon reading the actual schema SQL (`artifacts/supabase/schema.sql`):

```sql
CREATE TABLE IF NOT EXISTS "public"."booking_state" (
    "booking_id" "text" NOT NULL,
    ...
    "status" "text"       ← ALREADY EXISTS
);
```

And in `apply_envelope`:
- `BOOKING_CREATED` → `INSERT ... status = 'active'`
- `BOOKING_CANCELED` → `UPDATE ... SET status = 'canceled'`

**The status column exists and is populated correctly.** The Phase 42 finding was based on reading code descriptions rather than the actual schema SQL — now corrected.

## What Actually Needs Doing

1. E2E verify both transitions on live Supabase
2. Add `get_booking_status(booking_id, client=None)` — thin read-only utility for future amendment guard
3. Contract tests
4. Update amendment prerequisites table accordingly

## Scope

### `src/adapters/ota/booking_status.py`

```python
def get_booking_status(booking_id: str, client=None) -> str | None
```

- reads `booking_state.status` by `booking_id`
- returns `'active'` / `'canceled'` / `None` (unknown booking)
- read-only — never writes

**Critical constraint:** This function must ONLY be used in amendment pre-validation or operator tooling. It must NEVER be called inside the OTA ingestion path (`process_ota_event`, skills, adapters). Adapters must not read state.

### Contract Tests

- unknown booking → None
- active booking → 'active'
- canceled booking → 'canceled'
- client injection works (no live Supabase needed)

## Completion Conditions

Phase 43 is complete when:
- E2E confirms status transitions
- `booking_status.py` implements `get_booking_status`
- contract tests pass
- amendment prerequisite table updated (status column: ✅)
- all existing tests pass
