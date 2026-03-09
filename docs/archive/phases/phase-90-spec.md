# Phase 90 — External Integration Test Harness

**Status:** Closed
**Prerequisite:** Phase 89 (OTA Reconciliation Discovery)
**Date Closed:** 2026-03-09

## Goal

Build a deterministic, CI-safe end-to-end harness that exercises the full ingestion
pipeline for all 8 current OTA providers, from raw webhook payload through signature
verification, pipeline normalization, and canonical envelope production — without
requiring a live Supabase connection.

The harness verifies that every provider correctly produces:
- A valid canonical envelope for BOOKING_CREATED
- A valid canonical envelope for BOOKING_CANCELED
- A valid canonical envelope for BOOKING_AMENDED
- Proper idempotency key format
- Rejection of invalid payloads (400)
- Rejection of bad signatures (403 in prod mode)

This is a **Python-layer harness only** — it exercises the pipeline up to and including
`to_canonical_envelope()`, does not call `apply_envelope`, and does not require Supabase.

## Invariant (if applicable)

Pre-existing invariants preserved. No new invariants introduced.
The harness is test infrastructure only — no production code changes.

## Design / Files

| File | Change |
|------|--------|
| `tests/test_e2e_integration_harness.py` | NEW — full 8-provider harness, Groups A–H |

### Coverage

| Group | Scope |
|-------|-------|
| A | All 8 providers produce valid BOOKING_CREATED envelopes |
| B | All 8 providers produce valid BOOKING_CANCELED envelopes |
| C | All 8 providers produce valid BOOKING_AMENDED envelopes |
| D | booking_id format invariant: `{provider}_{normalized_ref}` across all 8 |
| E | idempotency_key format (non-empty string) for all 8 providers |
| F | Invalid payloads → PayloadValidationResult.valid=False for all 8 |
| G | Cross-provider isolation: same reservation_id → different booking_id per provider |
| H | Pipeline idempotency: running same payload twice produces same envelope |

## Result

**1172 tests pass, 2 skipped.**
No Supabase schema changes. No new migrations. No production code changes.
