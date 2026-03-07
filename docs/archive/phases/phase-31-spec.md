# Phase 31 – OTA Ingestion Contract Verification

## Status

Active

This file defines the active verification phase after Phase 30 closed.


## Depends On

Phase 30 – OTA Ingestion Interface Hardening

Phase 31 begins after Phase 30 closure and remains scoped to minimal
contract verification and hardening only.


## Objective

Verify and minimally harden the live OTA-to-core execution contract in
code and tests without changing canonical business semantics.

This phase exists to confirm that the runtime interface documented in
Phase 30 is consistently enforced by the implementation.

This is a verification phase with minimal hardening only.

It is not a redesign phase.
It is not a reconciliation phase.
It is not an amendment phase.


## What Is Already True

The current runtime model already shows the intended boundary:

ingest_provider_event
→ process_ota_event
→ canonical envelope
→ IngestAPI.append_event
→ CoreExecutor.execute
→ apply_envelope

What is already established:

- OTA service entry is thin
- shared OTA pipeline owns normalization, validation, classification,
  and canonical envelope construction
- provider adapters remain provider-specific translation only
- core ingest requires execution through CoreExecutor
- CoreExecutor remains the single execution boundary
- apply_envelope remains the sole canonical write authority
- MODIFY remains deterministic reject-by-default


## Why Phase 31 Exists

Phase 30 locks the interface contract at the documentation and boundary
definition level.

Phase 31 exists to verify that the implementation consistently matches
that contract and to close any small enforcement gaps that are found.

The purpose is not to add behavior.

The purpose is to remove ambiguity between documented runtime flow,
test assumptions, and actual execution wiring.


## In Scope

Phase 31 may include only the following categories of work:

1. Contract verification
- verify the OTA service returns canonical envelope output only
- verify the shared OTA pipeline performs the expected ordered stages
- verify the core ingest API rejects missing executor wiring
- verify the executor remains the only execution boundary

2. Minimal runtime hardening
- tighten type or shape checks at the OTA-to-core handoff
- remove small ambiguity in method naming or call shape if needed
- align replay assumptions with the same public ingest contract

3. Test hardening
- add or refine tests that prove the OTA-to-core contract remains stable
- verify no direct OTA call path bypasses core ingest or executor
- verify duplicate and invalid paths remain deterministic


## Out of Scope

Phase 31 must NOT introduce:

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

Phase 31 is complete when:

- the live OTA-to-core runtime contract is verified against the current implementation
- any real interface drift is corrected with minimal hardening only
- test or reference coverage is aligned to the same public ingest contract
- no alternate write path exists
- no Phase 30 architectural decision is reopened
