# iHouse Core – Vision

## Version
Phase 16 – Canonical Domain Event Migration

---

## What iHouse Is

iHouse is a deterministic domain execution kernel.

It is not a skill runner.
It is not an event-to-function router.
It is not an automation wrapper.

It is a domain state machine driven exclusively by canonical business events.

---

## Core Principle

All state transitions originate from canonical domain events.

Event types represent business reality only.

Internal execution mechanics are not exposed as event types.

---

## Canonical Direction

The system evolves from:

Execution-driven events

Into:

Domain-driven canonical events

Business events are the only allowed external contract.

All technical handlers operate internally and are never part of the public event surface.

---

## Determinism

Given the same ordered canonical event log,
the system must produce the same state.

Always.

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

## Final Direction

iHouse is a deterministic domain event engine.

State is derived.
Events are canonical.
Execution is internal.
Truth is replayable.
