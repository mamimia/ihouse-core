# iHouse Core — Current Snapshot

## Current Phase
Phase 62 — Per-Tenant Rate Limiting (closed)

## Last Closed Phase
Phase 62 — Per-Tenant Rate Limiting

## System Status

**Full HTTP ingestion stack: webhook → sig verify → JWT auth → rate limit → validate → pipeline → Supabase.**

apply_envelope is the only authority for canonical state mutations.

## HTTP API Layer (Phases 58–62) — Complete

| Phase | Feature | Status |
|-------|---------|--------|
| 58 | `POST /webhooks/{provider}` — sig verify + validate + ingest | ✅ |
| 59 | `src/main.py` — FastAPI entrypoint, `GET /health` | ✅ |
| 60 | Request logging middleware (`X-Request-ID`, duration, status) | ✅ |
| 61 | JWT auth — `tenant_id` from verified `sub` claim | ✅ |
| 62 | Per-tenant rate limiting (sliding window, 429 + `Retry-After`) | ✅ |

**313 tests pass** (2 pre-existing SQLite skips, unrelated)

## Request Flow (POST /webhooks/{provider})

```
HTTP  →  Logging middleware (X-Request-ID)
      →  verify_webhook_signature        (403)
      →  JWT auth / verify_jwt           (403)
      →  Rate limit / InMemoryRateLimiter (429 + Retry-After)
      →  validate_ota_payload            (400)
      →  ingest_provider_event           (200 + idempotency_key)
      →  500 on unexpected error
```

## HTTP Status Codes (Locked)

| Code | Meaning |
|------|---------|
| 200 | `{"status": "ACCEPTED", "idempotency_key": "..."}` |
| 400 | `{"error": "PAYLOAD_VALIDATION_FAILED", "codes": [...]}` |
| 403 | `{"error": "SIGNATURE_VERIFICATION_FAILED"}` or JWT auth failure |
| 429 | `{"error": "RATE_LIMIT_EXCEEDED", "retry_after_seconds": N}` |
| 500 | `{"error": "INTERNAL_ERROR"}` |

## Key Files — API Layer

| File | Role |
|------|------|
| `src/api/__init__.py` | Package init |
| `src/api/webhooks.py` | FastAPI router — `POST /webhooks/{provider}` |
| `src/api/auth.py` | JWT verification (HMAC-HS256, `sub` → `tenant_id`) |
| `src/api/rate_limiter.py` | Per-tenant sliding window rate limiter |
| `src/main.py` | FastAPI app — `/health` + router |

## OTA Adapter Matrix

| Provider    | CREATE | CANCEL | AMENDED | Signature Header |
|-------------|:------:|:------:|:-------:|------------------|
| Booking.com | ✅ | ✅ | ✅ | `X-Booking-Signature` |
| Expedia     | ✅ | ✅ | ✅ | `X-Expedia-Signature` |
| Airbnb      | ✅ | ✅ | ✅ | `X-Airbnb-Signature` |
| Agoda       | ✅ | ✅ | ✅ | `X-Agoda-Signature` |
| Trip.com    | ✅ | ✅ | ✅ | `X-TripCom-Signature` |

## Tests

**313 passing** (2 pre-existing SQLite skips, unrelated)
