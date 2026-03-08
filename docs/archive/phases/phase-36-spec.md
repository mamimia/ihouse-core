# Phase 36 — Business Identity Canonicalization

## Status

Active

This file defines the active phase after Phase 35 closed.

## Depends On

Phase 35 — OTA Canonical Emitted Event Alignment Implementation

Phase 36 begins after Phase 35 confirmed that OTA-originated booking lifecycle events reach `apply_envelope` through the canonical emitted business event contract.

## Objective

Verify and document that `booking_id` is constructed deterministically across every active runtime touchpoint, and confirm that `apply_envelope` provides sufficient business-level duplicate protection for OTA-originated booking lifecycle events.

This phase is a discovery and documentation phase.

It is not a redesign phase.
It is not a reconciliation phase.
It is not an amendment phase.

## Why Phase 36 Exists

Phase 35 introduced the `booking_id` construction rule: `"{source}_{reservation_ref}"`.

This rule is now active in `booking_created` and `booking_canceled` skills.

However:
- The rule was not formally documented as a canonical invariant before Phase 35
- It is not yet verified that `apply_envelope` enforces business-level dedup on `booking_id`
- It is not yet verified what happens when the same OTA business fact arrives with a different `request_id`

The backlog item **Business Idempotency Beyond Envelope Idempotency** (priority: high) and **Business Identity Enforcement** (priority: high) both point to this as the next required verification.

## In Scope

### 1. booking_id construction verification
- Inspect how `booking_id` is constructed in `booking_created` skill
- Inspect how `booking_id` is constructed in `booking_canceled` skill
- Verify both use the same deterministic rule
- Verify `apply_envelope` reads `booking_id` from emitted event payload correctly

### 2. Business dedup verification in Supabase
- Inspect `apply_envelope` SQL for `booking_id` uniqueness enforcement
- Verify what happens on a duplicate `BOOKING_CREATED` for the same `booking_id` with a different `request_id`
- Verify whether `booking_state` has a unique constraint on `booking_id`

### 3. Document canonical booking_id rule
- Formally document the `booking_id` construction rule as a canonical invariant
- Update relevant docs minimally

## Out of Scope

Phase 36 must NOT introduce:
- reconciliation logic
- amendment handling
- new canonical event kinds
- booking_state reads inside adapters
- alternative write paths
- out-of-order buffering

## Required Questions To Answer

1. Is `booking_id = "{source}_{reservation_ref}"` the canonical rule used consistently everywhere?
2. Does `apply_envelope` enforce `booking_id` uniqueness at the business level?
3. What is the current behavior when the same `booking_id` is submitted twice with different envelope `request_id` values?
4. Is the current protection sufficient, or is additional hardening required?

## Completion Conditions

Phase 36 is complete when:
- The `booking_id` construction rule is verified consistent across skills and Supabase
- The current business dedup behavior is described precisely with evidence
- Any gap between envelope idempotency and business idempotency is described concretely
- The canonical `booking_id` rule is formally documented
