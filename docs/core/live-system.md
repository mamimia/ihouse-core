# iHouse Core – Live System

## Phase
Phase 16 – Canonical Domain Event Migration

---

## Runtime Modes

DB_ADAPTER must be set to:

supabase

SQLite is not allowed in production runtime.

Startup must fail if DB_ADAPTER != supabase in production.

---

## Canonical Flow

External Input
→ Canonical Domain Event
→ Domain Dispatcher
→ Internal Handlers
→ EventLogPort (Supabase)
→ StateStorePort
→ Deterministic Commit

---

## HTTP API

POST /events

Accepts canonical domain events only.

Event types must match canonical registry.

Unknown types cause immediate rejection.

---

## Disabled Surfaces

No execution-primitive-based event types.
No direct skill invocation.
No alternate runtime paths.

FastAPI is the only execution entrypoint.

---

## Persistence

Supabase public.event_log
Supabase public.booking_state

Single source of truth.

---

## Replay

Rebuild derives state exclusively from Supabase public.event_log.

State hash validation required for deterministic proof.

---

## Invariants

Event order strictly preserved.
Idempotency enforced.
Single commit point.
No hidden state writes.

---

## Operational Rule

Code, event registry, and documentation must remain synchronized.

Drift is considered architectural violation.
