# iHouse Core — Work Context

## Current Active Phase

Phase 37 — External Event Ordering Protection Discovery

## Last Closed Phase

Phase 36 — Business Identity Canonicalization

## Current Objective

Verify and document what happens when OTA events arrive out of order, specifically when `BOOKING_CANCELED` arrives before `BOOKING_CREATED`. Identify the current system behavior and determine if additional ordering protection is required.

This phase is a discovery phase only.

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

## Phase 36 Closed Finding

[Claude]

Canonical booking_id rule confirmed: `booking_id = "{source}_{reservation_ref}"`

apply_envelope enforces business-level dedup in two layers: by booking_id and by composite (tenant_id, source, reservation_ref, property_id).

E2E verified: duplicate BOOKING_CREATED with different request_id returns ALREADY_EXISTS.

## Phase 37 Focus

Phase 37 investigates external event ordering protection.

The backlog item **External Event Ordering Protection** (priority: high) covers:
- delayed events
- missing events
- cancellation before creation (BOOKING_CANCELED arriving before BOOKING_CREATED)
- out-of-order arrival

Phase 37 must answer:
1. What does apply_envelope currently return when BOOKING_CANCELED arrives before BOOKING_CREATED?
2. Is there any buffering, retry, or ordering layer in the active runtime path?
3. Is the current behavior safe (deterministic reject), or is it an unhandled error condition?
4. What is the minimal safe response to this gap, if any is required?
