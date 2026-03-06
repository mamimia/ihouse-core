# Phase 29 – OTA Ingestion Replay Harness

## Status

Active Phase

Last Closed Phase  
Phase 28 – OTA External Surface Canonicalization


## Objective

Introduce a deterministic replay harness for the OTA ingestion pipeline.

The goal of this phase is to allow controlled simulation of OTA event
streams entering the system and verify that the canonical ingestion
pipeline behaves deterministically under replay.

This phase introduces testing and verification tooling only.

It does not introduce new business behavior.


## Background

Phase 27 introduced the shared multi-provider OTA adapter architecture.

Phase 28 resolved the external OTA surface decision and established
explicit canonical lifecycle events:

BOOKING_CREATED  
BOOKING_CANCELED

The generic transport envelope:

BOOKING_SYNC_INGEST

is no longer considered canonical.

As additional OTA providers are introduced, it becomes critical to
verify that the ingestion pipeline remains deterministic and safe
under replay conditions.

A replay harness enables safe testing of:

- adapter normalization
- semantic classification
- canonical envelope creation
- canonical validation
- database gate behavior


## Architectural Context

The OTA ingestion pipeline currently performs:

provider registry resolution  
→ adapter normalization  
→ structural validation  
→ semantic classification  
→ semantic validation  
→ canonical envelope creation  
→ canonical envelope validation  
→ apply_envelope (DB gate)


Replay testing must exercise this pipeline exactly as production
ingestion would.


## Hard Constraints

Phase 29 must preserve all canonical invariants:

- apply_envelope remains the only write authority
- booking_state remains projection-only
- event_log remains append-only
- adapters must not read booking_state
- adapters must not reconcile booking history
- MODIFY remains deterministic reject-by-default


Phase 29 must NOT introduce:

- reconciliation logic
- OTA provider polling
- snapshot fetch workflows
- booking_state reads inside adapters
- amendment handling


The replay harness must operate entirely outside the canonical
state mutation logic.


## Replay Harness Scope

The harness should allow controlled replay of OTA event sequences
against the ingestion pipeline.

Example usage:

simulate provider webhook events
→ feed events through pipeline
→ observe canonical outcomes


The harness should support testing of scenarios such as:

valid booking creation  
duplicate envelope replay  
deterministic cancellation  
rejection of MODIFY events  
invalid payload rejection


## Evaluation Criteria

The replay harness must allow verification of:

1. Deterministic Behavior

The same replay sequence must always produce the same canonical
outcomes.

2. Replay Safety

Duplicate envelopes must never mutate canonical state.

3. Adapter Stability

Adapters must produce deterministic canonical envelopes from
normalized OTA payloads.

4. Validator Correctness

Invalid events must be deterministically rejected.


## Completion Conditions

Phase 29 is complete when:

1. A replay harness exists capable of feeding OTA event sequences
   through the ingestion pipeline.

2. The harness can simulate multiple OTA scenarios.

3. Deterministic behavior under replay is verified.

4. Duplicate envelope replay produces no additional state mutation.

5. Canonical invariants remain unchanged.


## Non Goals

Phase 29 must NOT introduce:

- OTA reconciliation logic
- amendment support
- out-of-order buffering
- snapshot comparison
- booking_state inspection inside adapters

Those capabilities may appear in later phases.


## Expected Outcome

A deterministic replay framework for OTA ingestion that allows safe
testing of provider integrations without compromising the canonical
event architecture.

This tooling prepares the system for future expansion to additional
OTA providers while preserving deterministic behavior.

