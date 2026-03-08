# Phase 37 — External Event Ordering Protection Discovery

## Status

Active

## Depends On

Phase 36 — Business Identity Canonicalization

## Objective

Verify and document what the current system behavior is when OTA events arrive out of order, and determine whether the current behavior constitutes a safe deterministic rejection or an unhandled error condition.

This phase is a discovery phase only.

It is not a redesign phase.
It is not a reconciliation phase.
It is not an amendment phase.

## Why Phase 37 Exists

The backlog item **External Event Ordering Protection** (priority: high, discovered in Phase 21, Phase 27) covers:

- delayed events
- missing events
- cancellation before creation (BOOKING_CANCELED arriving before BOOKING_CREATED)
- out-of-order arrival scenarios

Phase 36 confirmed the happy path works correctly. Phase 37 investigates the unhappy path.

## Required Questions To Answer

1. What does `apply_envelope` currently return when `BOOKING_CANCELED` arrives before `BOOKING_CREATED`?
2. Does the current runtime path have any buffering, retry, or ordering layer between the OTA adapter and `apply_envelope`?
3. Is the current behavior: (a) safe deterministic rejection, (b) silent data loss, or (c) unhandled exception?
4. If a gap exists — what is the minimal safe response?

## In Scope

- E2E test of out-of-order arrival: BOOKING_CANCELED before BOOKING_CREATED
- Inspect active runtime path for any buffering or ordering layers
- Inspect apply_envelope SQL for BOOKING_NOT_FOUND behavior
- Document the finding precisely

## Out of Scope

- Implementing buffering or retry logic (not in this phase)
- Out-of-order event reordering
- Amendment handling
- Reconciliation
- New canonical event kinds

## Completion Conditions

Phase 37 is complete when:
- Current behavior on out-of-order arrival is verified with E2E evidence
- The behavior is classified as safe rejection or gap requiring future work
- Finding is documented in work-context and future-improvements if a gap is found
