# iHouse Core — Current Snapshot

## Current Phase
Phase 66 — booking_financial_facts Supabase Projection (closed)

## Last Closed Phase
Phase 66 — booking_financial_facts Supabase Projection

## System Status

**Full HTTP ingestion stack complete (Phases 58–64). Financial Data Foundation complete (Phase 65). Financial Supabase projection complete (Phase 66).**
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

**388 tests pass** (2 pre-existing SQLite skips, unrelated)

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
| `src/api/webhooks.py` | `POST /webhooks/{provider}` |
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

## Next Phase

**Phase 67 — TBD**
- See `docs/core/improvements/future-improvements.md` → Active Backlog

## Tests

**320 passing** (2 pre-existing SQLite skips, unrelated)
