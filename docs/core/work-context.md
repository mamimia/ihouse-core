# iHouse Core – Work Context

Current Phase
Phase 24 – OTA Modification Semantics

System State

The canonical event system is fully operational.

Key invariants:

- apply_envelope RPC remains the only authority allowed to mutate booking_state
- event_log is append-only
- booking_state is projection-only
- OTA payloads are normalized and validated before canonical envelope creation

Completed Phases

Phase 21
Defined canonical OTA ingestion boundary.

Phase 22
Implemented OTA adapter layer and normalization pipeline.

Phase 23
Introduced deterministic semantic classification and semantic validation
for OTA events before envelope creation.

Current Objective

Phase 24 introduces deterministic handling for OTA modification events.

Problem

Certain OTA providers (Booking.com in particular) emit events such as
reservation_modified which do not map directly to a canonical booking event.

A modification may represent:

- non-booking change (ignored)
- booking update
- date change requiring cancel + recreate

Phase 24 will introduce explicit semantic handling rules for OTA modification
events to prevent semantic ambiguity in the canonical model.

