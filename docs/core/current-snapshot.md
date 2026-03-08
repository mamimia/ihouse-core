# iHouse Core — Current Snapshot

## Current Phase
Phase 36 — TBD

## Last Closed Phase
Phase 35 — OTA Canonical Emitted Event Alignment Implementation

## System Status

The deterministic event architecture remains fully operational.

The canonical database gate (`apply_envelope`) remains the only authority allowed to mutate booking state.

OTA-originated `BOOKING_CREATED` and `BOOKING_CANCELED` now reach `apply_envelope` through the canonical emitted business event contract. The Phase 34 alignment gap is resolved.

## Phase 35 Result

[Claude]

Phase 35 implemented the minimal alignment defined by Phase 34.

Two new skills were implemented:
- `booking_created`: transforms OTA envelope payload into canonical `BOOKING_CREATED` emitted event shape
- `booking_canceled`: emits `BOOKING_CANCELED` with `booking_id` derived from provider + reservation_id

Registry updates routed `BOOKING_CREATED` and `BOOKING_CANCELED` to the new skills.

E2E verified against live Supabase:
- `BOOKING_CREATED` → `apply_envelope` returned `status: APPLIED`, `state_upsert_found: true`
- `BOOKING_CANCELED` → `apply_envelope` returned `status: APPLIED`, `state_upsert_found: true`

No canonical business semantics changed.
No alternative write path was introduced.
No new canonical event kinds were introduced.
MODIFY remains deterministic reject-by-default.

## Canonical External OTA Events

The canonical OTA lifecycle events remain:

- BOOKING_CREATED
- BOOKING_CANCELED

## Canonical Invariants

Event Store
- event_log is append-only
- events are immutable

State Model
- booking_state is projection-only
- booking_state is derived exclusively from events

Write Authority
- apply_envelope RPC is the only authority allowed to mutate booking state

Replay Safety
- duplicate envelopes must not create new events
- duplicate ingestion must remain idempotent
