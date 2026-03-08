# iHouse Core — Work Context

## Current Active Phase

Phase 38 — Dead Letter Queue for Failed OTA Events

## Last Closed Phase

Phase 37 — External Event Ordering Protection Discovery

## Current Objective

Design and implement a minimal Dead Letter Queue (DLQ) for OTA events that are rejected by `apply_envelope`, so that no OTA event is silently lost. Phase 37 proved that out-of-order events are currently lost. This phase introduces a safe, append-only preservation layer.

This phase is an implementation phase.

It is not a reconciliation phase.
It is not an amendment phase.
It must not introduce any new canonical write path.

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

## Phase 37 Closed Finding

[Claude]

BOOKING_CANCELED before BOOKING_CREATED → apply_envelope raises BOOKING_NOT_FOUND (P0001).

No buffering or retry layer exists. Rejected events are currently lost.

## Phase 38 Scope

Implement a minimal, safe DLQ that:

1. Captures any OTA event that is rejected by apply_envelope (BOOKING_NOT_FOUND or any other non-APPLIED status)
2. Stores the rejected envelope and the rejection reason in a Supabase table
3. Does NOT automatically retry or requeue
4. Does NOT bypass canonical apply gate
5. Is append-only and auditable

This is a preservation layer only. Manual replay from DLQ is a future phase.
