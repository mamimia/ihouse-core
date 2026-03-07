# Phase 33 — OTA Retry Business Idempotency Discovery

## Status

Active

This file defines the active phase after Phase 32 closed.

## Depends On

Phase 32 — OTA Ingestion Contract Test Verification

Phase 33 begins only after the OTA runtime contract is already locked and verified by executable evidence.

## Objective

Determine whether OTA-originated duplicate business facts can bypass the current transport-level idempotency boundary, and verify whether the active OTA runtime path is actually aligned with the canonical emitted business event contract required by `apply_envelope`.

This phase is a discovery and boundary-definition phase.

It is not an implementation-heavy phase.
It is not a reconciliation phase.
It is not an amendment phase.

## Why Phase 33 Exists

The current system protects transport retries through envelope idempotency.

A deferred backlog item already notes that future OTA integrations may send repeated business events with different request identifiers.

That remains a valid discovery question.

However, the evidence gathered during this phase narrows the active problem more precisely:

- canonical Supabase business protection already exists for canonical emitted business events
- canonical business handling in `apply_envelope` operates on emitted business events, not on the raw OTA envelope alone
- the active OTA runtime path currently appears to route `BOOKING_CREATED` through a noop skill rather than through a skill that emits the canonical business event payload expected by the Supabase apply contract

Therefore the current strongest verified concern is runtime mapping and routing alignment between:

- OTA adapter envelope shape
- executor skill routing
- emitted business event shape
- canonical Supabase apply contract

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

Phase 33 may include only the following categories of work:

### 1. Discovery and evidence gathering

- inspect current OTA identity fields used across normalized payload, canonical envelope, emitted events, and downstream apply path
- identify whether duplicate business facts could arrive with different envelope or request identifiers
- verify how the current runtime behaves when business-duplicate OTA events differ only in transport identity
- inspect existing canonical business identity constraints already present in Supabase
- inspect whether the active OTA runtime path actually reaches those canonical business identity constraints

### 2. Boundary definition

- determine whether the existing canonical business identity is already sufficient for OTA-originated duplicate protection when canonical emitted business events reach it
- determine whether the active OTA runtime path is aligned or misaligned with the canonical emitted business event contract
- if misaligned, define the smallest safe future hardening target without implementation of reconciliation or amendment logic
- document the exact separation between transport idempotency, emitted business event routing, and canonical business identity enforcement

### 3. Minimal verification work

- add focused tests only if needed to prove current behavior
- add fixtures or helpers only if required to reproduce OTA scenarios
- update active docs only if executable evidence justifies the wording

## Out of Scope

Phase 33 must NOT introduce:

- reconciliation logic
- amendment handling
- booking_state reads inside adapters
- direct apply_envelope calls from OTA code
- OTA snapshot fetching
- out-of-order buffering
- new canonical event kinds
- adapter-side mutation
- speculative schema changes without verified need
- reopening Phase 28, 31, or 32 decisions

## Evidence Gathered In This Phase

The current evidence set shows:

1. OTA adapters currently derive transport idempotency from provider `external_event_id`.

2. The active OTA adapter envelope shape uses provider-facing fields such as `provider`, `reservation_id`, `property_id`, and raw provider payload context.

3. `CoreExecutor` forwards the original envelope together with emitted events to `apply_envelope`.

4. `apply_envelope` performs canonical `BOOKING_CREATED` and `BOOKING_CANCELED` business handling from emitted events.

5. Canonical Supabase handling for `BOOKING_CREATED` requires canonical business payload keys including:
   - `booking_id`
   - `tenant_id`
   - `source`
   - `reservation_ref`
   - `property_id`

6. Canonical Supabase handling for `BOOKING_CANCELED` requires `booking_id`.

7. The currently active skill routing maps `BOOKING_CREATED` to `core.skills.booking_created_noop.skill`.

8. The currently active noop skill does not emit the canonical business event payload expected by the Supabase apply contract.

## Current Working Interpretation

The evidence does NOT currently justify the claim that canonical Supabase business dedup is intrinsically insufficient.

The evidence DOES justify the following narrower claim:

The current strongest verified gap is likely runtime mapping and routing misalignment between the active OTA path and the canonical emitted business event contract enforced by Supabase.

This means the active discovery focus is now:

- not only whether business-duplicate OTA events can exist beyond transport idempotency
- but whether the active OTA runtime path actually reaches the canonical business handling path in the shape the canonical database gate expects

## Required Questions To Answer

Phase 33 should answer these questions with evidence:

1. Can the same OTA business fact arrive with a different envelope or request identifier while still representing the same booking lifecycle change?

2. Which fields currently define OTA business identity in practice at the adapter boundary?

3. Does the active OTA runtime path currently emit the canonical business event payload shape required by `apply_envelope`?

4. Does the current system already prevent those duplicates safely through existing canonical identity constraints once canonical emitted business events reach Supabase?

5. If a real active gap exists, what is the smallest future-safe hardening shape:
- routing correction
- emitted event mapping alignment
- stronger constraint
- explicit business dedup layer
- or no change yet

## Completion Conditions

Phase 33 is complete when:

- the active OTA idempotency boundary is described precisely
- the difference between transport idempotency and canonical business identity enforcement is verified with evidence
- the emitted event routing and mapping path to `apply_envelope` is described precisely
- any real active verification gap is demonstrated concretely rather than assumed
- the next hardening direction is defined minimally and without violating canonical invariants
- no canonical semantic decision is reopened

## Current Expected Exit Shape

Based on current evidence, the most likely Phase 33 exit is one of these:

### Exit A
The active OTA runtime path is shown to emit canonical business events in the required shape, and no real active gap remains.

### Exit B
The active OTA runtime path is shown to remain misaligned with the canonical emitted business event contract, and the phase closes with a minimal future hardening target focused on routing and mapping alignment rather than broad architectural redesign.

## Follow-up Note For Future Hardening

Phase 33 does not prove an intrinsic failure of canonical Supabase business dedup.

The strongest current evidence indicates a likely alignment gap between the active OTA runtime path and the canonical emitted business event contract enforced by `apply_envelope`.

A future hardening phase should verify and align OTA skill routing and emitted event mapping so that OTA-originated `BOOKING_CREATED` and `BOOKING_CANCELED` reach the canonical Supabase apply path in the required business shape.

This follow-up does not authorize reconciliation logic, amendment handling, adapter-side booking_state reads, direct OTA calls to `apply_envelope`, or alternative write paths.
