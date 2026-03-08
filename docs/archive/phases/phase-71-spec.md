# Phase 71 — Booking State Query API

**Status:** Closed
**Prerequisite:** Phase 69 (BOOKING_AMENDED Pipeline)
**Date Closed:** 2026-03-09

## Goal

Expose `booking_state` as a read-only query API. Before this phase, the only data endpoint was `GET /financial/{booking_id}`. There was no way for an external client to query booking status, dates, or source without going directly to Supabase.

## Files

| File | Change |
|------|--------|
| `src/api/bookings_router.py` | NEW — `GET /bookings/{booking_id}`, JWT auth + tenant isolation, reads `booking_state` only |
| `src/main.py` | MODIFIED — bookings tag added to `_TAGS`, `bookings_router` registered |
| `tests/test_bookings_router_contract.py` | NEW — 16 contract tests |

## API Contract

```
GET /bookings/{booking_id}
Authorization: Bearer <JWT>

200 → { booking_id, tenant_id, source, reservation_ref, property_id,
         status, check_in, check_out, version, created_at, updated_at }
404 → { error: "BOOKING_NOT_FOUND", booking_id }
403 → AUTH_FAILED (from jwt_auth dependency)
500 → { error: "INTERNAL_ERROR" }
```

## Invariants

- Reads `booking_state` projection only — never `event_log`
- Tenant isolation: `.eq("tenant_id", tenant_id)` enforced at DB query level
- Cross-tenant reads return 404, not 403 (avoids leaking booking existence)
- No write path introduced

## Result

**467 tests pass, 2 skipped.**
No Supabase schema changes. No new migrations.
