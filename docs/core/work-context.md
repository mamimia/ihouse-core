# iHouse Core — Work Context

## Current Active Phase

Phase 39 — DLQ Controlled Replay

## Last Closed Phase

Phase 38 — Dead Letter Queue for Failed OTA Events

## Current Objective

Implement a safe, manually-triggered, idempotent replay mechanism that reads specific rows from `ota_dead_letter` and re-processes them through the canonical ingest pipeline — without bypassing `apply_envelope`.

This phase is an implementation phase.

It is not an automatic retry system.
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

## Phase 38 Closed Finding

[Claude]

`ota_dead_letter` table created. Rejected OTA events are now preserved.

DLQ write is best-effort, non-blocking, never bypasses apply_envelope.

E2E verified: BOOKING_CANCELED before BOOKING_CREATED → BOOKING_NOT_FOUND → DLQ row written.

DLQ rows are currently preserved but unactionable.

## Phase 39 Scope

### What this phase implements:

1. **Replay migration**: add `replayed_at`, `replay_result`, `replay_trace_id` columns to `ota_dead_letter`
2. **`replay_dlq_row(row_id)`**: Python function that reads one DLQ row, re-runs the skill, calls `apply_envelope`, and writes replay outcome back to the DLQ row
3. **Idempotency**: if a row has already been successfully replayed, re-running must be safe (idempotent)
4. **Contract tests**: verify replay behavior, idempotency, and outcome persistence

### What this phase does NOT implement:

- automatic retry scheduling
- bulk replay without operator control
- bypassing apply_envelope
- reading booking_state inside the adapter
- new canonical event kinds
