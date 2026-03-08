# Phase 58 — HTTP Ingestion Layer

**Status:** Closed  
**Date:** 2026-03-08  
**Tests:** 286 passed, 2 skipped  
**Commit:** (see closure commit)

## Objective

Wire signature verification, payload validation, and OTA ingestion into a real FastAPI HTTP endpoint — the production webhook boundary.

## Endpoint

```
POST /webhooks/{provider}
```

## Flow

1. Read raw body bytes (before `json.loads`)
2. `verify_webhook_signature(provider, raw_body, header)` → 403
3. `json.loads(raw_body)` → dict
4. `validate_ota_payload(provider, payload)` → 400 with codes
5. `ingest_provider_event(provider, payload, tenant_id)` → 200 + idempotency_key
6. Unexpected exception → 500

## HTTP Status Codes (Locked)

| Code | Meaning |
|------|---------|
| 200 | `{"status": "ACCEPTED", "idempotency_key": "..."}` |
| 400 | `{"error": "PAYLOAD_VALIDATION_FAILED", "codes": [...]}` |
| 403 | `{"error": "SIGNATURE_VERIFICATION_FAILED", "detail": "..."}` |
| 500 | `{"error": "INTERNAL_ERROR"}` |

## Files Created

| File | Role |
|------|------|
| `src/api/__init__.py` | Package init |
| `src/api/webhooks.py` | FastAPI APIRouter |
| `tests/test_webhook_endpoint.py` | 16 contract tests (TestClient, CI-safe) |

## Key Decisions

- `tenant_id` sourced from `payload["tenant_id"]` — validated non-empty by payload_validator
- JWT auth deferred to a future phase (no code change needed in webhooks.py)
- `ingest_provider_event` is mocked in all tests (no live Supabase required)
- Unknown provider → 403 (ValueError from signature layer, not 404 to avoid probing)

## Test Coverage

| # | Scenario | Status |
|---|----------|--------|
| 1 | Dev mode, valid payload → 200 | ✅ |
| 2 | Correct signature → 200 | ✅ |
| 3 | Wrong signature → 403 | ✅ |
| 4 | Missing header when secret set → 403 | ✅ |
| 5 | Invalid payload → 400 + codes | ✅ |
| 6 | Non-JSON body → 400 | ✅ |
| 7 | Unknown provider → 403 | ✅ |
| 8 | ingest crash → 500 | ✅ |
| 9 | tenant_id propagated | ✅ |
| 10 | 200 body has correct idempotency_key | ✅ |
| 11 | 400 body has "codes" list | ✅ |
| 12-16 | All 5 providers → 200 (parametrized) | ✅ |
