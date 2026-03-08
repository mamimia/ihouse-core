# Phase 44 — OTA Ordering Buffer

## Status

Active

## Problem

OTA events sometimes arrive out of order:
- `BOOKING_CANCELED` arrives before `BOOKING_CREATED`
- `apply_envelope` raises `BOOKING_NOT_FOUND`
- The event goes to `ota_dead_letter` (DLQ)

Currently DLQ rows are passive — there is no link between a buffered CANCELED row and the CREATED event that would unlock it. Operators must manually query the DLQ and call `replay_dlq_row()`.

## Solution

Add a structured ordering buffer:

1. When a rejection has `rejection_code = 'BOOKING_NOT_FOUND'`, the event is "ordering-blocked"
2. Write a row to `ota_ordering_buffer` linking the DLQ row to the `booking_id` it needs
3. When `BOOKING_CREATED` for that `booking_id` arrives and is applied, query the buffer and replay the waiting events

Phase 44 covers steps 1 and 2 (buffer table + write + read).
Phase 45 covers step 3 (auto-trigger on BOOKING_CREATED).

## Schema: `ota_ordering_buffer`

```sql
CREATE TABLE public.ota_ordering_buffer (
  id             bigserial        PRIMARY KEY,
  dlq_row_id     bigint           NOT NULL REFERENCES public.ota_dead_letter(id),
  booking_id     text             NOT NULL,
  event_type     text             NOT NULL,
  buffered_at    timestamptz      NOT NULL DEFAULT now(),
  status         text             NOT NULL DEFAULT 'waiting'
                                  CHECK (status IN ('waiting', 'replayed', 'expired'))
);
```

## API: `ordering_buffer.py`

```python
buffer_event(dlq_row_id, booking_id, event_type, client=None) → int  # buffer row id
get_buffered_events(booking_id, client=None) → list[dict]              # only 'waiting' rows
mark_replayed(buffer_id, client=None) → None
```

## Completion Conditions

Phase 44 is complete when:
- `ota_ordering_buffer` exists in Supabase
- `ordering_buffer.py` implements all three functions
- contract tests pass
- all existing tests pass
