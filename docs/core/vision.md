# iHouse Core — Vision


## What iHouse Is
iHouse is a deterministic domain execution kernel.
External interface is business events only.

## Core Principle
State is derived.
Events are canonical.
Execution is internal.
Truth is replayable.

## Determinism
Given the same ordered canonical event log, the system produces identical state.

## Financial Grade Objective
No duplicate application of the same envelope.
No double execution that mutates canonical truth.
Hard idempotency is enforced at the Supabase boundary.

Database-level canonical mutation authority.
No application-layer truth fabrication.
Hard idempotency with zero duplicate state mutation.

## SaaS Direction
Make the kernel operationally safe and repeatable:
canonical runtime wiring
strict governance and CI enforcement
no hidden drift between code, DB, and docs

## Availability Canon (Phase 18)
Availability is enforced for (tenant_id, property_id).
Bookings use half-open ranges [check_in, check_out).
Active predicate is legacy tolerant:
status IS DISTINCT FROM 'canceled'
