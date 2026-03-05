# iHouse Core — Current Snapshot

Current Phase: 20  
Last Closed Phase: 19

## Canonical Invariants

- event_log is the canonical ledger
- apply_envelope is the single write gate
- booking_state is a projection read model
- deterministic rebuild from event log is guaranteed

## Current Focus

Phase 20 — envelope validation hardening and safety.

## System Entry Points

Write Gate  
Supabase RPC: apply_envelope

Ledger  
public.event_log

Projection  
public.booking_state

## Notes

This file is intentionally short.  
Detailed architecture belongs in live-system.md.
