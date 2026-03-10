# iHouse Core — Current Snapshot

## Current Phase
Phase 153 — Operations Dashboard UI (closed)

## Last Closed Phase
Phase 153 — Operations Dashboard UI: `GET /operations/today` (arrivals/departures/cleanings); Next.js 14 `ihouse-ui/` scaffolded; dashboard page with Urgent, Today, Sync Health, Integration Alerts sections; 30 contract tests (Groups A-I)

## System Status

**Full HTTP ingestion stack (58–64). Financial Layer (65–67). booking_id Stability (68). BOOKING_AMENDED live (69). Booking Query API (71). Tenant Dashboard (72). Financial Aggregation (116). SLA Engine (117). Financial Dashboard (118). Reconciliation Inbox (119). Cashflow View (120). Owner Statement Generator (121). OTA Financial Health Comparison (122). Worker-Facing Task Surface (123). LINE Escalation Channel (124). Hotelbeds Adapter Tier 3 (125). Availability Projection (126). Integration Health Dashboard (127). Conflict Center (128). Booking Search (129). Properties Summary Dashboard (130). DLQ Inspector (131). Booking Audit Trail (132). OTA Ordering Buffer Inspector (133). Property-Channel Map Foundation (135). Provider Capability Registry (136). Outbound Sync Trigger (137). Outbound Executor (138). Real Outbound Adapters (139). iCal Date Injection (140). Rate-Limit Enforcement (141). Retry + Exponential Backoff (142). Idempotency Key (143). Outbound Sync Result Persistence (144). Outbound Sync Log Inspector (145). Sync Health Dashboard (146). Failed Sync Replay (147). Sync Result Webhook Callback (148). RFC 5545 VCALENDAR Compliance (149). iCal VTIMEZONE Support (150). iCal Cancellation Push (151). iCal Sync-on-Amendment Push (152). Operations Dashboard UI (153).**
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
| 101 | Owner Statement Query API -- owner_statement_router.py, GET /owner-statement/{property_id}?month=YYYY-MM, JWT auth, PROPERTY_NOT_FOUND/INVALID_MONTH error codes; error_models.py + main.py updated; 28 tests | ✅ |
| 102 | E2E Integration Harness Extension -- test_e2e_integration_harness.py expanded 8→11 (MakeMyTrip+Klook+Despegar payload factories); payload_validator.py +booking_id; harness: 375 tests | ✅ |
| 103 | Payment Lifecycle Query API -- payment_status_router.py, GET /payment-status/{booking_id}, JWT auth, BOOKING_NOT_FOUND 404, explain_payment_lifecycle (Phase 93), rule_applied + reason; main.py + tag; 24 tests | ✅ |
| 104 | Amendment History Query API -- amendments_router.py, GET /amendments/{booking_id}, booking_financial_facts WHERE event_kind='BOOKING_AMENDED', ordered ASC, 200+empty for known unamended booking, 404 for unknown; main.py + tag; 20 tests | ✅ |
| 105 | Admin Router Phase 82 Contract Tests -- test_admin_router_phase82_contract.py, 41 tests across Groups A-E covering /admin/metrics, /admin/dlq, /admin/health/providers, /admin/bookings/{id}/timeline; zero source changes | ✅ |
| 106 | Booking List Query API -- GET /bookings added to bookings_router.py; property_id/status/limit query params; 400 VALIDATION_ERROR on invalid status; limit clamped 1-100; test_booking_list_router_contract.py, 28 tests | ✅ |
| 107 | Roadmap Refresh -- roadmap.md resynced to Phase 106 actual state; completed-phases table extended 93–106; forward plan Phase 107–126 written covering API completeness → Reconciliation → Task System → Financial UI → Worker Communication | ✅ |
| 108 | Financial List Query API -- GET /financial added to financial_router.py; provider/month/limit filters; month validated by YYYY-MM regex (400 on bad format); limit clamped 1–100; test_financial_list_router_contract.py, 27 tests | ✅ |
| 109 | Booking Date Range Search -- GET /bookings extended with check_in_from + check_in_to (YYYY-MM-DD, gte/lte on check_in); ISO 8601 regex validation; 400 VALIDATION_ERROR on bad format; test_booking_date_range_contract.py, 36 tests | ✅ |
| 110 | OTA Reconciliation Implementation -- reconciliation_detector.py (FINANCIAL_FACTS_MISSING + STALE_BOOKING detectors); GET /admin/reconciliation endpoint in admin_router.py (include_findings param); test_reconciliation_detector_contract.py, 27 tests | ✅ |
| 111 | Task System Foundation -- src/tasks/task_model.py: TaskKind (5), TaskStatus (5), TaskPriority (4), WorkerRole (5) enums; mapping tables (urgency, ACK SLA minutes, default roles/priorities, valid transitions); Task dataclass with .build() factory; CRITICAL ACK SLA = 5 min locked; test_task_model_contract.py, 68 tests | ✅ |
| 112 | Task Automation from Booking Events -- task_automator.py: tasks_for_booking_created (CHECKIN_PREP+CLEANING), actions_for_booking_canceled (TaskCancelAction), actions_for_booking_amended (TaskRescheduleAction); pure functions, zero DB; test_task_automator_contract.py, 48 tests | ✅ |
| 113 | Task Query API -- task_router.py: GET /tasks (filters: property_id/status/kind/due_date/limit 1-100), GET /tasks/{task_id} (404 tenant-isolated), PATCH /tasks/{task_id}/status (VALID_TASK_TRANSITIONS enforced, 422 INVALID_TRANSITION); error_models.py +NOT_FOUND +INVALID_TRANSITION; main.py registered; 50 tests | ✅ |
| 114 | Task Persistence Layer -- Supabase `tasks` table DDL: 18 columns, 3 RLS policies (service_role all / authenticated read / authenticated update), 3 composite indexes (tenant+status, tenant+property_id, tenant+due_date); migration applied + E2E verified (INSERT/SELECT/UPDATE/DELETE); 0 new tests (infra phase) | ✅ |
| 115 | Task Writer -- task_writer.py: write_tasks_for_booking_created (upsert CHECKIN_PREP+CLEANING, idempotent), cancel_tasks_for_booking_canceled (PENDING→CANCELED), reschedule_tasks_for_booking_amended (due_date update); wired into service.py best-effort blocks after APPLIED for all 3 event types; test_task_writer_contract.py Groups A–E, 32 tests | ✅ |
| 116 | Financial Aggregation API -- financial_aggregation_router.py: GET /financial/summary, /by-provider, /by-property, /lifecycle-distribution; SUPPORTED_CURRENCIES frozenset (19 currencies); multi-currency grouping, dedup by booking_id; INVALID_PERIOD error code; 47 tests | ✅ |
| 117 | SLA Escalation Engine -- sla_engine.py: evaluate(payload) → EscalationResult; ACK_SLA_BREACH + COMPLETION_SLA_BREACH triggers; policy routing to notify_ops/notify_admin; terminal state guard; CRITICAL_ACK_SLA_MINUTES=5; 38 tests | ✅ |
| 118 | Financial Dashboard API -- financial_dashboard_router.py: GET /financial/status/{booking_id} (lifecycle card + epistemic tier + reason), GET /financial/revpar (total_net/available_room_nights per currency), GET /financial/lifecycle-by-property (distribution grouped by property); A/B/C tier helpers (_tier, _worst_tier); 44 tests | ✅ |
| 119 | Reconciliation Inbox API -- reconciliation_router.py: GET /admin/reconciliation?period=; 4 exception flags (RECONCILIATION_PENDING, PARTIAL_CONFIDENCE, MISSING_NET_TO_PROPERTY, UNKNOWN_LIFECYCLE); correction_hint per item; Tier C first sort order; empty inbox = clean financials; 32 tests | ✅ |
| 120 | Cashflow / Payout Timeline -- cashflow_router.py: GET /financial/cashflow?period=; expected_inflows_by_week (ISO week buckets), confirmed_released (PAYOUT_RELEASED only), overdue, forward_projection (30/60/90 days), totals per currency; OTA_COLLECTING explicitly excluded; _iso_week_key helper; 37 tests | ✅ |
| 121 | Owner Statement Generator (Ring 4) -- owner_statement_router.py: GET /owner-statement/{property_id}?month=&management_fee_pct=&format=pdf; per-booking line items (check_in/out, gross, ota_commission, net_to_property, epistemic_tier A/B/C, lifecycle_status); management fee deduction; owner_net_total; OTA_COLLECTING excluded from net; PDF plain-text export; property_id filter at DB level; dedup (most-recent recorded_at); 49 new tests + 28 updated Phase 101 tests | ✅ |
| 122 | OTA Financial Health Comparison -- ota_comparison_router.py: GET /financial/ota-comparison?period=; per-(OTA,currency) metrics: booking_count, gross_total, commission_total, net_total, avg_commission_rate, net_to_gross_ratio, revenue_share_pct, epistemic_tier (A/B/C), lifecycle_distribution; no cross-currency arithmetic; dedup by most-recent recorded_at; 44 tests | ✅ |
| 123 | Worker-Facing Task Surface -- worker_router.py: GET /worker/tasks (worker_role/status/date/limit filters, DB-level tenant isolation), PATCH /worker/tasks/{id}/acknowledge (PENDING→ACKNOWLEDGED), PATCH /worker/tasks/{id}/complete (IN_PROGRESS→COMPLETED); VALID_TASK_TRANSITIONS enforced; notes appended on complete; 41 tests | ✅ |
| 124 | LINE Escalation Channel -- channels/line_escalation.py: pure module: should_escalate (ACK_SLA_BREACH only), build_line_message, format_line_text, is_priority_eligible, LineEscalationRequest/LineDispatchResult dataclasses; api/line_webhook_router.py: POST /line/webhook: PENDING→ACKNOWLEDGED on LINE ack, idempotent for ACKNOWLEDGED, 409 for terminal; HMAC-SHA256 sig validation (dev=skip); 57 tests | ✅ |
| 125 | Hotelbeds Adapter (Tier 3 B2B Bedbank) -- hotelbeds.py: B2B semantics (property receives net_rate directly, markup_amount=Hotelbeds margin); voucher_ref normalization (HB- prefix strip); financial_extractor: FULL/ESTIMATED/PARTIAL confidence; amendment_extractor: amendment block (check_in/check_out/room_count guest_count fallback); registry registered; 42 tests | ✅ |
| 131 | DLQ Inspector -- dlq_router.py: GET /admin/dlq(source/status/limit filters; status derived pending/applied/error from replay_result; payload_preview 200chars; list excludes raw_payload) + GET /admin/dlq/{envelope_id}(full raw_payload); reads ota_dead_letter global; JWT required; 44 tests | ✅ |
| 139 | Real Outbound Adapters — AirbnbAdapter (api_first POST /v2/calendar_operations), BookingComAdapter (api_first), ExpediaVrboAdapter (api_first, shared API key), ICalPushAdapter (ical_fallback; Hotelbeds+TripAdvisor+Despegar); build_adapter_registry(); outbound_executor.py wired; dry_run on missing credentials / IHOUSE_DRY_RUN=true; 40 new contract tests | ✅ |
| 140 | iCal Date Injection — booking_dates.py (fetch_booking_dates, fail-safe); ICalPushAdapter.push() gains check_in/check_out; ICAL_TEMPLATE DTSTART/DTEND from real booking_state dates; executor + router wired; PRODID Phase 139→140; fallback constants 20260101/20260102; 16 contract tests | ✅ |
| 141 | Rate-Limit Enforcement — `_throttle(rate_limit)` in outbound `__init__.py`; wired into all 4 adapters before HTTP call; `IHOUSE_THROTTLE_DISABLED=true` opt-out; rate_limit≤0 logs WARNING + continues; 22 contract tests | ✅ |
| 142 | Retry + Exponential Backoff — `_retry_with_backoff(fn, max_retries=3)` in outbound `__init__.py`; backoff 4^attempt capped 30s (1s→4s→16s); retries on 5xx + network exceptions; no retry on 4xx; `IHOUSE_RETRY_DISABLED=true` opt-out; wired via `_do_req()` closure in all 4 adapters; 28 contract tests | ✅ |
| 143 | Idempotency Key — `_build_idempotency_key(booking_id, external_id)` in outbound `__init__.py`; format `{booking_id}:{external_id}:{YYYYMMDD}`; day-stable (UTC); attached as `X-Idempotency-Key` header in all 4 adapters; stable across retry attempts; `IHOUSE_THROTTLE_DISABLED`+`IHOUSE_RETRY_DISABLED` opt-outs; 23 contract tests | ✅ |
| 144 | Outbound Sync Result Persistence — `outbound_sync_log` table (DDL in `migrations/phase_144_outbound_sync_log.sql`); `src/services/sync_log_writer.py` (`write_sync_result()` best-effort append-only writer, client injection); `_persist()` helper in `outbound_executor.py` called after every ExecutionResult; skips not persisted; `IHOUSE_SYNC_LOG_DISABLED=true` opt-out; 13 contract tests | ✅ |
| 145 | Outbound Sync Log Inspector — `src/api/outbound_log_router.py` (NEW); `GET /admin/outbound-log` (filters: booking_id/provider/status/limit 1-200, default 50, newest-first) + `GET /admin/outbound-log/{booking_id}` (404 if no rows); tenant-scoped; registered in `main.py`; 30 contract tests | ✅ |
| 146 | Sync Health Dashboard — `GET /admin/outbound-health` added to `outbound_log_router.py`; `_compute_health()` in-memory aggregation of `outbound_sync_log` rows; per-provider: ok/failed/dry_run/skipped counts, last_sync_at, failure_rate_7d (7-day window, None if no ok+failed); alphabetical sort; malformed timestamps skipped; 33 contract tests | ✅ |
| 147 | Failed Sync Replay — `POST /admin/outbound-replay` in `outbound_log_router.py`; `_fetch_last_log_row()` helper + `execute_single_provider()` in `outbound_executor.py`; reconstructs SyncAction from log row; all Phase 141-144 guarantees apply; 400 on missing body fields; 404 when no prior log row; best-effort persistence; 33 contract tests | ✅ |
| 148 | Sync Result Webhook Callback — `_fire_callback(booking_id, tenant_id, result, *, callback_url)` in `outbound_executor.py`; reads `IHOUSE_SYNC_CALLBACK_URL`; fires only on `ok`; payload `{event:sync.ok, booking_id, tenant_id, provider, external_id, strategy, http_status}` via `urllib.request.urlopen`; 5s timeout; HTTP/connection/timeout errors swallowed; never retried; called in `execute_sync_plan()` after `_persist()`; 30 contract tests | ✅ |
| 153 | Operations Dashboard UI — `GET /operations/today` (arrivals/departures/cleanings, in-memory, `as_of` override); `ihouse-ui/` Next.js 14 App Router scaffolded; dashboard page: Urgent tasks, Today stats, Sync Health, Integration Alerts; typed `lib/api.ts` client; 30 contract tests (Groups A-I); UI build ✅ | ✅ |

**3993 tests pass** (2 pre-existing SQLite guard failures, unrelated)

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

**Phase 154** — API-first Cancellation Push (Airbnb, Booking.com, Expedia/VRBO `cancel()` adapters)

## Tests

**3993 passing** (2 pre-existing SQLite skips, unrelated)
