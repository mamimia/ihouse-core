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

That work confirmed the actual runtime boundary:

ingest_provider_event  
→ process_ota_event  
→ canonical envelope  
→ IngestAPI.ingest  
→ CoreExecutor.execute  
→ apply_envelope

This means the interface between OTA ingestion and core execution is
a first-class architectural boundary and must be hardened explicitly.


## Architectural Problem

Without an explicit and stable OTA ingestion interface, future provider
expansion can drift in small but dangerous ways.

Typical risks include:

- inconsistent tenant propagation
- implicit canonical envelope assumptions
- hidden coupling between adapters and executor internals
- replay tooling depending on unstable implementation details
- ambiguous ownership between OTA service, OTA pipeline, and core ingest

These risks do not require architectural redesign.

They require contract hardening.


## Phase 30 Scope

Phase 30 defines and stabilizes the minimal OTA ingestion contract that
production code and replay tooling both rely on.

This includes clarifying:

1. OTA Entry Contract

The provider-facing OTA entrypoint remains:

ingest_provider_event(...)

This entrypoint must stay thin and deterministic.

It may orchestrate OTA processing, but it must not execute writes,
mutate state, or bypass core ingest.

2. Canonical Envelope Contract

The shared OTA pipeline is responsible for producing a validated
canonical envelope.

The output of OTA processing is a canonical envelope ready for the
canonical ingest path.

3. Execution Handoff Contract

The canonical envelope must enter core execution only through the
ingest API boundary and then CoreExecutor.execute.

OTA code must not call apply_envelope directly.

4. Replay Verification Contract

Replay tooling may verify the OTA ingestion path only through the same
public execution handoff used by production flow.

Replay tooling must not become a second execution surface.

5. Responsibility Split

The responsibility boundary must remain explicit across:

- OTA service entry
- shared OTA pipeline
- provider adapter
- core ingest API
- core executor


## Stable Responsibility Model

### OTA Service Layer

Owns the provider-facing entrypoint.

Responsibilities:

- accept explicit OTA ingress inputs
- invoke the shared OTA pipeline
- return a canonical envelope for core ingest

Must not:

- execute canonical writes
- call apply_envelope directly
- infer business state
- reconcile history

### Shared OTA Pipeline

Owns shared OTA processing.

Responsibilities:

- adapter resolution
- normalized payload construction
- structural validation
- semantic classification
- semantic validation
- canonical envelope creation
- canonical envelope validation

Must not:

- mutate canonical state
- read booking_state
- execute core writes

### Provider Adapter

Owns provider-specific translation only.

Responsibilities:

- provider-specific normalization
- provider-specific envelope mapping

Must remain isolated from shared execution logic.

Must not:

- read booking_state
- reconcile booking history
- infer amendments
- perform writes

### Core Ingest API

Owns the canonical ingest handoff.

Responsibilities:

- accept canonical envelope input
- require execution through CoreExecutor
- reject missing executor wiring

This boundary is the explicit bridge from OTA ingestion into core
execution.

### Core Executor

Owns canonical execution.

Responsibilities:

- execute the canonical envelope
- preserve commit policy
- delegate mutation only through the canonical apply path

This is the only execution boundary for OTA-originated canonical
envelopes.


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
- direct apply_envelope calls from OTA code
- transport cleanup unrelated to the interface contract


## Required Deliverables

Phase 30 should end with the following outcomes.

### 1. Explicit OTA Entry Contract

The project exposes a clear OTA entrypoint that remains thin and
deterministic.

### 2. Explicit Envelope-to-Core Handoff

The handoff from OTA envelope creation into IngestAPI.ingest and
CoreExecutor.execute is documented as a stable boundary.

### 3. Replay Harness Compatibility Lock

Replay verification depends on the same OTA-to-core contract used by
production flow.

### 4. Responsibility Clarification

The docs state exactly which layer owns:

- provider resolution
- normalization
- semantic classification
- canonical envelope creation
- canonical ingest handoff
- execution
- write-gate invocation

### 5. Stability Verification

Tests confirm that the hardened interface remains stable and does not
weaken deterministic behavior.


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

1. The OTA entry contract is explicit and stable.
2. The canonical envelope handoff into core ingest is explicit.
3. The executor boundary is explicit and singular.
4. Replay harness assumptions are aligned to this contract.
5. Responsibility boundaries are documented without ambiguity.
6. Existing deterministic invariants remain unchanged.
7. Test coverage confirms the hardened interface.


## Expected Outcome

A hardened OTA ingestion interface that makes provider integration,
core execution handoff, and replay verification operate on the same
explicit contract.

This prepares the system for safer future provider expansion without
reopening Phase 28 decisions or introducing reconciliation behavior.
