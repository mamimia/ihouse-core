# iHouse Core — Work Context

## Current Active Phase

Phase 43 — booking_state Status Verification

## Last Closed Phase

Phase 42 — Reservation Amendment Discovery

## Current Objective

Phase 42 identified a gap: "booking_state has no explicit status column." Investigation revealed the column already exists in the schema and is set by apply_envelope. What was actually missing is verification and exposure.

This phase:
1. Verifies that apply_envelope correctly sets status='active' on BOOKING_CREATED and status='canceled' on BOOKING_CANCELED (E2E)
2. Adds a Python read function `get_booking_status(booking_id)` to expose status for future amendment guards
3. Adds contract tests for the status read function
4. Updates future-improvements.md and the amendment prerequisites table

This phase is a verification + thin read layer phase. No schema changes.

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

## Phase 43 Scope

1. E2E verification: confirm apply_envelope sets status=active/canceled correctly
2. `src/adapters/ota/booking_status.py`: `get_booking_status(booking_id, client=None) → str | None`
3. Contract tests: returns correct status / returns None for unknown booking / read-only guard
4. Update amendment prerequisites in future-improvements.md

Out of scope:
- Writing to booking_state directly
- Reading booking_state inside the ingestion path (adapters must not read state)
- Implementing BOOKING_AMENDED
