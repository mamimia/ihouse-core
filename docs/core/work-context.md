# iHouse Core — Work Context

## Current Active Phase

Phase 34 — OTA Canonical Event Emission Alignment

## Last Closed Phase

Phase 33 — OTA Retry Business Idempotency Discovery

## Current Objective

Determine exactly where the active OTA runtime path fails to emit the canonical business event shape expected by `apply_envelope`, and define the smallest safe alignment work required to restore canonical enforcement.

This phase remains a discovery and alignment-definition phase only.

It is not a redesign phase.
It is not a reconciliation phase.
It is not an amendment phase.

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

The verified runtime handoff remains:

ingest_provider_event  
→ process_ota_event  
→ canonical envelope  
→ IngestAPI.append_event  
→ CoreExecutor.execute  
→ apply_envelope

## Phase 33 Closed Finding

Phase 33 did not prove an intrinsic failure of canonical Supabase business dedup.

Phase 33 did verify a likely alignment gap between:

- OTA adapter envelope shape
- executor skill routing
- emitted business event shape
- canonical Supabase apply contract

The strongest current evidence indicates that the active OTA runtime path may not currently emit the canonical business event payload required for Supabase enforcement to operate as intended.

## Phase 34 Scope

Allowed work:

- inspect active skill routing for OTA-originated `BOOKING_CREATED` and `BOOKING_CANCELED`
- inspect emitted event construction used by the active OTA runtime path
- verify the exact canonical payload shape expected by `apply_envelope`
- verify whether the active runtime path reaches that shape today
- define the smallest safe future alignment change required if misalignment is confirmed
- update active docs minimally if evidence justifies it

Disallowed work:

- reconciliation
- amendment handling
- OTA snapshot fetching
- out-of-order buffering
- booking_state reads inside adapters
- adapter-side mutation of canonical state
- alternative write paths
- direct apply_envelope calls from OTA code
- new canonical event kinds
- reopening closed phase decisions

## Immediate Working Rule

Do not redesign the architecture.

Do not reopen closed phases.

Do only the minimum work required to align the active OTA runtime path with the canonical emitted business event contract already enforced by Supabase.

## Exit Condition For This Phase

Phase 34 is ready to close when the docs and evidence together support one precise conclusion:

either

- the active OTA runtime path is shown to emit canonical business events in the exact shape expected by `apply_envelope`, and no active alignment gap remains

or

- the active OTA runtime path is shown to remain misaligned with the canonical emitted business event contract, and the minimal future hardening change is defined precisely without changing architecture or reopening closed phases
