# Phase 34 — OTA Canonical Event Emission Alignment

## Status

Active

This file defines the active phase after Phase 33 closed.

## Depends On

Phase 33 — OTA Retry Business Idempotency Discovery

Phase 34 begins only after the OTA runtime boundary is already verified and Phase 33 has established that the strongest active risk is a likely alignment gap between the active OTA runtime path and the canonical emitted business event contract enforced by Supabase.

## Objective

Verify and align the active OTA runtime path so that OTA-originated `BOOKING_CREATED` and `BOOKING_CANCELED` reach `apply_envelope` through the canonical emitted business event contract expected by Supabase.

This phase is an alignment-definition phase.

It is not a redesign phase.
It is not a reconciliation phase.
It is not an amendment phase.

## Why Phase 34 Exists

Phase 33 showed that canonical Supabase business protection already exists for canonical emitted business events.

Phase 33 also showed that:

- `apply_envelope` performs canonical business handling from emitted events
- the active OTA adapters currently build transport-facing envelopes
- the active runtime skill routing currently appears misaligned with the canonical emitted business event contract expected by Supabase

Therefore the next smallest correct step is not broad hardening.

The next smallest correct step is to verify and align the emitted event path itself.

## What Is Already True

The following architectural facts remain locked:

- event_log is append-only
- events are immutable
- booking_state is projection-only
- apply_envelope is the only write authority
- adapters must not read booking_state
- adapters must not reconcile booking history
- adapters must not mutate canonical state
- provider-specific logic must remain isolated from the shared pipeline
- MODIFY remains deterministic reject-by-default

The OTA runtime contract remains:

ingest_provider_event  
→ process_ota_event  
→ canonical envelope  
→ IngestAPI.append_event  
→ CoreExecutor.execute  
→ apply_envelope

## In Scope

Phase 34 may include only the following categories of work:

### 1. Routing verification

- verify which active skills are currently mapped for OTA-originated `BOOKING_CREATED` and `BOOKING_CANCELED`
- verify whether those skills emit canonical business events or noop outputs
- verify whether any active alternate routing path exists in the runtime

### 2. Emitted event mapping verification

- inspect the canonical payload shape required by `apply_envelope`
- inspect the emitted business event shape currently produced by the active OTA runtime path
- identify the exact field and routing mismatch if alignment is not present

### 3. Minimal alignment definition

- define the smallest safe future change required to restore canonical emitted business event alignment
- keep the change bounded to routing and emitted event mapping unless stronger evidence proves otherwise
- update active docs minimally if executable evidence justifies it

## Out of Scope

Phase 34 must NOT introduce:

- reconciliation logic
- amendment handling
- booking_state reads inside adapters
- direct apply_envelope calls from OTA code
- OTA snapshot fetching
- out-of-order buffering
- new canonical event kinds
- adapter-side mutation
- broad schema redesign
- reopening Phase 28, 31, 32, or 33 decisions

## Required Questions To Answer

Phase 34 should answer these questions with evidence:

1. Which active runtime skill actually handles OTA-originated `BOOKING_CREATED` today?

2. Which active runtime skill actually handles OTA-originated `BOOKING_CANCELED` today?

3. Do those active skills emit canonical business events in the payload shape required by `apply_envelope`?

4. If not, what is the exact routing or emitted-event mapping mismatch?

5. What is the smallest future-safe alignment change required to restore canonical enforcement without changing architecture?

## Completion Conditions

Phase 34 is complete when:

- the active OTA emitted-event routing is described precisely
- the canonical emitted business event payload expected by `apply_envelope` is described precisely
- the exact active mismatch is demonstrated concretely rather than assumed
- the minimum future alignment target is defined without violating canonical invariants
- no canonical semantic decision is reopened

## Expected Exit Shape

The most likely Phase 34 exit is:

The active OTA runtime path is shown either to already emit canonical business events correctly, or to remain misaligned in a narrow and precisely defined way that can be corrected by future routing and emitted-event alignment work without broad architectural redesign.
