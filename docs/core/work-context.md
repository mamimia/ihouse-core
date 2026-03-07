# iHouse Core – Work Context

## Current Active Phase

Phase 30 – OTA Ingestion Interface Hardening


## Last Closed Phase

Phase 29 – OTA Ingestion Replay Harness


## Current Objective

Harden the OTA ingestion interface that connects provider adapters to
the canonical execution path.

This phase exists to make the OTA-to-core handoff explicit, stable,
minimal, and testable.

It does not change canonical business semantics.

It does not reopen previously closed architectural decisions.


## Locked Architectural Reality

The system remains a deterministic domain event execution kernel.

System truth is derived from canonical events.

booking_state is projection-only.

apply_envelope is the only authority allowed to mutate state.

Supabase is canonical.

External systems must never bypass the canonical apply gate.


## Permanent Invariants

- event_log is append-only
- events are immutable
- booking_state is derived from events only
- apply_envelope is the only write authority
- adapters must not read booking_state
- adapters must not reconcile booking history
- adapters must not mutate canonical state
- adapters must not bypass apply_envelope
- provider-specific logic must remain isolated from the shared pipeline
- MODIFY remains deterministic reject-by-default


## Current OTA Runtime Boundary

The actual runtime handoff now confirmed in code is:

ingest_provider_event  
→ process_ota_event  
→ canonical envelope  
→ IngestAPI.ingest  
→ CoreExecutor.execute  
→ apply_envelope

This boundary must remain explicit and singular.


## Layer Responsibilities

### OTA Service Entry

Owns the provider-facing entrypoint.

Responsibilities:

- accept OTA ingress inputs
- invoke the shared OTA pipeline
- return canonical envelope output only

Must not:

- perform writes
- call apply_envelope directly
- infer business state
- reconcile history

### Shared OTA Pipeline

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
- execute writes

### Provider Adapters

Responsibilities:

- provider-specific normalization
- provider-specific envelope mapping

Must remain isolated from shared execution logic.

Must not:

- read booking_state
- reconcile history
- infer amendments
- perform writes

### Core Ingest API

Responsibilities:

- accept canonical envelope input
- require execution through CoreExecutor
- reject missing executor wiring

### Core Executor

Responsibilities:

- execute canonical envelopes
- preserve commit policy
- delegate state mutation only through the canonical apply path


## What Phase 30 Is Not

Phase 30 is not:

- reconciliation
- amendment handling
- OTA snapshot fetching
- out-of-order buffering
- booking_state reads in adapters
- alternative write path design
- historical transport cleanup


## Immediate Working Rule

Do not redesign the architecture.

Do not reopen Phase 28.

Do not reopen Phase 29 replay work unless a concrete defect is found.

Do only the minimum work required to harden and lock the OTA ingestion
interface.
