# iHouse Core – Live System

## Phase
Current:
Phase 17 – Operational Hardening and Canonical Governance

Last closed:
Phase 16C – Hard Idempotency Gate

## Runtime Mode
Production runtime must use Supabase.
Any production configuration that allows SQLite writes is invalid.

## Canonical Flow
External request
→ IngestAPI
→ CoreExecutor
→ EventLogPort append_event (ingest envelope id)
→ apply_envelope RPC (atomic canonical apply)
→ StateStore commit only when APPLIED

## HTTP API
POST /events is the canonical ingest path.

Unknown event types are rejected.

## Idempotency
Hard idempotency enforced via apply_envelope.
Replay of same envelope_id must not mutate the canonical log.

## Replay and Rebuild
Replay and rebuild derive from Supabase event_log only.
