# Phase 73 — BOOKING_NOT_FOUND → Ordering Buffer Auto-Route

**Status:** Closed
**Prerequisite:** Phase 72 (Tenant Dashboard)
**Date Closed:** 2026-03-09

## Problem Solved

Before this phase, when `BOOKING_CANCELED` or `BOOKING_AMENDED` arrived before `BOOKING_CREATED`, `apply_envelope` returned `BOOKING_NOT_FOUND`. The event was written to the DLQ and **stayed there permanently** — it was never automatically replayed even after `BOOKING_CREATED` was processed.

The ordering buffer (Phases 44-45) existed but was never automatically populated in this path.

## Solution

When `status == "BOOKING_NOT_FOUND"` AND `envelope.type in {"BOOKING_CANCELED", "BOOKING_AMENDED"}`:

1. **Write to DLQ** via `write_to_dlq_returning_id` (new helper) — preserves event for audit, returns `dlq_row_id`
2. **Buffer in `ota_ordering_buffer`** via `buffer_event(dlq_row_id, booking_id, event_type)` — event marked `status=waiting`
3. **Return `BUFFERED`** status — event is NOT dead, it will be auto-replayed
4. When `BOOKING_CREATED` fires and is `APPLIED` → `ordering_trigger.trigger_ordered_replay(booking_id)` replays all `waiting` buffer rows

## Files

| File | Change |
|------|--------|
| `src/adapters/ota/service.py` | MODIFIED — BOOKING_NOT_FOUND → buffer auto-route |
| `src/adapters/ota/dead_letter.py` | MODIFIED — added `write_to_dlq_returning_id()` (returns `Optional[int]`) |
| `src/adapters/ota/ordering_buffer.py` | MODIFIED — `dlq_row_id` now `Optional[int]` |
| `tests/test_ordering_buffer_autoroute_contract.py` | NEW — 11 contract tests |

## Result

**492 tests pass, 2 skipped.**
No Supabase schema changes. No new migrations.

## End-to-End Flow (Now Live)

```
BOOKING_CANCELED arrives before BOOKING_CREATED:
  → apply_envelope → BOOKING_NOT_FOUND
  → write_to_dlq_returning_id() → dlq_row_id=42
  → buffer_event(dlq_row_id=42, booking_id="bcom_res1", "BOOKING_CANCELED")
  → return {"status": "BUFFERED", "reason": "AWAITING_BOOKING_CREATED"}

BOOKING_CREATED arrives later:
  → apply_envelope → APPLIED
  → trigger_ordered_replay("bcom_res1")
  → ota_ordering_buffer WHERE booking_id="bcom_res1" AND status="waiting"
  → replay_dlq_row(dlq_row=42) → APPLIED
  → mark_replayed(buffer_row_id)
```
