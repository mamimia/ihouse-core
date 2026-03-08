# iHouse Core — Work Context

## Current Active Phase

Phase 40 — DLQ Observability

## Last Closed Phase

Phase 39 — DLQ Controlled Replay

## Current Objective

Make the Dead Letter Queue visible and operational. Operators currently have no way to know how many events are in the DLQ, what types of rejections are happening, or which rows have been replayed. This phase adds a read-only inspection layer.

This phase is a read-only observability phase.

It must not add new write paths.
It must not read booking_state.
It must not modify canonical event behaviour.

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

## DLQ State After Phase 38-39

ota_dead_letter columns:
- id, received_at, provider, event_type, rejection_code, rejection_msg
- envelope_json, emitted_json, trace_id
- replayed_at, replay_result, replay_trace_id

## Phase 40 Scope

1. Supabase SQL view `ota_dlq_summary` — rejection counts grouped by event_type and rejection_code
2. Python read-only utility `src/adapters/ota/dlq_inspector.py`:
   - `get_pending_count()` → int: rows where replay_result IS NULL or not in APPLIED set
   - `get_replayed_count()` → int: rows where replay_result in APPLIED set
   - `get_rejection_breakdown()` → list[dict]: grouped by event_type + rejection_code
3. Contract tests (unit, mocked — no live Supabase required)

Out of scope:
- alerting thresholds (Phase 41)
- automatic retry
- any write to ota_dead_letter beyond what already exists
