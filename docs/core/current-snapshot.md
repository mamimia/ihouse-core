# iHouse Core — Current Snapshot

## Current Phase
Phase 100 -- Owner Statement Foundation (closed)

## Last Closed Phase
Phase 100 -- Owner Statement Foundation

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
| 81 | Tenant Isolation Audit -- tenant_isolation_checker.py, TenantIsolationReport, audit_tenant_isolation(), 24 tests; financial_router 404/500 standardised | ✅ |
| 82 | Admin Query API -- GET /admin/metrics, /admin/dlq, /admin/health/providers, /admin/bookings/{id}/timeline; 35 tests | ✅ |
| 83 | Vrbo Adapter -- vrbo.py, VrboAdapter, extract_amendment_vrbo, _extract_vrbo, schema_normalizer+registry+financial_extractor+amendment_extractor updated; 43 tests | ✅ |
| 84 | Reservation Timeline -- reservation_timeline.py, TimelineEvent, ReservationTimeline, build_reservation_timeline(); 45 tests | ✅ |
| 85 | Google Vacation Rentals Adapter -- gvr.py, GVRAdapter, _extract_gvr, extract_amendment_gvr; architecture diff documented; 50 tests | ✅ |
| 86 | Conflict Detection Layer -- conflict_detector.py, ConflictKind, ConflictSeverity, Conflict, ConflictReport, detect_conflicts(); 58 tests | ✅ |
| 87 | Tenant Isolation Hardening -- tenant_isolation_enforcer.py, TABLE_REGISTRY, TableIsolationPolicy, check_cross_tenant_leak, audit_system_isolation; 54 tests | ✅ |
| 88 | Traveloka Adapter (SE Asia Tier 1.5) -- traveloka.py, _extract_traveloka, extract_amendment_traveloka, _strip_traveloka_prefix; 6 files changed; 53 tests | ✅ |
| 89 | OTA Reconciliation Discovery -- reconciliation_model.py, ReconciliationFindingKind (7), ReconciliationSeverity (3), ReconciliationFinding, ReconciliationReport, ReconciliationSummary; 87 tests | ✅ |
| 90 | External Integration Test Harness -- test_e2e_integration_harness.py, 8 providers full pipeline coverage (CREATE/CANCEL/AMENDED), Groups A-H, 276 tests | ✅ |
| 91 | OTA Replay Fixture Contract -- tests/fixtures/ota_replay/ (16 YAML fixtures, 8 providers×2), test_ota_replay_fixture_contract.py, Groups A-E, 273 tests | ✅ |
| 92 | Roadmap + System Audit -- roadmap.md rewritten (Phase 21-91 full table), system-audit.md created (module inventory, boundary conditions, architecture integrity, gap analysis) | ✅ |
| 93 | Payment Lifecycle / Revenue State Projection -- payment_lifecycle.py, PaymentLifecycleStatus (7 states), PaymentLifecycleState, PaymentLifecycleExplanation, project_payment_lifecycle(), explain_payment_lifecycle(), 6-rule priority engine; 118 tests | ✅ |
| 94 | MakeMyTrip Adapter (Tier 2 India) -- makemytrip.py, MMT- prefix stripping, financial extractor (order_value/mmt_commission/net_amount), amendment extractor (amendment block), semantics aliases (booking_confirmed/cancelled/modified), gap fix in semantics.py; 66 tests | ✅ |
| 95 | MakeMyTrip Replay Fixture Contract -- tests/fixtures/ota_replay/makemytrip.yaml (CREATE+CANCEL), EXPECTED_PROVIDERS expanded to 9, fixture count invariant updated 16→18; +34 tests (total replay: 307) | ✅ |
| 96 | Klook Adapter (Tier 2 Asia activities) -- klook.py, KL- prefix stripping, travel_date/end_date/participants canonical mapping, financial extractor (booking_amount/klook_commission/net_payout), amendment extractor (modification block), 60 tests | ✅ |
| 97 | Klook Replay Fixture Contract -- tests/fixtures/ota_replay/klook.yaml (CREATE+CANCEL), EXPECTED_PROVIDERS expanded to 10, fixture count invariant updated 18→20; +34 tests (total replay: 341) | ✅ |
| 98 | Despegar Adapter (Tier 2 Latin America) -- despegar.py, DSP- prefix stripping, passenger_count/total_fare/despegar_fee canonical mapping, financial extractor (ARS/BRL/MXN multi-currency), amendment extractor (modification block), payload_validator.py extended for reservation_code; 61 tests | ✅ |
| 99 | Despegar Replay Fixture Contract -- tests/fixtures/ota_replay/despegar.yaml (CREATE+CANCEL, ARS), EXPECTED_PROVIDERS expanded to 11, fixture count invariant updated 20→22 (test_e4 renamed); +34 tests (total replay: 375) | ✅ |
| 100 | Owner Statement Foundation -- owner_statement.py, StatementConfidenceLevel (VERIFIED/MIXED/INCOMPLETE), OwnerStatementEntry, OwnerStatementSummary, build_owner_statement(); multi-currency guard; canceled-exclusion rule; 60 tests | ✅ |

**2134 tests pass** (2 pre-existing SQLite skips, unrelated)

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

**Phase 101** *(See `docs/core/roadmap.md`)*

## Tests

**2134 passing** (2 pre-existing SQLite skips, unrelated)
