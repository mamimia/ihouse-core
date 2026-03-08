# Phase 50 Spec — BOOKING_AMENDED DDL + apply_envelope Branch

## Objective

Implement the final 3 prerequisites for `BOOKING_AMENDED` at the SQL/stored-procedure layer,
and verify E2E on live Supabase before Phase 51 (Python pipeline integration).

## Prerequisites Completed By This Phase

| Prerequisite | Status After Phase 50 |
|-------------|----------------------|
| DLQ infrastructure | ✅ |
| booking_id stability | ✅ |
| MODIFY classification | ✅ |
| booking_state.status | ✅ |
| Ordering infrastructure | ✅ |
| Idempotency key format | ✅ |
| Normalized AmendmentPayload | ✅ |
| event_kind enum: BOOKING_AMENDED | ✅ (Step 1) |
| apply_envelope BOOKING_AMENDED branch | ✅ (Step 2) |
| ACTIVE-state lifecycle guard | ✅ (Step 2) |

## Step 1 — enum extension (deployed in prior chat)

```sql
ALTER TYPE public.event_kind ADD VALUE IF NOT EXISTS 'BOOKING_AMENDED';
```

## Step 2 — apply_envelope replacement

**Migration file:** `supabase/migrations/20260308210000_phase50_step2_apply_envelope_amended.sql`  
**Deployed via:** `supabase db push --linked`

### BOOKING_AMENDED branch logic:

1. Extract `booking_id` from `e->'payload'->>'booking_id'` → raises `BOOKING_ID_REQUIRED` if null
2. `SELECT bs.state_json, bs.status FROM booking_state WHERE booking_id = ... FOR UPDATE` → row-level lock
3. If not found → raises `BOOKING_NOT_FOUND`
4. **ACTIVE-state guard:** if `status = 'canceled'` → raises `AMENDMENT_ON_CANCELED_BOOKING`
5. Extract optional `new_check_in` / `new_check_out` from payload
6. Validate: if both provided, check_out > check_in
7. Build updated `state_json`, embed amendment payload
8. Append-only `INSERT INTO event_log` (kind = `STATE_UPSERT`)
9. `UPDATE booking_state SET check_in = COALESCE(new, existing), check_out = COALESCE(new, existing)` — status stays `'active'`

## Deliverables

- `artifacts/supabase/migrations/phase50_step2_apply_envelope_amended.sql` — canonical SQL
- `supabase/migrations/20260308210000_phase50_step2_apply_envelope_amended.sql` — deployed
- `tests/test_booking_amended_e2e.py` — 5 E2E tests on live Supabase

## E2E Tests (all passing)

| Scenario | Expected | Result |
|----------|----------|--------|
| BOOKING_CREATED | APPLIED | ✅ |
| BOOKING_AMENDED both dates | APPLIED, dates updated, status=active, version=2 | ✅ |
| BOOKING_AMENDED check_in only | APPLIED, check_out preserved via COALESCE | ✅ |
| BOOKING_AMENDED on CANCELED | AMENDMENT_ON_CANCELED_BOOKING | ✅ |
| BOOKING_AMENDED on non-existent | BOOKING_NOT_FOUND | ✅ |

## Canonical Invariants — Unchanged

- `apply_envelope` remains the single write authority
- `event_log` remains append-only
- `booking_state` remains projection-only
- No adapter reads booking_state
- No alternative write path introduced

## Outcome

158 tests pass (2 pre-existing SQLite failures unrelated).  
BOOKING_AMENDED prerequisites: **10/10 ✅**

## Next Phase

Phase 51 — Python Pipeline Integration (semantics.py + service.py BOOKING_AMENDED routing)
