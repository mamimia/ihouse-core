# iHouse Core — Current Snapshot

## Current Phase
Phase 46 — TBD

## Last Closed Phase
Phase 45 — Ordering Buffer Auto-Trigger on BOOKING_CREATED

## System Status

The deterministic event architecture remains fully operational.

`apply_envelope` remains the only authority allowed to mutate canonical booking state.

**The out-of-order event problem is now fully handled (Phases 44+45).**

## Phase 45 Result

[Claude]

The ordering loop is closed.

**Flow (fully operational):**

```
BOOKING_CANCELED arrives too early
        ↓ BOOKING_NOT_FOUND
  ota_dead_letter (DLQ)         Phase 38
        ↓ buffer_event()
  ota_ordering_buffer [waiting]  Phase 44

BOOKING_CREATED arrives → APPLIED
        ↓ trigger_ordered_replay()    Phase 45
  get_buffered_events(booking_id)
        ↓ per row:
  replay_dlq_row(dlq_row_id)         Phase 39
        ↓
  mark_replayed(buffer_id)      Phase 44
```

E2E verified: CANCELED buffered → CREATED applied → auto-trigger → 0 waiting in buffer.

## OTA Adapter Layer — Full Module Map

| Module | Role |
|--------|------|
| `dead_letter.py` | preserve rejected events in DLQ |
| `dlq_replay.py` | controlled replay → apply_envelope |
| `dlq_inspector.py` | read-only DLQ observability |
| `dlq_alerting.py` | threshold alerting |
| `booking_status.py` | read booking lifecycle status |
| `ordering_buffer.py` | ordering buffer: write, read, mark |
| `ordering_trigger.py` | auto-trigger on BOOKING_CREATED ← NEW |

## BOOKING_AMENDED Prerequisites

4/10 satisfied. External Event Ordering Buffer (Phases 44-45) now also satisfies the "ordering infrastructure" prerequisite.

Updated status:

| Prerequisite | Status |
|-------------|--------|
| DLQ infrastructure (Phases 38-39) | ✅ |
| booking_id stability | ✅ |
| MODIFY classification (semantics.py) | ✅ |
| booking_state.status column | ✅ |
| Ordering infrastructure | ✅ (Phases 44-45) |
| Normalized AmendmentPayload schema | ❌ |
| apply_envelope BOOKING_AMENDED branch | ❌ |
| event_kind enum: BOOKING_AMENDED | ❌ |
| ACTIVE-state amendment guard | ❌ |
| Idempotency key for amendments | ❌ |

**5/10 prerequisites now satisfied.**

## Canonical Invariants

- event_log is append-only
- events are immutable
- booking_state is projection-only
- apply_envelope is the only write authority
- booking_id = "{source}_{reservation_ref}" — deterministic and canonical
- MODIFY → deterministic reject-by-default
