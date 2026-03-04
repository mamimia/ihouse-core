# iHouse Core — Live System

## Phase
Current:
Phase 18 — Legacy-Tolerant Availability Canon + DB Invariants (Closed)

Last closed:
Phase 18 — Legacy-Tolerant Availability Canon + DB Invariants

## Runtime Mode
Production runtime must use Supabase.
Any production configuration that allows SQLite writes is invalid.

## Canonical Flow
External request
→ IngestAPI
→ CoreExecutor
→ apply_envelope RPC (atomic canonical apply)
→ event_log appended exactly once per envelope_id
→ booking_state materialized by DB-generated internal events
→ StateStore commit only when APPLIED

## HTTP API
POST /events is the canonical ingest path.
Unknown event types are rejected.

## Idempotency
Hard idempotency enforced via apply_envelope.
Replay of same envelope_id must not mutate the canonical log or booking_state.
apply_envelope returns ALREADY_APPLIED on duplicate envelope.

## Availability Contract
Scope:
tenant_id + property_id

Range:
[check_in, check_out)

Overlap predicate:
existing.check_in < new.check_out AND new.check_in < existing.check_out

Active predicate (Option B):
status IS DISTINCT FROM 'canceled'
