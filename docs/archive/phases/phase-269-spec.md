# Phase 269 — E2E Webhook Ingestion Integration Test

**Status:** Closed
**Prerequisite:** Phase 268 (E2E Task System)
**Date Closed:** 2026-03-11

## Goal

Add HTTP-level E2E tests for the single webhook ingestion entry point `POST /webhooks/{provider}`.
CI-safe — no live DB, no staging, no SUPABASE_URL required.

## Flow Under Test

```
JWT (dev bypass) → sig verify (dev bypass) → JSON parse → payload_validator → ingest_provider_event (mocked)
```

## Files

| File | Change |
|------|--------|
| `tests/test_webhook_ingestion_e2e.py` | NEW — 25 tests, 5 groups |

## Test Groups

| Group | Tests | Description |
|-------|-------|-------------|
| A | 5 | Happy path — airbnb/bookingcom/agoda valid payloads → 200 ACCEPTED |
| B | 3 | Unknown provider → 403; sig secret set + missing header → 403 |
| C | 3 | Invalid JSON (empty, malformed, non-JSON) → 400 PAYLOAD_VALIDATION_FAILED |
| D | 4 | Payload validation: empty dict, missing fields, missing `occurred_at` → 400 |
| E | 5 | Response shape: Content-Type JSON, `idempotency_key` is string, `error` key on 4xx |

## Key Discovery

`payload_validator.py` requires an `occurred_at` ISO 8601 field in **all** provider payloads
(Rule 5 in the shared validator). This field must be present and parseable — otherwise 400.
Documented in this spec for future test authors.

## Result

**~6,132 tests pass, 13 skipped, 0 failures.**
