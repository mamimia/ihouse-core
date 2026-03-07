# Phase 30 – OTA Ingestion Interface Hardening

## Status

Active Phase

Last Closed Phase  
Phase 29 – OTA Ingestion Replay Harness


## Objective

Harden the OTA ingestion interface that connects provider adapters to
the canonical execution path.

The purpose of this phase is to make the OTA-to-core handoff explicit,
stable, minimal, and testable without changing the canonical event
architecture.

This phase is a boundary-hardening phase.

It is not a reconciliation phase.
It is not an amendment phase.
It does not introduce new canonical business behavior.


## Background

Phase 27 introduced the shared multi-provider OTA adapter architecture.

Phase 28 canonicalized the external OTA event surface into explicit
business lifecycle events:

BOOKING_CREATED  
BOOKING_CANCELED

Phase 29 introduced deterministic replay verification across the OTA
ingestion path and the core execution boundary.

That work exposed an important architectural reality:

The OTA layer itself stops at canonical envelope construction.

The actual canonical write path continues through core execution:

ingest_provider_event  
→ canonical envelope  
→ CoreExecutor.execute  
→ apply_envelope

This means the interface between OTA ingestion and core execution is
now a first-class architectural boundary and should be hardened
explicitly.


## Architectural Problem

Without an explicit and stable OTA ingestion interface, future provider
expansion can drift in small but dangerous ways.

Typical risks include:

- inconsistent tenant propagation
- implicit canonical envelope assumptions
- mismatched replay harness expectations
- hidden coupling between adapters and core execution
- ambiguous ownership between OTA service layer and core executor

These issues do not require architectural redesign to fix.

They require contract hardening.


## Phase 30 Scope

Phase 30 should define and stabilize the minimal OTA ingestion
interface that production code and replay tooling both rely on.

This includes clarifying:

1. OTA Entry Contract

What the provider-facing entrypoint accepts.

Expected inputs should remain explicit, minimal, and deterministic.

2. Canonical Envelope Contract

What shape leaves the OTA pipeline and enters the core executor.

3. Execution Handoff Contract

How the canonical envelope is passed into CoreExecutor.execute and what
is considered part of the stable execution boundary.

4. Replay Verification Contract

What the replay harness is allowed to assume and verify without
becoming a second execution surface.

5. Responsibility Split

What belongs to:
- service layer
- shared OTA pipeline
- provider adapter
- core executor

The goal is to eliminate ambiguity without changing system authority.


## Hard Constraints

Phase 30 must preserve all canonical invariants:

- apply_envelope remains the only write authority
- booking_state remains projection-only
- event_log remains append-only
- adapters must not read booking_state
- adapters must not reconcile booking history
- adapters must not mutate canonical state
- provider logic must remain isolated from the shared pipeline
- MODIFY remains deterministic reject-by-default


Phase 30 must NOT introduce:

- reconciliation logic
- OTA snapshot fetching
- amendment handling
- out-of-order buffering
- business-state inference in adapters
- alternative write paths
- transport cleanup unrelated to the interface contract


## Required Deliverables

Phase 30 should end with the following outcomes.

### 1. Explicit OTA Ingestion Interface

The project should expose a clear and stable OTA entry contract.

The entrypoint must remain thin and deterministic.

### 2. Explicit Envelope-to-Core Handoff

The handoff from OTA envelope creation into CoreExecutor.execute
should be documented and, where needed, minimally normalized so the
boundary is clear.

### 3. Replay Harness Compatibility Lock

The replay harness should rely on the same interface contract rather
than hidden assumptions.

### 4. Responsibility Clarification

The project docs should state exactly which layer owns:

- provider resolution
- normalization
- semantic classification
- canonical envelope creation
- execution handoff
- write-gate invocation

### 5. Stability Verification

Tests should confirm that the hardened interface remains stable and
does not weaken existing deterministic behavior.


## Non Goals

Phase 30 does NOT include:

- OTA reconciliation
- provider sync recovery
- BOOKING_AMENDED
- amendment interpretation
- historical transport artifact cleanup
- additional provider implementations beyond what is needed for
  interface verification
- booking_state reads in adapters
- replay-time state mutation outside apply_envelope


## Completion Conditions

Phase 30 is complete when:

1. The OTA ingress contract is explicit and stable.
2. The canonical envelope handoff into CoreExecutor.execute is explicit.
3. The replay harness depends on this contract cleanly.
4. Responsibility boundaries are documented without ambiguity.
5. Existing deterministic invariants remain unchanged.
6. Test coverage confirms the hardened interface.


## Expected Outcome

A hardened OTA ingestion interface that makes provider integration,
core execution handoff, and replay verification operate on the same
explicit contract.

This prepares the system for safer future provider expansion without
reopening Phase 28 decisions or introducing reconciliation behavior.
