# iHouse Core – Current Snapshot

Current Phase  
Phase 30 – OTA Ingestion Interface Hardening

Last Closed Phase  
Phase 29 – OTA Ingestion Replay Harness


## System Status

The deterministic event architecture remains fully operational.

The canonical database gate (`apply_envelope`) remains the only
authority allowed to mutate booking_state.

External systems interact with iHouse Core through the OTA ingestion
boundary and then the canonical core ingest path.


## Phase 29 Result

Phase 29 introduced deterministic OTA replay verification.

The system now includes replay tooling that validates OTA ingestion
through the canonical execution path:

ingest_provider_event  
→ process_ota_event  
→ canonical envelope  
→ IngestAPI.ingest  
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


## OTA Interface Status

OTA service layer responsibilities:

- accept provider-facing ingress inputs
- invoke the shared OTA pipeline
- return canonical envelope output only

Shared OTA pipeline responsibilities:

- provider resolution
- payload normalization
- structural validation
- semantic classification
- semantic validation
- canonical envelope creation
- canonical envelope validation

Core ingest responsibilities:

- accept canonical envelope input
- route execution through CoreExecutor only

Core executor responsibilities:

- execute canonical envelopes
- preserve commit policy
- keep write authority behind apply_envelope


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

This phase clarifies and stabilizes the explicit handoff between:

- OTA service entry
- shared OTA pipeline
- canonical envelope output
- core ingest API
- CoreExecutor execution boundary
- replay verification contract

It must not introduce reconciliation, amendment handling, or out-of-order
processing.
