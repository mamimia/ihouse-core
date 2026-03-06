# iHouse Core – Work Context

Current Phase  
Phase 28 – OTA External Surface Decision

Last Closed Phase  
Phase 27 – Multi-OTA Adapter Architecture


## Phase 28 Objective

Decide whether the current OTA external ingestion surface should
remain a single canonical envelope kind:

BOOKING_SYNC_INGEST

or be split into more explicit deterministic external kinds aligned
with OTA semantic outcomes.

This phase is a contract decision phase.

It must not introduce reconciliation logic or modify the DB gate.


## Phase 27 Closed Result

Phase 27 introduced the shared multi-OTA adapter architecture.

Completed:

- shared OTA orchestration pipeline added
- service layer reduced to entrypoint behavior
- provider registry now supports multiple providers
- Booking.com remains the concrete provider implementation
- Expedia scaffold adapter added to validate provider extensibility

Meaning:

The architecture is now multi-provider, but not all target OTA
providers are fully implemented yet.


## Architectural Constraints

The following invariants remain unchanged:

- apply_envelope remains the only authority allowed to mutate booking_state
- event_log remains append-only
- booking_state remains projection-only
- adapters must not perform booking_state lookup
- adapters must not reconcile booking history
- adapters must not mutate canonical state
- adapters must not bypass the canonical database gate


## Canonical OTA Event Surface

Current external envelope kind:

BOOKING_SYNC_INGEST

OTA modification notifications remain classified as:

MODIFY

Current rule:

MODIFY  
→ deterministic reject-by-default


## Phase 28 Scope

This phase must decide whether the external OTA surface remains:

single kind:
BOOKING_SYNC_INGEST

or becomes a more explicit external canonical surface aligned with
deterministic CREATE / CANCEL outcomes.

This phase may update:

- adapter contract
- validator contract
- external canonical surface documentation

This phase must not update:

- booking_state mutation authority
- apply_envelope write authority
- reconciliation rules
- modification handling rules


## Expected Outcome

A clear canonical decision about the OTA external surface that can
support future provider additions without ambiguity or semantic drift.
