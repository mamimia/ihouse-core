# iHouse Core – Current Snapshot

Current Phase  
Phase 30 – OTA Ingestion Interface Hardening

Last Closed Phase  
Phase 29 – OTA Ingestion Replay Harness


## System Status

The deterministic event architecture remains fully operational.

The canonical database gate (`apply_envelope`) remains the only authority
allowed to mutate booking_state.

External systems interact with iHouse Core exclusively through the OTA
ingestion boundary.


## Phase 29 Result

Phase 29 introduced deterministic OTA replay verification.

The system now includes replay tooling that validates OTA ingestion
through the canonical execution path:

ingest_provider_event  
→ canonical envelope  
→ CoreExecutor.execute  
→ apply_envelope

This allows deterministic verification of:

- booking creation
- booking cancellation
- duplicate replay behavior
- MODIFY rejection
- invalid payload rejection


## Canonical External OTA Events

The canonical OTA lifecycle events remain:

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

Replay tooling now verifies this boundary through the core execution path.


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


## Phase 30 Focus

Phase 30 focuses on OTA ingestion interface hardening.

This phase should clarify and stabilize the explicit handoff between:

- OTA ingestion entry
- canonical envelope shape
- core execution boundary
- replay verification contract

It must not introduce reconciliation, amendment handling, or out-of-order
processing.
