# iHouse Core — Current Snapshot

## Current Phase
Phase 44 — TBD

## Last Closed Phase
Phase 43 — booking_state Status Verification

## System Status

The deterministic event architecture remains fully operational.

`apply_envelope` remains the only authority allowed to mutate canonical booking state.

`MODIFY → deterministic reject-by-default` remains in place.

## Phase 43 Result

[Claude]

**Key correction:** Phase 42 incorrectly identified `booking_state.status` as missing. The column already exists and is managed correctly by `apply_envelope`:
- `BOOKING_CREATED` → `status = 'active'`
- `BOOKING_CANCELED` → `status = 'canceled'`

**E2E verified** on live Supabase: `active → canceled` transition confirmed.

**New module:** `src/adapters/ota/booking_status.py`
- `get_booking_status(booking_id, client=None) → str | None`
- Read-only, never used inside the ingestion path

## BOOKING_AMENDED Prerequisites: 4/10

| Prerequisite | Status |
|-------------|--------|
| DLQ infrastructure (Phases 38-39) | ✅ |
| booking_id stability | ✅ |
| MODIFY classification (semantics.py) | ✅ |
| booking_state.status column | ✅ (Phase 43 verified) |
| Normalized AmendmentPayload schema | ❌ |
| apply_envelope BOOKING_AMENDED branch | ❌ |
| event_kind enum: BOOKING_AMENDED | ❌ |
| ACTIVE-state amendment guard | ❌ |
| Amendment replay ordering rule | ❌ |
| Idempotency key for amendments | ❌ |

## Canonical External OTA Events

- BOOKING_CREATED
- BOOKING_CANCELED
- (BOOKING_AMENDED — future, 4/10 prerequisites met)

## Canonical Invariants

- event_log is append-only
- events are immutable
- booking_state is projection-only
- apply_envelope is the only write authority
- booking_id = "{source}_{reservation_ref}" — deterministic and canonical
- MODIFY → deterministic reject-by-default

## OTA Adapter Layer Summary

| Module | Role |
|--------|------|
| `dead_letter.py` | preserve rejected events |
| `dlq_replay.py` | controlled replay → apply_envelope |
| `dlq_inspector.py` | read-only DLQ observability |
| `dlq_alerting.py` | threshold alerting |
| `booking_status.py` | read booking lifecycle status (for amendment guards) |
