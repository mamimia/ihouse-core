# iHouse Core – Work Context

Current Phase  
Phase 29 – OTA Ingestion Replay Harness

Last Closed Phase  
Phase 28 – OTA External Surface Canonicalization


## Phase 28 Result

Phase 28 resolved the OTA external surface ambiguity.

The system no longer accepts the generic ingestion envelope:

BOOKING_SYNC_INGEST

OTA adapters must emit explicit canonical business events.

Canonical external events:

- BOOKING_CREATED
- BOOKING_CANCELED

OTA modification notifications remain classified as:

MODIFY  
→ deterministic reject-by-default


## Architectural Status

The canonical database gate remains the only authority allowed to
mutate booking_state.

Canonical invariants remain unchanged:

- event_log is append-only
- booking_state is projection-only
- adapters must not read booking_state
- adapters must not reconcile booking history
- adapters must not mutate canonical state
- adapters must not bypass apply_envelope


## Phase 29 Objective

Introduce deterministic OTA ingestion replay capability.

The goal of this phase is to enable safe replay of OTA event streams
against the canonical ingestion pipeline.

This allows the system to:

- simulate OTA event ingestion sequences
- validate deterministic behavior of adapters
- verify rejection rules
- test replay safety of the canonical event pipeline


## Phase 29 Constraints

Phase 29 must not introduce:

- reconciliation logic
- booking_state reads in adapters
- OTA provider polling
- modification resolution logic

The phase focuses exclusively on replay tooling for the ingestion pipeline.


## Expected Outcome

A deterministic replay harness capable of feeding OTA event sequences
into the ingestion pipeline and verifying canonical outcomes.

