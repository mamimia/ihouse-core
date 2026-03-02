# iHouse Core – System Identity

## Phase
Current:
Phase 17 – Operational Hardening and Canonical Governance

Last closed:
Phase 16C – Hard Idempotency Gate

## System Type
Deterministic Domain Event Execution Kernel.

Not skill driven as an external contract.
Skills are internal implementation.

## Event Authority
Only canonical business events are allowed externally.
Unknown event types are rejected.

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
