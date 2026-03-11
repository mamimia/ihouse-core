# Phase 280 — Real Webhook Endpoint Validation

**Status:** Closed
**Prerequisite:** Phase 279 (CI Pipeline Hardening)
**Date Closed:** 2026-03-11

## Goal

Extend webhook endpoint test coverage to close critical gaps: JWT+HMAC interplay, JWT rejection paths, body tampering, and error body schema contracts.

## Changes

### `tests/test_webhook_validation_p280.py` — NEW (22 tests)

| Group | Tests | Coverage |
|-------|-------|----------|
| A — JWT Rejection | 6 | 503 (no secret, no dev mode), 403 expired/tampered/wrong-secret/no-sub JWT, 200 valid JWT+HMAC |
| B — Per-Provider HMAC | 5 | All 5 OTA providers with correct header name and real HMAC signature |
| C — Body Tampering | 4 | Tampered body after sig computed, empty body, sig prefix stripped, sig without prefix |
| E — Error Schema | 3 | 403 has `error` field, 400 has `codes` list, 200 has `status=ACCEPTED` + `idempotency_key` |

### `tests/test_webhook_endpoint.py` — Updated

- Added `autouse` `_dev_mode` fixture: sets `IHOUSE_DEV_MODE=true` for all 12 existing tests (these test signature/payload logic, not JWT auth)
- Fixed `test_9` (`test_tenant_id_propagated`): previously relied on absent secret = dev mode (Phase 61 behavior). Now explicitly sets `IHOUSE_DEV_MODE=true` (Phase 276 behavior)
- Added a comment to the fixture explaining the design intent

## Test Results

```
34 webhook tests passed (12 existing + 22 new Phase 280)
Full suite: exit 0
```

## Key Finding: HMAC Header Names

Verified from `signature_verifier.py` — the correct header names are:
| Provider | Header |
|----------|--------|
| bookingcom | `X-Booking-Signature` |
| airbnb | `X-Airbnb-Signature` |
| expedia | `X-Expedia-Signature` |
| agoda | `X-Agoda-Signature` |
| tripcom | `X-TripCom-Signature` |
