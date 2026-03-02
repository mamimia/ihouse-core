# iHouse Core – Canonical Event Architecture

## Status
Authoritative – Phase 16B Closed

Last closed:
Phase 16B – Deterministic Execution Core Alignment

Next:
Phase 16C – Hard Idempotency Gate (Financial-Grade Enforcement)

---

## Purpose

Define the single allowed business event surface of the system.

This document replaces all previous execution-primitive-based event routing.

---

## Canonical Business Event Types (External)

BOOKING_CREATED
BOOKING_UPDATED
BOOKING_CANCELED
BOOKING_CHECKED_IN
BOOKING_CHECKED_OUT
BOOKING_SYNC_ERROR
AVAILABILITY_UPDATED
RATE_UPDATED

No additional external event types are allowed without registry update and startup validation.

---

## Internal Emitted Event Types (Not External Contract)

STATE_UPSERT

STATE_UPSERT exists for deterministic internal state commit.
It must never be accepted from the public API.

---

## Event Contract (External)

Each canonical external event must contain:

- event_id (string, UUID format)
- tenant_id
- occurred_at (ISO8601)
- source
- entity_id
- payload (object)

No technical orchestration fields allowed in external contract.

---

## Enforcement Rules

1. Unknown external event types are rejected at runtime.
2. Canonical registry validated at startup.
3. Every external event must map to an internal handler.
4. No handler may exist without canonical event mapping.
5. No aliasing allowed.
6. Event types must be SCREAMING_SNAKE_CASE.
7. STATE_UPSERT cannot be externally invoked.
8. Idempotency must be enforced before any state mutation.

---

## Supabase Authority

Supabase public.event_log is the single canonical event store.

All rebuild operations must originate exclusively from this table.

SQLite fallback is forbidden in production runtime.

---

## Determinism Requirement

Rebuild must produce identical state hash across runs.

Phase 16C will enforce financial-grade idempotency before write.

---

## Architectural Direction

Domain Events → Dispatcher → Internal Handlers → Deterministic Commit

Skills are internal mechanics.
Business events are the only external contract.
