# iHouse Core – Vision

## Version
Phase 17 – Operational Hardening and Canonical Governance

Last closed:
Phase 16C – Hard Idempotency Gate

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

## Phase 17 Direction
Turn the kernel into an operationally safe SaaS foundation:
tighten runtime composition and governance
remove ambiguity and remaining legacy surfaces
add operational observability and audit discipline
