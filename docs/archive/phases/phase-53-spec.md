# Phase 53 Spec — Expedia Adapter Full Implementation

## Objective

Complete the Expedia OTA adapter from scaffold to full implementation,
including BOOKING_CREATED, BOOKING_CANCELED, and BOOKING_AMENDED support.

## Status

In Progress

## Background

Phase 27 introduced Expedia as an architectural scaffold adapter to validate
multi-provider extensibility. Since then:
- Booking.com gained full BOOKING_AMENDED support (Phases 49–51)
- AmendmentFields schema exists in schemas.py
- extract_amendment_expedia() already implemented in amendment_extractor.py (Phase 49)
- The registry and pipeline are provider-agnostic

Expedia needs:
1. normalize() — currently assumed as scaffold; needs real field mapping
2. to_canonical_envelope() — currently missing BOOKING_AMENDED branch
3. Contract tests — currently no Expedia-specific contract tests

## Scope

### In scope

1. `src/adapters/ota/expedia.py` — read fully before touching
   - normalize(): align to real Expedia webhook field names
   - to_canonical_envelope(): add BOOKING_AMENDED branch (mirrors bookingcom pattern)

2. `tests/test_expedia_contract.py`
   - normalize + classify + envelope shape for CREATE / CANCEL / BOOKING_AMENDED
   - Regression: Booking.com tests still pass

### Out of scope

- Live Expedia webhook testing (no real Expedia account)
- Expedia auth / HMAC signature verification
- Any canonical code changes (apply_envelope, event_log, booking_state)

## Invariants — must not change

- apply_envelope remains single write authority
- No canonical event schema changes
- no adapter reads booking_state

## Expected outcome

Expedia adapter mirrors Booking.com capability.
All 3 event kinds production-ready through the same pipeline.
