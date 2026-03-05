# iHouse Core — System Identity

Current:
Phase 20 – Envelope Event Identity Hardening + Replay Safety (Open)

Last closed:
Phase 19 – Event Version Discipline + DB Gate Validation (Closed)

## System Type
Deterministic Domain Event Execution Kernel.

Not skill-driven as an external contract.
Skills are internal implementation.

## Event Authority
Only canonical business events are allowed externally.
Unknown event types are rejected.
User self-booking and manual bookings are external sources and must emit canonical business events through the same canonical path.

## Persistence Authority
Supabase is canonical:
public.event_log
public.booking_state

SQLite is not an allowed production write path.

## Financial Grade Guarantees
Hard idempotency at the canonical event store boundary
Atomic apply gate
Commit only after APPLIED
No commit during replay

State mutation authority resides exclusively in Supabase apply_envelope.
Application layer cannot fabricate internal state events.
Duplicate envelopes never mutate state.

## Availability Canon
Active predicate:
status IS DISTINCT FROM 'canceled'

Overlap scope:
tenant_id + property_id

Range semantics:
[check_in, check_out)
