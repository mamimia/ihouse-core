# iHouse Core – Current Snapshot

Current Phase  
Phase 29 – OTA Ingestion Replay Harness

Last Closed Phase  
Phase 28 – OTA External Surface Canonicalization


## System Status

The deterministic event architecture remains fully operational.

The canonical database gate (`apply_envelope`) remains the only authority
allowed to mutate booking_state.

External systems interact with iHouse Core exclusively through the OTA
ingestion boundary.


## Phase 28 Result

Phase 28 resolved the ambiguity in the OTA external event surface.

The previous generic external envelope:

BOOKING_SYNC_INGEST

is no longer considered a canonical external business event.

OTA adapters must now emit explicit canonical lifecycle events that
represent the deterministic business outcome of the OTA notification.


## Canonical External OTA Events

The canonical OTA lifecycle events are now:

- BOOKING_CREATED
- BOOKING_CANCELED

These events represent explicit business facts entering the system.


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
- duplicate ingestion must remain idempotent


## OTA Boundary Status

OTA adapters perform:

- provider resolution
- payload normalization
- semantic classification
- semantic validation
- canonical envelope creation
- canonical envelope validation


Current provider status:

- Booking.com implemented
- Expedia scaffold added for architectural validation
- Airbnb not implemented
- Agoda not implemented
- Trip.com not implemented


## Modification Handling

OTA modification notifications are classified as:

MODIFY

Current rule:

MODIFY  
→ deterministic reject-by-default


## Future Improvements

OTA Sync Recovery Layer

A future reconciliation system capable of:

- detecting modification notifications
- triggering provider reservation re-fetch
- comparing OTA state with local state
- emitting deterministic canonical events

This layer must remain outside the canonical ingestion pipeline.

