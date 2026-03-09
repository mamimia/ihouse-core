# Phase 133 — OTA Ordering Buffer Inspector
**Spec version:** 1.0
**Status:** Closed ✅
**Date:** 2026-03-09

---

## Objective

Provide read-only operator visibility into the `ota_ordering_buffer` — the
table that holds events which arrived before their `BOOKING_CREATED` was
processed (out-of-order delivery). Operators can now see:

- Which events are stuck in `waiting` (blocked waiting for booking creation)
- How long each entry has been waiting (`age_seconds`)
- Which DLQ entry corresponds to the buffer entry (`dlq_row_id`)
- Event type, booking_id, and creation timestamp per entry

## Endpoints

```
GET /admin/buffer                  — list entries (filters: status, booking_id, limit)
GET /admin/buffer/{entry_id}       — single entry by integer ID
```

**Auth:** Bearer JWT required.  
**Source:** `ota_ordering_buffer` — global (not tenant-scoped).  
**Invariant:** Read-only. Never writes to any table.

## Query Parameters (list endpoint)

| Param | Values | Default |
|-------|--------|---------|
| `status` | `waiting` \| `replayed` \| `all` | `all` |
| `booking_id` | any string | (none) |
| `limit` | 1–100 | 50 |

## Response Schema (list)

```json
{
  "total":              2,
  "status_filter":      "waiting",
  "booking_id_filter":  null,
  "entries": [
    {
      "id":          1,
      "booking_id":  "bk-airbnb-X001",
      "event_type":  "BOOKING_CANCELED",
      "status":      "waiting",
      "dlq_row_id":  42,
      "created_at":  "2026-03-09T10:00:00Z",
      "age_seconds": 3722
    }
  ]
}
```

## `age_seconds` — Operational Value

`age_seconds` shows how long an entry has been in the buffer since `created_at`.
For stuck `waiting` entries, large values identify ordering bottlenecks.
`null` when `created_at` is missing.

## Files Added / Modified

| File | Action |
|------|--------|
| `src/api/buffer_router.py` | NEW |
| `tests/test_buffer_router_contract.py` | NEW (35 tests) |
| `src/main.py` | MODIFIED (router registered, `buffer` tag added) |
| `docs/archive/phases/phase-133-spec.md` | NEW (this file) |

## Test Results

35/35 passing ✅  
Full suite: 3384 passed, 2 failed (pre-existing SQLite guards), 3 skipped.
