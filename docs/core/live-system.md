# iHouse Core – Live System

## Phase
Current:
Phase 16C – Hard Idempotency Gate

Last closed:
Phase 16B – Deterministic Core Alignment

---

## Runtime Mode

DB_ADAPTER must be:

supabase

Startup fails if DB_ADAPTER != supabase in production.

---

## Canonical Flow

External Input
→ Canonical Domain Event
→ Dispatcher
→ Internal Handler
→ EventLogPort (Supabase)
→ StateStorePort
→ Deterministic Commit

---

## HTTP API

POST /events

Accepts canonical domain events only.

Unknown types cause immediate rejection.

---

## Idempotency Requirement

No duplicate envelope_id may be written.

Idempotency must be enforced before event_log mutation.

Phase 16C implements atomic write gate.

---

## Replay

Rebuild derives state exclusively from Supabase public.event_log.

