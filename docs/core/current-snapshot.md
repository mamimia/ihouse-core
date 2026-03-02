# iHouse Core – Current Snapshot

## Phase
Current:
Phase 16C – Hard Idempotency Gate

Last closed:
Phase 16B – Deterministic Core Alignment

---

## System Type

Deterministic Domain Event Execution Kernel.

Business events only.
No execution-primitive exposure.

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

---

## Execution Flow

Canonical Domain Event
→ Dispatcher
→ Internal Handler
→ Deterministic Apply
→ Supabase Event Log
→ Supabase State Store

---

## Persistence

Supabase public.event_log
Supabase public.booking_state

Single source of truth.

---

## Idempotency Status

Soft idempotency exists at execution level.

Phase 16C introduces:
Hard idempotency gate before any envelope write.

---

## Determinism

Rebuild derives state exclusively from Supabase public.event_log.

State hash validation required for deterministic guarantee.

