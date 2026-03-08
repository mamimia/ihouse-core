# iHouse Core — Work Context

## Current Active Phase

Phase 42 — Reservation Amendment Discovery

## Last Closed Phase

Phase 41 — DLQ Alerting Threshold

## Current Objective

Discovery phase — no implementation.

Investigate what it would take to safely introduce `BOOKING_AMENDED` as a canonical OTA event kind.

The current system rule is `MODIFY → deterministic reject-by-default`.

This phase does not lift that rule.
This phase does not introduce any new event kinds.
This phase does not modify any database schema.
This phase does not modify any skill.

The output of this phase is a documented finding set: what we know, what gaps remain, and what must be true before implementation can begin.

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
- MODIFY remains deterministic reject-by-default (until this discovery proves otherwise)

## Phase 42 Discovery Questions

1. How do OTA providers (Booking.com, Expedia) represent amendment events?
2. Can amendment intent be classified deterministically at the adapter layer?
3. What does apply_envelope need to do differently for an amendment vs a creation?
4. What ordering guarantees are required before amendment is safe?
5. What state must exist in booking_state before an amendment can be applied?
6. What invariants could an amendment violate if applied out-of-order?
7. Is booking_id stable across amendment events from the same provider?

## Completion

Phase 42 is complete when all seven questions have documented findings in `phase-42-spec.md`.
