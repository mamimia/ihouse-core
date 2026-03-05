# iHouse Core — Current Snapshot

## Phase
Current:
Phase 20 — Envelope Event Identity Hardening + Replay Safety (Closed)

Last closed:
Phase 20 — Envelope Event Identity Hardening + Replay Safety (Closed)

## Active Work Context
No active phase work session.
If starting a new phase, update docs/core/work-context.md.

## System Type
Deterministic Domain Event Execution Kernel.

External contract is business events only.
Internal mechanics are hidden.

## Canonical Persistence
Supabase is canonical:
public.event_log
public.booking_state

SQLite is not an allowed production write path.

## Canonical Apply Gate
apply_envelope RPC is the single atomic write authority into event_log.
It writes envelope_received once per envelope_id and returns ALREADY_APPLIED on replay.

booking_state is materialized by DB-generated internal events (STATE_UPSERT) and must never be mutated by application code.

## Availability Invariants
Scope:
(tenant_id, property_id)

Range:
[check_in, check_out)

Overlap:
existing.check_in < new.check_out AND new.check_in < existing.check_out

Active predicate (legacy tolerant):
status IS DISTINCT FROM 'canceled'

## Business Identity
Stable business identity:
tenant_id + source + reservation_ref + property_id

## Phase 20 Verification Notes
Database inspection confirmed no redundant STATE_UPSERT mutations were detected by the causality gap check (0 rows returned).
Supabase stored function definitions were exported into artifacts/supabase/Functions.sql for canonical reference.
