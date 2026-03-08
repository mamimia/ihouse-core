# Phase 61 — JWT Auth Middleware

**Status:** Closed  
**Date:** 2026-03-08  
**Tests:** 307 passed, 2 skipped  

## Objective

Move `tenant_id` from OTA payload body into verified JWT Bearer token (sub claim).

## Files Changed

| File | Change |
|------|--------|
| `src/api/auth.py` | **NEW** — `verify_jwt` + `jwt_auth` Depends |
| `src/api/webhooks.py` | Added `tenant_id: str = Depends(jwt_auth)` to route |
| `src/adapters/ota/payload_validator.py` | Removed Rule 4 (TENANT_ID_REQUIRED) |
| `tests/test_auth.py` | **NEW** — 8 contract tests |
| `tests/test_payload_validator_contract.py` | Removed TENANT_ID_REQUIRED assertions |
| `tests/test_webhook_endpoint.py` | Test 9 updated for dev-mode tenant |

## Key Decisions

- `IHOUSE_JWT_SECRET` not set → dev-mode → `"dev-tenant"` (same pattern as signature_verifier)
- `TENANT_ID_REQUIRED` constant kept in payload_validator for backward compat (rule not enforced)
- HTTPBearer scheme, HMAC-HS256 algorithm, `sub` claim = `tenant_id`
- All 403s on: missing creds, malformed, wrong secret, expired, no sub, empty sub

## Test Coverage

| # | Scenario |
|---|----------|
| 1 | Valid JWT → tenant_id from sub |
| 2 | Missing creds + secret set → 403 |
| 3 | Malformed token → 403 |
| 4 | Wrong secret → 403 |
| 5 | Expired → 403 |
| 6 | Dev mode → "dev-tenant" |
| 7 | No sub claim → 403 |
| 8 | Empty sub → 403 |
