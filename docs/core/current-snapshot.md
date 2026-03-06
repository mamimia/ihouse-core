# iHouse Core – Current Snapshot

System Version  
Phase 24 – OTA Modification Semantics (Active)

Last Closed Phase  
Phase 23 – External Event Semantics Hardening


## System Status

The deterministic event architecture is fully operational.

The canonical database gate (`apply_envelope`) remains the only authority
allowed to mutate booking_state.

External systems interact with iHouse Core exclusively through the OTA
ingestion boundary.


## Canonical Invariants

Event Store
- event_log is append-only
- events are immutable

State Model
- booking_state is projection-only
- booking_state is derived exclusively from events

Write Authority
- apply_envelope RPC is the only authority allowed to mutate booking_state

Replay Safety
- duplicate envelopes must not create new events
- duplicate envelopes must not mutate booking_state


## OTA Ingestion Pipeline

External OTA payload

↓ adapter normalization

↓ validate_normalized_event

↓ classify_normalized_event        (added in Phase 23)

↓ validate_classified_event        (added in Phase 23)

↓ to_canonical_envelope

↓ validate_canonical_envelope

↓ append_event

↓ apply_envelope (database gate)


## OTA Adapters

Current adapters

- Booking.com

Responsibilities

Adapters must:

- normalize external payloads
- classify OTA event semantics
- validate semantic consistency
- produce canonical envelopes

Adapters must not:

- perform booking lookups
- perform duplicate detection
- mutate booking_state
- bypass the canonical database gate


## Current Focus

Phase 24 introduces deterministic handling of OTA modification events.

Certain OTA providers emit events such as `reservation_modified`
which do not map directly to canonical CREATE or CANCEL events.

Phase 24 introduces explicit semantic mapping rules for these events
while preserving the canonical database gate as the sole authority
for booking identity and duplicate enforcement.

