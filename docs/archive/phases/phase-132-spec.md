# Phase 132 — Booking Audit Trail
**Spec version:** 1.0
**Status:** Closed ✅
**Date:** 2026-03-09

---

## Objective

Expose a read-only chronological audit trail for a single booking
from the `event_log` table — the canonical source of truth.

## Endpoint

```
GET /bookings/{booking_id}/history
```

**Auth:** Bearer JWT required (`sub` claim = `tenant_id`).
**Tenant isolation:** Enforced at DB level — only events for the authenticated tenant are returned.
**404 semantics:** 404 returned when no events exist for the `booking_id`/`tenant_id` pair. Cross-tenant reads return 404, not 403, to avoid leaking existence.

## Response Schema

```json
{
  "booking_id":   "bk-abc-001",
  "tenant_id":    "tenant-xyz",
  "event_count":  3,
  "events": [
    {
      "event_id":    "evt-1",
      "event_kind":  "BOOKING_CREATED",
      "version":     1,
      "envelope_id": "env-abc",
      "source":      "airbnb",
      "property_id": "prop-A",
      "check_in":    "2026-03-01",
      "check_out":   "2026-03-08",
      "recorded_at": "2026-01-10T10:00:00Z"
    }
  ]
}
```

**Ordering:** Oldest event first (`recorded_at ASC`).

## Source Table

`event_log` — the canonical event store.
**Not** `booking_state` (that is the projection).

## Event Kinds Returned

- `BOOKING_CREATED`
- `BOOKING_AMENDED`
- `BOOKING_CANCELED`
- Any buffered, replayed, or DLQ-sourced events

## Invariants

1. Read-only. Never writes to any table.
2. Reads `event_log` only — never `booking_state`.
3. JWT auth required.
4. `apply_envelope` remains the only write authority.
5. `recorded_at` falls back to `created_at` if null.

## Files Added / Modified

| File | Action |
|------|--------|
| `src/api/booking_history_router.py` | NEW |
| `tests/test_booking_history_contract.py` | NEW (32 tests) |
| `src/main.py` | MODIFIED (router registered, `history` tag added) |
| `docs/archive/phases/phase-132-spec.md` | NEW (this file) |

## Test Results

32/32 passing ✅
Full suite: 3349 passed, 2 failed (pre-existing SQLite guards), 3 skipped.
