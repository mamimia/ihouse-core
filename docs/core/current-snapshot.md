# iHouse Core – Current Snapshot

## Phase
Phase 16 – Canonical Domain Event Migration

---

## System Type

Deterministic Domain Event Execution Kernel.

Business events only.
No execution-primitive events exposed.

---

## Canonical Event Types

BOOKING_CREATED
BOOKING_UPDATED
BOOKING_CANCELED
BOOKING_CHECKED_IN
BOOKING_CHECKED_OUT
BOOKING_SYNC_ERROR
AVAILABILITY_UPDATED
RATE_UPDATED

Event types must be SCREAMING_SNAKE_CASE.
No aliases allowed.
No lowercase allowed.

---

## Execution Flow

Canonical Domain Event
→ Domain Dispatcher
→ Internal Handlers
→ Deterministic Apply
→ Supabase Event Log
→ Supabase State Store

---

## Persistence

Supabase is the single source of truth.

SQLite not allowed in production.

---

## Determinism

Rebuild must derive identical state from:

Supabase public.event_log only.

State hash validation required for Phase 16 closure.

---

## Enforcement Status

Documentation updated.
Canonical contract defined.
Migration to domain event layer in progress.

Phase 16 not closed until:

- Startup registry validation implemented
- Runtime rejection verified
- Supabase hard enforcement implemented
- Deterministic rebuild hash validated
