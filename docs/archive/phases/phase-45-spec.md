# Phase 45 — Ordering Buffer Auto-Trigger on BOOKING_CREATED

## Status

Active

## Depends On

Phase 44 — OTA Ordering Buffer (`ordering_buffer.py`)
Phase 39 — DLQ Controlled Replay (`dlq_replay.py`)

## Objective

Close the ordering loop. When BOOKING_CREATED is successfully applied, automatically check the ordering buffer for waiting events linked to that booking_id, and replay them in order.

## Flow After Phase 45

```
1. BOOKING_CANCELED arrives → BOOKING_NOT_FOUND
       ↓
   ota_dead_letter (Phase 38)
       ↓ buffer_event()
   ota_ordering_buffer [status: waiting]

2. BOOKING_CREATED arrives → APPLIED
       ↓ (trigger_ordered_replay)
   get_buffered_events(booking_id)
       ↓ for each:
   replay_dlq_row(dlq_row_id)  → apply_envelope
       ↓
   mark_replayed(buffer_id)
```

## Module: `ordering_trigger.py`

```python
def trigger_ordered_replay(booking_id: str, client=None) -> dict:
    # Returns: {replayed: int, failed: int, results: list[dict]}
```

- reads buffer rows for booking_id
- calls replay_dlq_row per row
- marks replayed on success, continues on failure
- never raises — best-effort

## Integration Point: `service.py`

In `ingest_provider_event_with_dlq`, after a successful BOOKING_CREATED result:

```python
if envelope.type == "BOOKING_CREATED" and status == "APPLIED":
    booking_id = emitted[0]["payload"].get("booking_id", "")
    if booking_id:
        trigger_ordered_replay(booking_id)  # best-effort, non-blocking
```

## Contract Tests

- empty buffer → 0 replayed, replay_dlq_row not called
- one waiting row → replay_dlq_row called with correct dlq_row_id, mark_replayed called
- replay failure → logged, continues, failed count incremented
- correct booking_id passed to get_buffered_events
- non-BOOKING_CREATED events must NOT trigger buffer check

## Completion Conditions

Phase 45 is complete when:
- `ordering_trigger.py` implements `trigger_ordered_replay`
- `service.py` calls it after BOOKING_CREATED APPLIED
- contract tests pass
- full E2E: CANCELED → buffer → CREATED → auto-replay confirmed
- all existing tests pass
