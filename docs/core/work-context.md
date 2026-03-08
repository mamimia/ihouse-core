# iHouse Core — Work Context

## Current Active Phase

Phase 35 — OTA Canonical Emitted Event Alignment Implementation

## Last Closed Phase

Phase 34 — OTA Canonical Event Emission Alignment

## Current Objective

Implement the minimal routing and emitted-event mapping changes defined by Phase 34 so that OTA-originated `BOOKING_CREATED` and `BOOKING_CANCELED` reach `apply_envelope` through the canonical emitted business event contract expected by Supabase.

This phase is a minimal implementation phase only.

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

## Phase 34 Closed Finding

[Claude]

Phase 34 proved a routing and emitted-event alignment gap in the active OTA runtime path.

Phase 34 did not prove an intrinsic failure of canonical Supabase business dedup.

Phase 34 did not justify architecture redesign.

The following evidence was verified by executable inspection:

1. `BOOKING_CREATED` routes to `core.skills.booking_created_noop.skill` which emits zero business events.

2. `BOOKING_CANCELED` has no entry in `kind_registry.core.json` and raises `NO_ROUTE` at execution time.

3. The noop skill returns `events_to_emit=[]`, so `apply_envelope` receives an empty `p_emit` array and never activates its canonical `BOOKING_CREATED` business logic (business dedup, overlap check, booking_state write).

4. Even if routing were corrected, the OTA adapter canonical envelope payload shape does not match the canonical emitted business event payload shape required by `apply_envelope`. A payload transformation is required.

5. The minimal future alignment change is:
   - a new `booking_created` skill that transforms the OTA envelope payload into the canonical emitted event shape and emits `BOOKING_CREATED` with the required payload fields
   - a new `booking_canceled` skill that emits `BOOKING_CANCELED` with `booking_id`
   - registry updates to route `BOOKING_CREATED` and `BOOKING_CANCELED` to the new skills

## Phase 35 Scope

Implement only the minimal alignment defined by Phase 34:

- new skill: `booking_created`
- new skill: `booking_canceled`
- registry updates: `kind_registry.core.json` and `skill_exec_registry.core.json`
- verification tests

No reconciliation, no amendment handling, no adapter-side state reads, no alternative write paths, no new canonical event kinds.

## Immediate Working Rule

Do not redesign the architecture.

Do not reopen closed phases.

Do only the minimum implementation required to align the active OTA runtime path with the canonical emitted business event contract already enforced by Supabase.
