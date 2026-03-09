# Phase 106 — Booking List Query API

**Status:** Closed
**Date Closed:** 2026-03-09

## Goal

Extend `bookings_router.py` with the `GET /bookings` list endpoint. Previously only `GET /bookings/{booking_id}` (single lookup) existed. This gives callers a way to query all bookings for their tenant, with optional filtering.

## Invariant

- Reads `booking_state` only. Never reads `event_log`. Never writes.
- Tenant isolation via `.eq("tenant_id", tenant_id)` at DB level.
- `status` validation happens **before** any DB call — invalid status never hits the DB.

## Design / Files

| File | Change |
|------|--------|
| `src/api/bookings_router.py` | MODIFIED — `GET /bookings` list endpoint added |
| `tests/test_booking_list_router_contract.py` | NEW — 28 tests, Groups A–G |

## Endpoint spec

```
GET /bookings
  ?property_id=<str>          optional, filter by property
  ?status=active|canceled     optional, 400 VALIDATION_ERROR on invalid value
  ?limit=<int>                optional, default 50, clamped to 1–100
```

**Response:**
```json
{
  "tenant_id": "...",
  "count": 3,
  "limit": 50,
  "bookings": [{ ... }, ...]
}
```

**Ordered by** `updated_at DESC` (most recently modified first).

## Notes

- `status` validation fires before `_get_supabase_client()` — no unnecessary DB calls.
- `limit` is clamped server-side: `max(1, min(limit, 100))`.

## Result

**2374 tests pass, 2 skipped.**
No Supabase schema changes. No migrations. `booking_state` read-only.
