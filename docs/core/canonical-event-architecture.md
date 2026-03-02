# iHouse Core – Canonical Event Architecture

## Status
Authoritative – Phase 16

---

## Purpose

Define the single allowed business event surface of the system.

This document replaces all previous execution-primitive-based event routing.

---

## Canonical Business Event Types

BOOKING_CREATED
BOOKING_UPDATED
BOOKING_CANCELED
BOOKING_CHECKED_IN
BOOKING_CHECKED_OUT
BOOKING_SYNC_ERROR
AVAILABILITY_UPDATED
RATE_UPDATED

No additional event types are allowed without registry update and startup validation.

---

## Event Contract

Each canonical event must contain:

- event_id (UUID)
- tenant_id
- occurred_at (ISO8601)
- source
- entity_id
- payload (object)

No technical fields allowed in external contract.

---

## Enforcement Rules

1. Unknown event types are rejected at runtime.
2. Canonical registry is validated at startup.
3. Every event type must map to an internal handler.
4. No handler may exist without a canonical event type.
5. No reverse mapping allowed.
6. No aliasing allowed.
7. No lowercase or kebab-case event types allowed.

---

## Supabase Authority

Supabase public.event_log is the single canonical event store.

All rebuild operations must originate exclusively from this table.

SQLite fallback is forbidden in production runtime.

---

## Determinism Requirement

Rebuild must produce identical state hash across runs.

Phase 16 is not closed without deterministic rebuild validation.

---

## Architectural Direction

Domain Events → Dispatcher → Internal Handlers → Deterministic Commit

Skills are internal mechanics.

Business events are the only external contract.
