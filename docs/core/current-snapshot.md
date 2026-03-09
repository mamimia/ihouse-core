# iHouse Core — Current Snapshot

## Current Phase
Phase 80 -- Structured Logging Layer (closed)

## Last Closed Phase
Phase 80 -- Structured Logging Layer

## System Status

**Full HTTP ingestion stack (58–64). Financial Layer (65–67). booking_id Stability (68). BOOKING_AMENDED live (69). Booking Query API (71). Tenant Dashboard (72).**
apply_envelope is the only authority for canonical state mutations.

## HTTP API Layer — Complete

| Phase | Feature | Status |
|-------|---------|--------|
| 58 | `POST /webhooks/{provider}` — sig verify + validate + ingest | ✅ |
| 59 | `src/main.py` — FastAPI entrypoint, `GET /health` | ✅ |
| 60 | Request logging middleware (`X-Request-ID`, duration, status) | ✅ |
| 61 | JWT auth — `tenant_id` from verified `sub` claim | ✅ |
| 62 | Per-tenant rate limiting (sliding window, 429 + `Retry-After`) | ✅ |
| 63 | OpenAPI docs — BearerAuth, response schemas, `/docs` + `/redoc` | ✅ |
| 64 | Enhanced health check — Supabase ping, DLQ count, 503 support | ✅ |
| 65 | Financial Data Foundation — BookingFinancialFacts, 5-provider extraction | ✅ |
| 66 | booking_financial_facts Supabase projection — write after BOOKING_CREATED APPLIED | ✅ |
| 67 | Financial Facts Query API — GET /financial/{booking_id}, JWT auth, tenant isolation | ✅ |
| 68 | booking_id Stability — normalize_reservation_ref, all 5 adapters, 30 contract tests | ✅ |
| 69 | BOOKING_AMENDED Python Pipeline — booking_amended skill, registry wiring, 20 contract tests | ✅ |
| 71 | Booking State Query API — GET /bookings/{booking_id}, JWT auth, tenant isolation, 16 tests | ✅ |
| 72 | Tenant Summary Dashboard — GET /admin/summary, 7 fields, DLQ pending, amendment count, 14 tests | ✅ |
| 73 | Ordering Buffer Auto-Route — BOOKING_NOT_FOUND → buffer auto-replay, 11 contract tests | ✅ |
| 74 | OTA Date Normalization — date_normalizer.py, all 5 providers, 22 contract tests | ✅ |
| 75 | Production Hardening — error_models.py, X-API-Version header, standard error body, 19 tests | ✅ |
| 76 | occurred_at vs recorded_at Separation — server ingestion timestamp, 12 contract tests | ✅ |
| 77 | OTA Schema Normalization — schema_normalizer.py, 3 canonical keys, all 5 providers, 27 contract tests | ✅ |
| 78 | OTA Schema Normalization (Dates + Price) -- 4 more canonical keys (check_in, check_out, currency, total_price), 26 tests | ✅ |
| 79 | Idempotency Monitoring -- idempotency_monitor.py, IdempotencyReport, collect_idempotency_report(), 35 tests | ✅ |
| 80 | Structured Logging Layer -- structured_logger.py, StructuredLogger, get_structured_logger(), 30 tests | ✅ |

**663 tests pass** (2 pre-existing SQLite skips, unrelated)

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

## Health Check Response

```json
{
  "status": "ok | degraded | unhealthy",
  "version": "0.1.0",
  "env": "production",
  "checks": {
    "supabase": {"status": "ok", "latency_ms": 12},
    "dlq": {"status": "ok", "unprocessed_count": 0}
  }
}
```

| Status | HTTP | Condition |
|--------|------|-----------|
| `ok` | 200 | Supabase up, DLQ empty |
| `degraded` | 200 | Supabase up, DLQ > 0 |
| `unhealthy` | 503 | Supabase unreachable |

## Key Files — API Layer

| File | Role |
|------|------|
| `src/api/webhooks.py` | POST /webhooks/{provider} — OTA ingestion |
| `src/api/financial_router.py` | GET /financial/{booking_id} — financial facts query (Phase 67) |
| `src/api/auth.py` | JWT verification |
| `src/api/rate_limiter.py` | Per-tenant rate limiting |
| `src/api/health.py` | Dependency health checks |
| `src/schemas/responses.py` | OpenAPI Pydantic response models |
| `src/main.py` | FastAPI app entrypoint |

## Financial Layer (Phase 65)

| File | Role |
|------|------|
| `src/adapters/ota/financial_extractor.py` | `BookingFinancialFacts` dataclass + per-provider extraction |
| `src/adapters/ota/financial_writer.py` | Best-effort writer to `booking_financial_facts` (Phase 66) |

### Provider Financial Fields

| Provider | Fields | Confidence |
|----------|--------|------------|
| Booking.com | `total_price`, `currency`, `commission`, `net` | FULL when all present |
| Expedia | `total_amount`, `currency`, `commission_percent` | ESTIMATED (derived net) |
| Airbnb | `payout_amount`, `booking_subtotal`, `taxes` | FULL when all present |
| Agoda | `selling_rate`, `net_rate`, `currency` | FULL when all present |
| Trip.com | `order_amount`, `channel_fee`, `currency` | ESTIMATED (derived net) |

**Invariant (locked Phase 62+):** `booking_state` must NEVER contain financial data.

### booking_financial_facts Table (Phase 66)

| Column | Type | Notes |
|--------|------|-------|
| `id` | BIGSERIAL | PK |
| `booking_id` | TEXT | `{source}_{reservation_ref}` |
| `tenant_id` | TEXT | |
| `provider` | TEXT | |
| `total_price` | NUMERIC | |
| `currency` | CHAR(3) | |
| `ota_commission` | NUMERIC | |
| `taxes` | NUMERIC | |
| `fees` | NUMERIC | |
| `net_to_property` | NUMERIC | |
| `source_confidence` | TEXT | FULL/PARTIAL/ESTIMATED |
| `raw_financial_fields` | JSONB | Raw provider fields |
| `event_kind` | TEXT | BOOKING_CREATED / BOOKING_AMENDED |
| `recorded_at` | TIMESTAMPTZ | auto |

RLS: enabled. Indexed on `booking_id`, `tenant_id`.

## Financial Query API (Phase 67)

```
GET /financial/{booking_id}
  Authorization: Bearer <JWT>
  → 200 { booking_id, provider, total_price, currency, ota_commission, taxes, fees,
           net_to_property, source_confidence, event_kind, recorded_at }
  → 404 { "error": "BOOKING_NOT_FOUND" }
  → 403 if JWT missing/invalid
```

Tenant isolation: `.eq("tenant_id", tenant_id)` enforced at DB query level.

## Booking Identity Layer (Phase 68)

| File | Role |
|------|------|
| `src/adapters/ota/booking_identity.py` | `normalize_reservation_ref(provider, raw_ref)` + `build_booking_id(source, ref)` |

**Invariant (locked Phase 68):** `reservation_ref` is normalized (strip + lowercase + per-provider prefix stripping) before use in `booking_id`. Formula unchanged: `booking_id = {source}_{reservation_ref}`.

## Next Phase

**Phase 81 -- TBD**
- See `docs/core/improvements/future-improvements.md`

## Tests

**663 passing** (2 pre-existing SQLite skips, unrelated)
