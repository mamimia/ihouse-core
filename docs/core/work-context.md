# iHouse Core — Work Context

## Current Active Phase

Phase 44 — OTA Ordering Buffer

## Last Closed Phase

Phase 43 — booking_state Status Verification

## Current Objective

Introduce a minimal ordering buffer layer for OTA events that are rejected with `BOOKING_NOT_FOUND` because they arrived before the corresponding `BOOKING_CREATED`.

Currently those events go to `ota_dead_letter` (DLQ, Phase 38) where they sit passively. Phase 44 adds a structured buffer table that tags BOOKING_NOT_FOUND rejections as ordering-blocked and makes them queryable by booking_id — so that when BOOKING_CREATED eventually arrives, the system can find and replay them.

This phase covers: buffer table + write + read. Auto-trigger on CREATED is Phase 45.

## Locked Architectural Reality

The system remains a deterministic domain event execution kernel.

System truth is derived from canonical events.

booking_state is projection-only.

apply_envelope is the only authority allowed to mutate state.

Supabase is canonical.

External systems must never bypass the canonical apply gate.

## Phase 44 Scope

1. Supabase table `ota_ordering_buffer`:
   - References `ota_dead_letter.id`
   - `booking_id` — the booking that needs to exist first
   - `event_type` — the buffered event type
   - `buffered_at` — when buffered
   - `status`: `waiting` | `replayed` | `expired`

2. `src/adapters/ota/ordering_buffer.py`:
   - `buffer_event(dlq_row_id, booking_id, event_type, client=None)` — write buffer row
   - `get_buffered_events(booking_id, client=None) → list[dict]` — read waiting rows for booking_id
   - `mark_replayed(buffer_id, client=None)` — update status after replay

3. Contract tests:
   - buffer_event writes correct row
   - get_buffered_events returns only 'waiting' rows for a booking_id
   - mark_replayed updates status
   - empty result for unknown booking_id

Out of scope:
- auto-trigger on BOOKING_CREATED (Phase 45)
- actual replay calls from within ordering buffer (replay is dlq_replay.py)
- TTL/expiry logic (future)
