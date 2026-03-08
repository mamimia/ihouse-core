# iHouse Core — Current Snapshot

## Current Phase
Phase 45 — Ordering Buffer Auto-Trigger on BOOKING_CREATED

## Last Closed Phase
Phase 44 — OTA Ordering Buffer

## System Status

The deterministic event architecture remains fully operational.

`apply_envelope` remains the only authority allowed to mutate canonical booking state.

## Phase 44 Result

[Claude]

**Migration:** `ota_ordering_buffer` table:
- FK to `ota_dead_letter.id`
- `booking_id` — what the event is waiting for
- `event_type` — the blocked event
- `status` — `waiting` | `replayed` | `expired`
- Index on `(booking_id, status)` for fast lookup

**Module:** `ordering_buffer.py`
- `buffer_event(dlq_row_id, booking_id, event_type)` — write
- `get_buffered_events(booking_id)` — read waiting rows
- `mark_replayed(buffer_id)` — update after replay

**E2E verified** on live Supabase.

## Event Ordering Lifecycle (After Phase 44)

```
BOOKING_CANCELED arrives (too early)
         ↓ BOOKING_NOT_FOUND
    ota_dead_letter (DLQ)
         ↓ buffer_event()
    ota_ordering_buffer  ← [status: waiting]
         ↓ (Phase 45)
    BOOKING_CREATED arrives → check buffer → replay
         ↓
    mark_replayed()       ← [status: replayed]
```

## OTA Adapter Layer — Full Module Map

| Module | Role |
|--------|------|
| `dead_letter.py` | preserve rejected events in DLQ |
| `dlq_replay.py` | controlled replay → apply_envelope |
| `dlq_inspector.py` | read-only DLQ observability |
| `dlq_alerting.py` | threshold alerting |
| `booking_status.py` | read booking lifecycle status |
| `ordering_buffer.py` | ordering buffer: write + read + mark ← NEW |

## BOOKING_AMENDED Prerequisites: 4/10
(unchanged — no amendment work in Phase 44)

## Canonical Invariants

- event_log is append-only
- events are immutable
- booking_state is projection-only
- apply_envelope is the only write authority
- booking_id = "{source}_{reservation_ref}" — deterministic and canonical
- MODIFY → deterministic reject-by-default
