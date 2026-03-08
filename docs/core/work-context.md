# iHouse Core — Work Context

## Current Active Phase

Phase 45 — Ordering Buffer Auto-Trigger on BOOKING_CREATED

## Last Closed Phase

Phase 44 — OTA Ordering Buffer

## Current Objective

Connect the ordering buffer to the ingestion pipeline. After a successful BOOKING_CREATED, automatically check the ordering buffer for any events that were waiting for this booking_id, replay them through dlq_replay.py, and mark them replayed.

This closes the ordering loop started in Phase 44.

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

## Phase 45 Scope

1. `src/adapters/ota/ordering_trigger.py`:
   - `trigger_ordered_replay(booking_id, client=None) → dict`
   - Reads waiting buffer rows for booking_id
   - For each: calls `replay_dlq_row(dlq_row_id)` → marks replayed
   - Returns `{replayed: int, skipped: int, results: list}`
   - Best-effort: single row replay failure logs and continues

2. Integration into `service.py`:
   - In `ingest_provider_event_with_dlq`, after a successful BOOKING_CREATED APPLIED result:
   - Call `trigger_ordered_replay(booking_id)` non-blocking, best-effort

3. Contract tests:
   - No buffered events → empty result, no replay called
   - One buffered event → replay called, mark_replayed called
   - replay failure → logged, not raised (remaining rows still processed)
   - booking_id extracted correctly from BOOKING_CREATED envelope

Out of scope:
- Amendment replay ordering (future)
- Expiry of buffer rows (future)
