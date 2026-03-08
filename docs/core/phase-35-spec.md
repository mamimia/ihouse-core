# Phase 35 — OTA Canonical Emitted Event Alignment Implementation

## Status

Active

This file defines the active phase after Phase 34 closed.

## Depends On

Phase 34 — OTA Canonical Event Emission Alignment

Phase 35 begins only after Phase 34 has verified the alignment gap and defined the minimal implementation change.

## Objective

Implement the minimal routing and emitted-event mapping changes defined by Phase 34 so that OTA-originated `BOOKING_CREATED` and `BOOKING_CANCELED` reach `apply_envelope` through the canonical emitted business event contract expected by Supabase.

This phase is a minimal implementation phase.

It is not a redesign phase.
It is not a reconciliation phase.
It is not an amendment phase.

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

## In Scope

Phase 35 includes only the following implementation work:

### 1. New Skill: `booking_created`
- Implement a skill that receives the OTA envelope payload.
- Transforms the OTA shape into the canonical emitted business event shape.
- Emits a `BOOKING_CREATED` event with: `booking_id`, `tenant_id`, `source`, `reservation_ref`, `property_id`, `check_in`, `check_out`.

### 2. New Skill: `booking_canceled`
- Implement a skill that emits a `BOOKING_CANCELED` event with: `booking_id`.

### 3. Registry Updates
- Update `kind_registry.core.json` to route `BOOKING_CREATED` and `BOOKING_CANCELED` to the new skills.
- Update `skill_exec_registry.core.json` to map the new skill names to their implementations.

### 4. Verification
- Add/update tests to verify that an OTA webhook now results in a canonical emitted event reaching the Supabase `apply_envelope` contract.

## Out of Scope

Phase 35 must NOT introduce:

- reconciliation logic
- amendment handling
- booking_state reads inside adapters
- direct apply_envelope calls from OTA code
- new canonical event kinds
- broad schema redesign

## Completion Conditions

Phase 35 is complete when:

- OTA-originated `BOOKING_CREATED` results in a canonical business event appearing in `p_emit` during `apply_envelope` call.
- OTA-originated `BOOKING_CANCELED` results in a canonical business event appearing in `p_emit` during `apply_envelope` call.
- All automated OTA contract tests pass.
- No canonical invariants are violated.
