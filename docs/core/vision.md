# iHouse Core – Vision

## Version
Phase 17B – Canonical Governance Completion

Last closed:
Phase 17A – Operational Runner, Secrets, CI, and Smoke Hardening

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

## SaaS Direction
Make the kernel operationally safe and repeatable:
canonical runtime wiring
strict governance and CI enforcement
no hidden drift between code, DB, and docs
