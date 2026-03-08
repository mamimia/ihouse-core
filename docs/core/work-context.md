# iHouse Core — Work Context

## Current Active Phase

Phase 36 — Business Identity Canonicalization

## Last Closed Phase

Phase 35 — OTA Canonical Emitted Event Alignment Implementation

## Current Objective

Verify and document that `booking_id` is constructed deterministically and consistently across the entire active runtime path, and confirm that `apply_envelope` is protected against business-level duplicate bookings with the same identity.

This phase is a discovery and documentation phase.

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

## Phase 35 Closed Finding

[Claude]

Phase 35 resolved the Phase 34 alignment gap.

OTA-originated `BOOKING_CREATED` and `BOOKING_CANCELED` now reach `apply_envelope` through the canonical emitted business event contract.

E2E verified against live Supabase: both events returned `status: APPLIED`, `state_upsert_found: true`.

## Phase 36 Focus

Phase 36 investigates business identity canonicalization.

The active `booking_id` construction rule is: `"{source}_{reservation_ref}"`.

This rule was introduced in Phase 35 but was not formally documented as a canonical invariant.

Phase 36 must answer:

1. Is `booking_id` construction deterministic and consistent across every active touchpoint (skills, Supabase, tests)?
2. Does `apply_envelope` enforce uniqueness on `booking_id` at the business level (not just envelope idempotency)?
3. What happens if the same OTA business fact arrives with a different `request_id`?
4. Is the current protection sufficient, or is a stronger business-idempotency guard needed?
