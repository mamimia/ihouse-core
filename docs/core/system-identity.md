# iHouse Core – System Identity

## Phase
Current:
Phase 17B – Canonical Governance Completion

Last closed:
Phase 17A – Operational Runner, Secrets, CI, and Smoke Hardening

## System Type
Deterministic Domain Event Execution Kernel.

Not skill driven as an external contract.
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

## Operational Governance
Canonical local runner:
scripts/run_api.sh

CI enforces:
no direct pytest usage
English-only repo content
canonical scripts exist
boot API then run HTTP smoke

Secrets:
IHOUSE_API_KEY provided via GitHub Actions secrets.
