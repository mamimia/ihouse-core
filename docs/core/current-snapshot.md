# iHouse Core — Current Snapshot

## Phase

Current:
Phase 23 — External Event Semantics Hardening (Open)

Last closed:
Phase 22 — OTA Ingestion Boundary (Closed)

## Active Work Context
Phase 23 active.
See docs/core/phase-23-spec.md.

## System Type
Deterministic Domain Event Execution Kernel.

External contract is business events only.
Internal mechanics remain hidden.

## Canonical Persistence
Supabase is canonical:

public.event_log  
public.booking_state

SQLite is not an allowed production write path.

## Canonical Apply Gate

apply_envelope RPC is the single atomic write authority.

Properties:

- Writes envelope_received once per envelope_id
- Returns ALREADY_APPLIED on replay
- Guarantees deterministic idempotent behavior

booking_state is projection-only and must never be mutated directly by application code.

## External Ingestion Boundary (Phase 22)

External systems interact through an ingestion adapter layer.

Pipeline:

External System  
→ Adapter  
→ Normalization  
→ Validation  
→ Canonical Envelope  
→ apply_envelope RPC

External payloads never write directly to event_log.

Replay safety and deterministic event authority remain preserved.

## Availability Invariants

Scope:
tenant_id + property_id

Range:
[check_in, check_out)

Overlap rule:

existing.check_in < new.check_out AND new.check_in < existing.check_out

Active predicate:

status IS DISTINCT FROM 'canceled'

## Business Identity

tenant_id + source + reservation_ref + property_id