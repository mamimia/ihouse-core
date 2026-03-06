# Phase 28 – OTA External Surface Decision

## Status

Active Phase

Last Closed Phase  
Phase 27 – Multi-OTA Adapter Architecture


## Objective

Decide whether the OTA ingestion boundary should continue to emit a
single canonical external envelope kind:

BOOKING_SYNC_INGEST

or whether the external OTA surface must be split into more explicit
deterministic kinds aligned with semantic outcomes such as CREATE and
CANCEL.

This is a contract decision phase.

It is not a reconciliation phase.
It is not a provider implementation phase.


## Background

The current OTA pipeline already performs:

- provider resolution
- normalization
- structural validation
- semantic classification
- semantic validation
- canonical envelope creation
- canonical envelope validation

The current shared validator accepts one external envelope kind:

BOOKING_SYNC_INGEST

This means multiple deterministic OTA outcomes are currently funneled
through a single external canonical type.

This may be sufficient.
It may also become too implicit as more providers are added.


## Architectural Question

Should the OTA external surface remain:

one external kind  
BOOKING_SYNC_INGEST

with semantic differentiation represented inside payload structure

or should the OTA boundary emit a more explicit deterministic external
surface with distinct canonical kinds for distinct outcomes.


## Hard Constraints

Phase 28 must preserve all existing invariants:

- apply_envelope remains the only write authority
- booking_state remains projection-only
- event_log remains append-only
- adapters must not read booking_state
- adapters must not reconcile booking history
- MODIFY remains deterministic reject-by-default

Phase 28 must not introduce:

- OTA Sync Recovery Layer
- snapshot reconciliation
- provider API fetch workflows
- out-of-order buffering
- booking_state reads in adapters


## Evaluation Criteria

The decision must evaluate:

1. Clarity  
   Does the external canonical surface clearly express deterministic
   business meaning.

2. Scalability  
   Can additional OTA providers be added without semantic drift.

3. Validation discipline  
   Can the validator contract remain strict and explicit.

4. Replay safety  
   Does the external surface preserve deterministic replay behavior.

5. Provider isolation  
   Does the surface prevent provider-specific semantics from leaking
   into the canonical event model.


## Possible Outcomes

### Outcome A

Retain a single external kind:

BOOKING_SYNC_INGEST

If retained, the phase must justify why a single external kind is
architecturally sufficient for multi-provider scale.

### Outcome B

Split the external OTA surface into more explicit deterministic kinds.

If split, the phase must define:

- the new external canonical kinds
- adapter contract changes
- validator changes
- backward compatibility expectations


## Completion Conditions

Phase 28 is complete when:

1. The OTA external surface decision is made explicitly.
2. The decision is reflected in canonical docs.
3. The validator and adapter contract implications are defined.
4. No deterministic invariants are weakened.
5. No reconciliation logic is introduced.
