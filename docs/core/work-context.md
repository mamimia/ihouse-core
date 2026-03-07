# iHouse Core – Work Context

Current Phase  
Phase 30 – OTA Ingestion Interface Hardening

Last Closed Phase  
Phase 29 – OTA Ingestion Replay Harness


## Phase 29 Result

Phase 29 added deterministic OTA replay verification.

The system now verifies OTA ingestion through:

ingest_provider_event  
→ canonical envelope  
→ CoreExecutor.execute

Replay coverage includes:

- BOOKING_CREATED
- BOOKING_CANCELED
- duplicate replay
- MODIFY rejection
- invalid payload rejection

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


## Phase 30 Objective

Phase 30 hardens the OTA ingestion interface.

The goal of this phase is to make the handoff between OTA ingestion,
canonical envelope execution, and replay verification fully explicit,
stable, and testable.

This phase should clarify and lock:

- the minimal OTA entry contract
- the canonical envelope handoff into core execution
- the replay-oriented verification contract
- the boundary between OTA orchestration and core execution


## Phase 30 Constraints

Phase 30 must not introduce:

- reconciliation logic
- booking_state reads in adapters
- OTA provider polling
- modification resolution logic
- amendment handling
- out-of-order event handling
- cleanup of historical transport artifacts unless explicitly reopened


## Expected Outcome

A hardened and explicitly documented OTA ingestion interface with stable
contracts across service, pipeline, envelope execution, and replay
verification.
