# Phase 32 – OTA Ingestion Contract Test Verification

## Status

Active

This file defines the active phase after Phase 31 closed.


## Depends On

Phase 31 – OTA Ingestion Contract Verification

Phase 32 begins after Phase 31 closure and remains scoped to
verification-by-test only.


## Objective

Verify with executable evidence that the OTA-to-core runtime contract
locked by Phases 30 and 31 is enforced by the current implementation.

This phase may tighten or add tests where a real verification gap is
found, but it must not change canonical business semantics.

It is not a redesign phase.
It is not a reconciliation phase.
It is not an amendment phase.


## What Is Already True

The documented runtime boundary is:

ingest_provider_event
→ process_ota_event
→ canonical envelope
→ IngestAPI.append_event
→ CoreExecutor.execute
→ apply_envelope

The following architectural facts are already locked:

- OTA service entry is thin
- shared OTA pipeline owns normalization, validation, classification,
  and canonical envelope construction
- core ingest requires executor-backed execution
- CoreExecutor remains the single execution boundary
- apply_envelope remains the sole canonical write authority
- MODIFY remains deterministic reject-by-default


## Why Phase 32 Exists

Phase 31 aligned the documentation and interface contract to the live
implementation.

Phase 32 exists to convert that contract alignment into explicit
executable verification.

The purpose is not to add new behavior.

The purpose is to prove that the public OTA ingest contract, executor
boundary, and replay assumptions are enforced by tests and direct
verification.


## In Scope

Phase 32 may include only the following categories of work:

1. Contract verification by test
- verify the OTA service returns canonical envelope output only
- verify the shared OTA pipeline performs the expected ordered stages
- verify the core ingest API rejects missing executor wiring
- verify the executor remains the only execution boundary
- verify replay uses the same public ingest contract

2. Minimal test hardening
- add missing tests for real contract gaps
- refine existing tests to assert the locked runtime handoff
- verify no OTA path bypasses core ingest or executor

3. Reference verification
- verify test names, helpers, and fixtures align to `IngestAPI.append_event`
- remove stale references that imply `IngestAPI.ingest`
- verify no misleading contract wording remains in active docs or tests


## Out of Scope

Phase 32 must NOT introduce:

- reconciliation logic
- amendment handling
- booking_state reads inside adapters
- direct apply_envelope calls from OTA code
- alternate write paths
- OTA snapshot fetching
- out-of-order buffering
- provider-specific business inference beyond existing semantics
- new canonical event kinds
- reopening Phase 28 decisions


## Required Verification Targets

### OTA Service Entry
Must remain a thin provider-facing wrapper.
Must not perform writes.
Must not execute apply directly.

### Shared OTA Pipeline
Must remain responsible for:
- adapter lookup
- normalization
- structural validation
- semantic classification
- semantic validation
- canonical envelope creation
- canonical envelope validation

### Core Ingest API
Must require executor-backed ingest only.
Must reject missing executor wiring.

### Core Executor
Must remain the single execution boundary.
Must preserve commit policy.
Must not allow adapter-level mutation in canonical runtime.

### Replay Alignment
Replay tooling must rely on the same public contract as production flow.


## Completion Conditions

Phase 32 is complete when:

- executable coverage verifies the locked OTA runtime contract
- any real test or reference gap is corrected minimally
- no OTA path bypasses core ingest or executor
- no alternate write path exists
- no canonical semantic decision is reopened
