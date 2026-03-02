# iHouse Core – Current Snapshot

## Phase
Current:
Phase 17 – Operational Hardening and Canonical Governance

Last closed:
Phase 16C – Hard Idempotency Gate

## System Type
Deterministic Domain Event Execution Kernel.

External contract is business events only.
Internal mechanics are hidden.

## Canonical Business Event Types
BOOKING_CREATED
BOOKING_UPDATED
BOOKING_CANCELED
BOOKING_CHECKED_IN
BOOKING_CHECKED_OUT
BOOKING_SYNC_ERROR
AVAILABILITY_UPDATED
RATE_UPDATED

## Execution Flow
Ingest envelope
→ CoreExecutor routes by canonical registry
→ skill executes deterministically
→ apply_envelope RPC performs atomic write into Supabase event_log
→ StateStore commit runs only when apply_status == APPLIED
→ replay_mode forbids commits

## Persistence
Supabase public.event_log is canonical event store.
Supabase public.booking_state is canonical state store.

SQLite is not allowed as a production write path.

## Idempotency
Hard idempotency is enforced at the database boundary:
apply_envelope returns ALREADY_APPLIED if envelope_received already exists for the envelope_id.
This prevents duplicate envelope application.

## Determinism
Rebuild and replay must derive truth from Supabase event_log only.
Given the same ordered event_log, state must be identical.

## Phase 17 Focus
Operational hardening and governance:
runtime wiring validation
schema and migration discipline
observability and audit queries
removal of remaining legacy paths and ambiguity
