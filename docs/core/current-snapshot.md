# iHouse Core – Current Snapshot

System Version  
Phase 28 – OTA External Surface Decision (Active)

Last Closed Phase  
Phase 27 – Multi-OTA Adapter Architecture


## System Status

The deterministic event architecture remains fully operational.

The canonical database gate (`apply_envelope`) remains the only authority
allowed to mutate booking_state.

External systems interact with iHouse Core exclusively through the OTA
ingestion boundary.


## Phase 27 Result

Phase 27 introduced the shared multi-OTA adapter architecture.

Completed architectural outcomes:

- shared OTA orchestration pipeline introduced
- service layer reduced to entrypoint behavior
- provider registry extended to support multiple OTA adapters
- Booking.com retained as the concrete provider adapter
- Expedia scaffold adapter added to prove multi-provider extensibility

Result:

A new provider can now be added through the shared OTA adapter contract
without changing the canonical database gate or the shared orchestration
flow.


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


## Current Architectural Question

The OTA external ingestion surface currently uses a single external
envelope kind:

BOOKING_SYNC_INGEST

Phase 28 will decide whether this single surface remains sufficient
for multi-provider scale or whether the external canonical surface
must be split into more explicit deterministic kinds.


## Future Improvements

OTA Sync Recovery Layer

A future reconciliation system capable of:

- detecting modification notifications
- triggering provider reservation re-fetch
- comparing OTA state with local state
- emitting deterministic canonical events

This layer must remain outside the canonical ingestion pipeline.
