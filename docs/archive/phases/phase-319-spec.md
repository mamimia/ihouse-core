# Phase 319 — Real Webhook E2E Validation

**Status:** Closed
**Prerequisite:** Phase 318 (Frontend E2E Smoke Tests)
**Date Closed:** 2026-03-12

## Goal

Create vertical integration tests that exercise the FULL webhook ingestion pipeline — normalize + classify + to_canonical_envelope — with NO service-layer mocking.

## Files Changed

| File | Change |
|------|--------|
| `tests/test_webhook_vertical_e2e.py` | NEW — 33 parameterized tests |

## Test Coverage

| Group | Tests | Providers | What |
|-------|-------|-----------|------|
| A — Direct Pipeline | 21 | airbnb, bookingcom, agoda | ingest_provider_event → real normalize + classify + envelope |
| B — HTTP Vertical | 12 | airbnb, bookingcom, agoda | POST /webhooks/{provider} → real pipeline → 200 ACCEPTED |

## Key Difference from Phase 269

Phase 269 E2E tests mock `ingest_provider_event`.
Phase 319 tests exercise the REAL pipeline — no mocks on normalize/classify/envelope.

## Result

**33 tests. 33 passed. 0 failed. 0.83s. Exit 0.**
