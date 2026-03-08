# iHouse Core — Work Context

## Current Active Phase

Phase 41 — DLQ Alerting Threshold

## Last Closed Phase

Phase 40 — DLQ Observability

## Current Objective

Add a configurable threshold check on the DLQ pending count. When the number of unresolved DLQ rows exceeds a configured limit, emit a structured warning log. This gives operators an early signal before problems compound.

This phase is a read-only alerting layer. No new write paths. No new Supabase tables.

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

## Phase 41 Scope

1. `src/adapters/ota/dlq_alerting.py`:
   - `check_dlq_threshold(threshold: int, client=None) -> DLQAlertResult`
   - `DLQAlertResult`: dataclass with `pending_count`, `threshold`, `exceeded`, `message`
   - if `pending_count >= threshold` → `exceeded=True`, emit structured WARNING to stderr
   - configurable default threshold via env var `DLQ_ALERT_THRESHOLD` (default: 10)

2. Contract tests:
   - threshold not exceeded → exceeded=False, no warning
   - threshold exceeded → exceeded=True, warning emitted to stderr
   - threshold boundary (pending==threshold) → exceeded=True
   - default threshold from env var
   - zero pending → never exceeded

Out of scope:
- external alerting (webhook, email, Slack)
- automatic retry
- any writes
