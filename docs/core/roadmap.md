# iHouse Core – Roadmap

> [!NOTE]
> This document is a living directional guide, not a binding contract.
> It is updated every few phases to reflect what we've learned and where we're headed.
> Last updated: Phase 180 checkpoint. Phases 176–179 closed. Forward plan Phase 181–190 written. [Antigravity]


## ✅ Completed Phases

| Phase | Title | Key Deliverable |
|-------|-------|----------------|
| 21 | External OTA ingestion boundary | Boundary defined |
| 22–33 | (See phase-timeline.md) | Adapter layer, validation, DLQ, replay |
| 34 | OTA canonical emitted event alignment discovery | Alignment mapping |
| 35 | Alignment implementation | BOOKING_CREATED, BOOKING_CANCELED skills |
| 36 | Business identity canonicalization | booking_id = {source}_{ref} locked |
| 37–49 | (See phase-timeline.md) | Ordering, DLQ, amendment groundwork |
| 50 | BOOKING_AMENDED | DDL, apply_envelope branch, E2E verified |
| 51–57 | (See phase-timeline.md) | Pipeline, service, ingest layers |
| 58 | POST /webhooks/{provider} | Signature verify + validate + ingest |
| 59 | FastAPI entrypoint | GET /health, uvicorn |
| 60 | Request logging middleware | X-Request-ID, duration_ms |
| 61 | JWT auth middleware | tenant_id from sub, 403 on failure |
| 62 | Per-tenant rate limiting | Sliding window, 429 + Retry-After |
| 63 | OpenAPI enrichment | BearerAuth, response schemas |
| 64 | Enhanced health check | Supabase ping, DLQ count, ok/degraded/unhealthy |
| 65 | Financial data extraction | BookingFinancialFacts, 5 providers, in-memory |
| 66 | Financial persistence | booking_financial_facts Supabase table |
| 67–76 | (See phase-timeline.md) | API error standards, OpenAPI, sig verification |
| 77 | OTA Schema Normalization | canonical_guest_count, canonical_booking_ref, canonical_property_id |
| 78 | Schema Normalization (Dates + Price) | canonical_check_in/out, canonical_currency, canonical_total_price |
| 79 | Idempotency Monitoring | idempotency_monitor.py |
| 80 | Structured Logging Layer | structured_logger.py, JSON output |
| 81 | Integration Health Dashboard | integration_health.py |
| 82 | Admin Query API | admin_router.py, /admin/* endpoints |
| 83 | Vrbo Adapter | VrboAdapter, unit_id mapping, alteration extraction |
| 84 | Reservation Timeline / Audit Trail | Per-booking event story API |
| 85 | Google Vacation Rentals Adapter | GVRAdapter, connected_ota field, GVR-specific financial |
| 86 | Conflict Detection Layer | conflict_detector.py, overlap detection, read-only |
| 87 | Tenant Isolation Hardening | tenant_isolation_enforcer.py, RLS audit, cross-tenant test |
| 88 | Traveloka Adapter | TravelokaAdapter, SE Asia Tier 1.5, TV- prefix stripping |
| 89 | OTA Reconciliation Discovery | reconciliation_model.py, 7 FindingKinds, 3 Severities, READ-ONLY |
| 90 | External Integration Test Harness | 8-provider E2E harness, Groups A-H, 276 tests |
| 91 | OTA Replay Fixture Contract | 16 YAML fixtures, fixture-driven determinism, 273 tests |
| 92 | Roadmap + System Audit | This document. system-audit.md. 1665 tests total. |
| 93 | Payment Lifecycle Projection | payment_lifecycle.py, 7 states, 6-rule priority engine, 118 tests |
| 94 | MakeMyTrip Adapter (India) | makemytrip.py, MMT- prefix, financial+amendment extractors, 66 tests |
| 95 | MakeMyTrip Replay Fixture | fixtures/ota_replay/makemytrip.yaml, 18 fixtures total, 307 replay tests |
| 96 | Klook Adapter (Asia activities) | klook.py, KL- prefix, travel_date/participants canonical mapping, 60 tests |
| 97 | Klook Replay Fixture | fixtures/ota_replay/klook.yaml, 20 fixtures total, 341 replay tests |
| 98 | Despegar Adapter (Latin America) | despegar.py, DSP- prefix, ARS/BRL/MXN multi-currency, 61 tests |
| 99 | Despegar Replay Fixture | fixtures/ota_replay/despegar.yaml, 22 fixtures total, 375 replay tests |
| 100 | Owner Statement Foundation | owner_statement.py, StatementConfidenceLevel, build_owner_statement(), 60 tests |
| 101 | Owner Statement Query API | owner_statement_router.py, GET /owner-statement/{property_id}?month=, 28 tests |
| 102 | E2E Harness Extension | harness expanded 8→11 providers (MakeMyTrip+Klook+Despegar), 375 harness tests |
| 103 | Payment Lifecycle Query API | payment_status_router.py, GET /payment-status/{booking_id}, 24 tests |
| 104 | Amendment History Query API | amendments_router.py, GET /amendments/{booking_id}, 20 tests |
| 105 | Admin Router Contract Tests | test_admin_router_phase82_contract.py, 41 tests, zero source changes |
| 106 | Booking List Query API | GET /bookings, property_id/status/limit filters, test_booking_list_router_contract.py, 28 tests |
| 107 | Roadmap Refresh | roadmap.md Phase 93–106 completion table, forward plan Phase 107–126 written |
| 108 | Financial List Query API | GET /financial?property_id=&month=, limit 1–100 clamped, 27 tests |
| 109 | Booking Date Range Search | GET /bookings extended with check_in_from + check_in_to, ISO 8601 validation, 36 tests |
| 110 | OTA Reconciliation Implementation | reconciliation_detector.py, FINANCIAL_FACTS_MISSING + STALE_BOOKING detectors, GET /admin/reconciliation, 27 tests |
| 111 | Task System Foundation | task_model.py: TaskKind (5), TaskStatus (5), TaskPriority (4), WorkerRole (5), CRITICAL_ACK_SLA=5min, 68 tests |
| 112 | Task Automation from Booking Events | task_automator.py: BOOKING_CREATED→CHECKIN_PREP+CLEANING, cancel, reschedule; 48 tests |
| 113 | Task Query API | task_router.py: GET /tasks + GET /tasks/{id} + PATCH status, VALID_TASK_TRANSITIONS, 50 tests |
| 114 | Task Persistence Layer | tasks table DDL, 3 RLS policies, 3 composite indexes, migration applied |
| 115 | Task Writer | task_writer.py: write/cancel/reschedule, upsert idempotent, wired into service.py, 32 tests |
| 116 | Financial Aggregation API | GET /financial/summary + /by-provider + /by-property + /lifecycle-distribution, 47 tests |
| 117 | SLA Escalation Engine | sla_engine.py: ACK_SLA_BREACH + COMPLETION_SLA_BREACH, EscalationResult, 38 tests |
| 118 | Financial Dashboard API | GET /financial/status/{id}, /revpar, /lifecycle-by-property; A/B/C tier; 44 tests |
| 119 | Reconciliation Inbox API | GET /admin/reconciliation, 4 flags, correction_hint, Tier C-first sort, 32 tests |
| 120 | Cashflow / Payout Timeline | GET /financial/cashflow, ISO week buckets, forward projection 30/60/90 days, 37 tests |
| 121 | Owner Statement Generator | GET /owner-statement/{property_id}?month=&management_fee_pct=&format=pdf, line items, 49 tests |
| 122 | OTA Financial Health Comparison | GET /financial/ota-comparison, net-to-gross ratio, revenue share, lifecycle dist., 44 tests |
| 123 | Worker-Facing Task Surface | worker_router.py: GET /worker/tasks + PATCH acknowledge/complete, role-scoped, 41 tests |
| 124 | LINE Escalation Channel | line_escalation.py, POST /line/webhook, HMAC-SHA256 sig, PENDING→ACKNOWLEDGED, 57 tests |
| 125 | Hotelbeds Adapter (Tier 3 B2B) | hotelbeds.py, B2B semantics, HB- prefix, FULL/ESTIMATED/PARTIAL confidence, 42 tests |
| 126 | Availability Projection | availability_projection.py, GET /availability/{property_id}?from=&to=, occupancy read model |
| 127 | Integration Health Dashboard | integration_health_router.py, GET /admin/integration-health, per-provider status |
| 128 | Conflict Center API | conflicts_router.py, GET /admin/conflicts, overlap + missing-mapping detection |
| 129 | Booking Search | bookings_router.py extended with full-text search + property filter |
| 130 | Properties Summary Dashboard | properties_summary_router.py, GET /admin/properties/summary |
| 131 | DLQ Inspector | dlq_router.py: GET /admin/dlq + GET /admin/dlq/{envelope_id}, status derived, 44 tests |
| 132 | Booking Audit Trail | booking_history_router.py, GET /bookings/{id}/history, chronological event list |
| 133 | OTA Ordering Buffer Inspector | buffer_router.py, GET /admin/buffer, per-provider buffered counts |
| 135 | Property-Channel Map Foundation | property_channel_map table, channel_map_router.py, GET/POST/DELETE mappings |
| 136 | Provider Capability Registry | provider_capability_registry table + GET /admin/registry/providers |
| 137 | Outbound Sync Trigger | build_sync_plan() — deterministic SyncAction list from channel map + registry |
| 138 | Outbound Executor | execute_sync_plan() — fail-isolated ExecutionResult per action, ExecutionReport |
| 139 | Real Outbound Adapters | AirbnbAdapter, BookingComAdapter, ExpediaVrboAdapter, ICalPushAdapter; dry-run on missing keys; 40 tests |
| 140 | iCal Date Injection | booking_dates.py, ICalPushAdapter.push(check_in/check_out), DTSTART/DTEND from real dates, 16 tests |
| 141 | Rate-Limit Enforcement | _throttle() in outbound __init__.py, IHOUSE_THROTTLE_DISABLED opt-out, 22 tests |
| 142 | Retry + Exponential Backoff | _retry_with_backoff(), 4^attempt backoff capped 30s, IHOUSE_RETRY_DISABLED opt-out, 28 tests |
| 143 | Idempotency Key | _build_idempotency_key(), format booking_id:external_id:YYYYMMDD, day-stable, 23 tests |
| 144 | Outbound Sync Result Persistence | outbound_sync_log table, sync_log_writer.py, _persist() in executor, 13 tests |
| 145 | Outbound Sync Log Inspector | GET /admin/outbound-log + /admin/outbound-log/{booking_id}, 30 tests |
| 146 | Sync Health Dashboard | GET /admin/outbound-health, per-provider: ok/failed counts, failure_rate_7d, 33 tests |
| 147 | Failed Sync Replay | POST /admin/outbound-replay, reconstructs SyncAction from log, all Phase 141-144 guarantees, 33 tests |
| 148 | Sync Result Webhook Callback | _fire_callback() on ok, IHOUSE_SYNC_CALLBACK_URL, 5s timeout swallowed, 30 tests |
| 149 | RFC 5545 VCALENDAR Compliance | CALSCALE, METHOD, DTSTAMP, SEQUENCE:0 in iCal payload |
| 150 | iCal VTIMEZONE Support | VTIMEZONE block + TZID-qualified DTSTART/DTEND, backward-compat UTC path |
| 151 | iCal Cancellation Push | ICalPushAdapter.cancel(), STATUS:CANCELLED, HMAC-safe dry-run path |
| 152 | iCal Sync-on-Amendment Push | iCal push on BOOKING_AMENDED |
| 153 | Operations Dashboard UI | GET /operations/today + Next.js dashboard page (arrivals, tasks, sync health, alerts), 30 tests |
| 154 | API-first Cancellation Push | AirbnbAdapter.cancel(), BookingComAdapter.cancel(), ExpediaVrboAdapter.cancel() |
| 155 | API-first Amendment Push | AirbnbAdapter.amend(), BookingComAdapter.amend(), ExpediaVrboAdapter.amend() |
| 156 | Property Metadata Table | properties table, GET/POST/PATCH/DELETE /properties |
| 157 | Worker Task UI | Next.js /tasks page — task list, task detail, acknowledge/complete |
| 158 | Booking View UI | Next.js /bookings page — list + filters + amendment history |
| 159 | Guest Profile Foundation | guest_profile table, GET/POST /guests |
| 160 | Guest Profile UI | Next.js guest profile view (linked from booking) |
| 161 | Financial Correction API | financial_correction_router.py, POST /financial/{id}/correct, audit trail |
| 162 | Financial Correction API | Closed prior |
| 163 | Financial Dashboard UI | Next.js /financial page — summary, cashflow, OTA comparison |
| 164 | Owner Statement UI | Next.js /financial/statements page |
| 165 | Properties Metadata API | GET /properties, POST /properties, properties table + RLS, migrations applied |
| 166 | Role-Based Scoping | Worker/owner/manager isolation enforced in routers, permission guards |
| 167 | Permissions Routing | PATCH /permissions/{user_id}/grant + revoke + GET list |
| 168 | Push Notification Foundation | notification_channels table, dispatch_notification() LINE>FCM>email, 27 tests |
| 169 | Admin Settings UI | PATCH /admin/registry/providers/{provider} + Next.js /admin page, 15 tests |
| 170 | Owner Portal UI | Next.js /owner page — portfolio, statement drawer, payout timeline |
| 171 | Admin Audit Log | admin_audit_log table, write_audit_event(), GET /admin/audit-log, 28 tests |
| 172 | Health Check Enrichment | OutboundSyncProbeResult, run_health_checks_enriched(), checks['outbound'], 20 tests |
| 173 | IPI — Proactive Availability Broadcasting | outbound_availability_broadcaster.py, POST /admin/broadcast/availability, audit debt closed, 35 tests |
| 174 | Outbound Sync Stress Harness | Groups I–O in E2E harness (send/cancel/amend/throttle/retry/idempotency/routing), 449 total harness tests |
| 175 | Platform Checkpoint | System audit, roadmap refresh, handoff document, docs update |
| 176 | Outbound Sync Auto-Trigger for BOOKING_CREATED | `outbound_created_sync.py`, `fire_created_sync()` wired into service.py, 26 tests |
| 177 | SLA→Dispatcher Bridge | `sla_dispatch_bridge.py`, `dispatch_escalations()`, tenant_permissions role resolution, 28 tests |
| 178 | Worker Mobile UI | `/worker` route, bottom nav, To Do/Active/Done, DetailSheet, acknowledge+complete |
| 179 | UI Auth Flow | `POST /auth/token`, `/login` page, Next.js Edge middleware, `api.login()`, 21 tests |
| 180 | Roadmap Refresh | roadmap.md updated 176–179, forward plan 181–190 written |


---

## 🎯 Active Direction — Phase 181+

Phases 176–179 closed the **integration wiring gap**: outbound sync auto-triggers, SLA→notification bridge, worker mobile UI, and end-to-end auth. The next wave focuses on **real-time data freshness, platform hardening, and market expansion**.

---

### Phase 181–184 — Real-Time + Reliability *(closed or in-progress)*

**Phase 181 — SSE Live Refresh** ✅ *Closed*  
`sse_broker.py`, `GET /events/stream`, `/worker` EventSource (fallback 60s). 20 tests.

**Phase 182 — Outbound Sync Auto-Trigger for BOOKING_CANCELED + BOOKING_AMENDED** ✅ *Closed*  
`outbound_canceled_sync.py` + `outbound_amended_sync.py` via `build_sync_plan → execute_sync_plan`. Additive (parallel) triggers in service.py. 28 tests.

**Phase 183 — Notification Delivery Status Tracking** ✅ *Closed*  
`notification_delivery_log` table, `write_delivery_log()`, wired into `sla_dispatch_bridge.py`. 25 tests.

**Phase 184 — Booking Conflict Auto-Resolution Engine**  
Extend `conflict_detector.py` with resolution proposals: hold_newer, hold_older, flag_for_ops. Write proposed resolution to `conflict_resolution_queue`. `/admin/conflicts` gains `POST /admin/conflicts/{pair_id}/resolve`. Zero writes to booking_state without operator approval.

---

> [!WARNING]
> **Confirmed Tech Debt — Phase 185**
>
> Phase 182 intentionally introduced a **parallel-trigger architecture** for BOOKING_CANCELED and BOOKING_AMENDED:
> - **Fast path** (Phases 151/152/154/155): `cancel_sync_trigger.py` + `amend_sync_trigger.py` call adapters directly — no rate-limit, no retry, no idempotency key, no sync log.
> - **Guaranteed path** (Phase 182): `outbound_canceled_sync.py` + `outbound_amended_sync.py` via `execute_sync_plan` — full Phase 141–144 guarantees.
>
> Both paths currently fire on every BOOKING_CANCELED and BOOKING_AMENDED event, which means **double adapter calls per provider**. This is idempotent in most OTAs but is not sustainable as a long-term design — silent path divergence is the main risk.
>
> **Phase 185 exists to close this tech debt intentionally and on record.**

---

### Phase 185 — Outbound Sync Trigger Consolidation *(Tech Debt)*

**Goal:** Remove the parallel fast-path triggers (`cancel_sync_trigger.py`, `amend_sync_trigger.py`) once `execute_sync_plan` is proven to fully cover the same behavior safely.

**Entry condition:** `execute_sync_plan` must be verified to handle:
- Direct `.cancel()` + `.amend()` API adapter calls (api_first providers)
- iCal push cancellation + amendment (ical_fallback providers)
- All Phase 141–144 guarantees active and tested under load

**Work:**
1. Audit `cancel_sync_trigger.py` and `amend_sync_trigger.py` line by line → confirm `execute_sync_plan` covers equivalent behavior
2. Add missing behaviors to `execute_sync_plan` if any gaps found
3. Remove `fire_amend_sync` and `fire_cancel_sync` calls from `service.py` (fast paths)
4. Delete `cancel_sync_trigger.py` and `amend_sync_trigger.py` (or archive to `deprecated/`)
5. Update `service.py` CANCELED + AMENDED blocks — single path only
6. Full regression run on the 400+ outbound harness tests (Phase 174)

**Risk:** Medium. The outbound stress harness (Phase 174, 449 tests) provides the safety net for this refactor.

---

### Phase 186–191 — Market + Product Depth

**Phase 186 — Logout + Session Management**  
`POST /auth/logout` (client-side token clear + cookie delete + redirect to `/login`). Token expiry detection in `apiFetch` — if 403, auto-logout. Required for production readiness.

**Phase 187 — Rakuten Travel Adapter (Japan Market)**  
Tier 3 adapter. Dominant Japanese OTA. Adds JP market coverage. Standard adapter pattern. RAK- prefix for booking_id.

**Phase 188 — PDF Owner Statements**  
`GET /owner-statement/{id}?format=pdf`. Lightweight PDF library (`reportlab` or `weasyprint`). PDF includes property name, month, line items, fee breakdown, owner net total. Owner Portal `/owner` gets download button.

**Phase 189 — Booking Mutation Audit Events**  
Every state-changing operation (acknowledge, complete, override, cancel, amend) emits a structured `AuditEvent` to `admin_audit_log`. Includes: actor, action, before/after state, timestamp. Closes the actor-level traceability gap.

**Phase 190 — Manager Dashboard UI**  
New `/manager` route: cross-property task overview, pending conflicts, unacknowledged CRITICAL tasks, outbound sync health summary. Manager can acknowledge on behalf, override conflicts, and download owner statements.

**Phase 191 — Platform Checkpoint II**  
Second platform audit. Update all docs. Evaluate: Hostelworld adapter, WhatsApp escalation channel, multi-property tenant onboarding, payment gateway webhook integration. Write forward plan Phase 192–200.

---

## Architectural Constraints — Permanently Locked

> [!IMPORTANT]
> These rules come from hard lessons learned in early phases and must never be violated.

| Rule | Phase Locked | Rationale |
|------|-------------|-----------|
| `apply_envelope` is the ONLY write authority to booking_state | Phase 35 | Prevents split-brain state corruption |
| `booking_id = {provider}_{normalized_ref}` | Phase 36 | Enables cross-provider reservation identity |
| `booking_state` must NEVER contain financial calculations | Phase 62+ | Financial data is provider-specific and must remain separate |
| `occurred_at` from OTA payload; `recorded_at` from server | Phase 76 | Provider time ≠ ingestion time — both preserved |
| Reconciliation layer is READ-ONLY | Phase 89 | Corrections go through canonical pipeline only |
| `payload_validator` recognizes: reservation_id, booking_ref, order_id | Phase 90 (discovered) | GVR/Traveloka require reservation_id duplication |
| `semantics.py` maps a fixed set of event_type strings | Phase 90 (discovered) | Adapter event_types must match the known set |


---

## Forward Planning — Worker Communication & Escalation Layer

> [!IMPORTANT]
> This is a planning direction, not an active phase. Full detail: `docs/core/planning/worker-communication-layer.md`

The system will eventually support **worker-facing operational communication** for: cleaner, check-in/check-out staff, operations manager, maintenance, garden/pool/repair.

### The Core Rule — Must Not Be Violated

**iHouse Core is the system of record, always.**

External channels (LINE → WhatsApp → Telegram → SMS) are fallback escalation surfaces only — never the source of truth.

### Schema Preservation Guidance

When working on the task system or SLA escalation engine, preserve space for:
- `urgency` field on tasks (low / medium / high / critical)
- `worker_role` on task assignments (role-aware routing)
- `ack_sla_minutes` per task (not global fixed timers)

Full detail: `docs/core/planning/worker-communication-layer.md`



## Completed

Phase 21 — External OTA ingestion boundary defined.
Phase 22–33 — (See phase-timeline.md for full history.)
Phase 34 — OTA canonical emitted event alignment discovery.
Phase 35 — Alignment implementation (BOOKING_CREATED, BOOKING_CANCELED skills).
Phase 36 — Business identity canonicalization (booking_id locked).
Phase 37–49 — (See phase-timeline.md for full history.)
Phase 50 — BOOKING_AMENDED: DDL, apply_envelope branch, E2E verified.
Phase 51–57 — (See phase-timeline.md for full history.)
Phase 58 — POST /webhooks/{provider}: signature verify + validate + ingest.
Phase 59 — FastAPI entrypoint, GET /health, uvicorn.
Phase 60 — Request logging middleware (X-Request-ID, duration_ms).
Phase 61 — JWT auth middleware (tenant_id from sub, 403 on failure).
Phase 62 — Per-tenant rate limiting (sliding window, 429 + Retry-After).
Phase 63 — OpenAPI enrichment (BearerAuth, response schemas).
Phase 64 — Enhanced health check (Supabase ping, DLQ count, ok/degraded/unhealthy).
Phase 65 — Financial data extraction (BookingFinancialFacts, 5 providers, in-memory).
Phase 66 — Financial persistence (booking_financial_facts Supabase table, financial_writer.py).
Phase 67–76 — (See phase-timeline.md for full history.)
Phase 77 — OTA Schema Normalization (canonical_guest_count, canonical_booking_ref, canonical_property_id, 27 tests).


---

## Forward Planning Context (Phase 78+)

Two major forward-planning notes are locked in `docs/core/improvements/future-improvements.md`:

1. **Product and Architecture Bundle** — visibility, auditability, reconciliation, financial clarity, owner surfaces, operational usefulness.
2. **Adapter Expansion Wave** — Vrbo → Google Vacation Rentals → Traveloka → MakeMyTrip → Despegar.

These are not immediate execution orders. They are direction notes that inform future phase decisions.


---

## Phase 78–107 Forward Plan

### Phase 78–82 — Infrastructure Hardening + Schema Completion

**Phase 78 — Schema Normalization (Dates + Price)**
Extend Phase 77: add `canonical_check_in`, `canonical_check_out`, `canonical_currency`, `canonical_total_price` for all 5 providers. Completes the canonical schema layer.

**Phase 79 — Idempotency Monitoring**
`idempotency_monitor.py`: metrics on duplicate envelope detection, retry storms, anomalies. Uses existing DLQ + ordering_buffer + event_log data.

**Phase 80 — Structured Logging Layer**
`structured_logger.py`: JSON output with `request_id`, `tenant_id`, `provider`, `duration_ms`, `result`. Replaces all stderr print statements. Foundation for future dashboards.

**Phase 81 — Integration Health Dashboard (Foundation)**
`integration_health.py`: per-provider last successful ingest, occurred_at vs recorded_at lag, DLQ counts, buffer counts, reject counts, stale alerts. Surfaces data the system already collects.

**Phase 82 — Admin Query API**
`src/api/admin_router.py` endpoints: `GET /admin/metrics`, `GET /admin/dlq`, `GET /admin/health/providers`, `GET /admin/bookings/{id}/timeline`. First queryable surface for operators.

---

### Phase 83–87 — Adapter Wave 1 + Visibility

**Phase 83 — Vrbo Adapter** *(Tier 1)*
First new adapter after the core set. Closes the largest vacation-rental credibility gap. Standard adapter pattern: normalize → validate → classify → to_canonical_envelope.

**Phase 84 — Reservation Timeline / Audit Trail**
Per-booking story API from existing event_log: created, amended, canceled, buffered, replayed, DLQ events, financial updates. Zero DB schema changes — only reads what already exists.

**Phase 85 — Google Vacation Rentals Adapter** *(Tier 1)*
Distribution surface rather than classic OTA. Critical for discoveryability. Adapter pattern may differ slightly — document the difference explicitly.

**Phase 86 — Conflict Detection Layer**
`conflict_detector.py`: overlap on same property, missing mapping, incomplete canonical coverage, potential overbooking, provider mapping gaps. Visibility only — no writes to booking_state.

**Phase 87 — Tenant Isolation Hardening**
RLS policy audit across all Supabase tables. Verify per-tenant isolation in event_log, booking_state, booking_financial_facts. Add contract tests for cross-tenant data leakage prevention.

---

### Phase 88–92 — Recovery + Southeast Asia + Test Infrastructure

**Phase 88 — Traveloka Adapter** *(Tier 1.5 — Southeast Asia)*
Dominant platform in Thailand and regional SE Asia context. Increases market fit for local operators.

**Phase 89 — OTA Reconciliation Discovery**
Discovery phase only. Map what comparison is possible between iHouse Core state and OTA state without a live API. Define the reconciliation model: what to detect, how to flag, what to correct.

**Phase 90 — External Integration Test Harness**
End-to-end deterministic harness for all current providers (5 core + Vrbo + GVR + Traveloka): webhook → signature → pipeline → Supabase state. Covers rejection, dedup, replay.

**Phase 91 — Replay Harness**
Historical OTA event stream deterministic replay against the canonical pipeline. For incident recovery and regression testing. Builds on DLQ replay infrastructure (Phase 39+).

**Phase 92 — Roadmap + System Audit**
Update all docs: `roadmap.md`, `future-improvements.md`, `current-snapshot.md`. Close gaps between code and documentation. Evaluate next 10-phase direction based on what's been learned.

---

### Phase 93–97 — Financial Layer + Latin America + India

**Phase 93 — Payment Lifecycle / Revenue State Projection**
`payment_lifecycle.py`: financial status states — `guest_paid`, `ota_collecting`, `payout_pending`, `payout_released`, `reconciliation_pending`, `owner_net_pending`. Builds on BookingFinancialFacts without touching booking_state.

**Phase 94 — MakeMyTrip Adapter** *(Tier 2 — India)*
Expands into the Indian travel market. Follows established adapter pattern.

**Phase 95 — Owner Statements Foundation**
`owner_statement.py`: per-property monthly summary, net revenue, payout summary. Read-only layer over financial_facts. First owner-facing surface.

**Phase 96 — Despegar Adapter** *(Tier 2 — Latin America)*
Strongest Latin American travel brand. Completes the Tier 2 adapter wave.

**Phase 97 — OTA Reconciliation Implementation**
Implement the reconciliation model defined in Phase 89. Detection and correction-support layer — never bypasses apply_envelope. Flags drift via admin API.

---

### Phase 98–107 — Product Layer (Operational Completeness)

**Phase 98 — Guest Pre-Arrival / Check-In Intake**
Lightweight intake flow per reservation: contact info, arrival time, agreement, special notes, readiness status.

**Phase 99 — Task Automation for Operations**
Rule-based task layer driven by booking events: BOOKING_CREATED → prep task, checkout tomorrow → cleaning task, amendment → reschedule, cancellation → cancel pending.

**Phase 100 — Owner Statements Full View**
Expand Phase 95 into a complete owner-facing surface: monthly statement, property revenue, net vs gross, payout history, scoped role visibility.

**Phase 101–107 — TBD based on product learning**
Candidates: Tier 3 adapters (Rakuten, Hotelbeds, Hostelworld), advanced financial reporting, outbound channel sync discovery, multi-projection read models, revenue analytics, advanced conflict resolution.


---

## Where We Land After Phase 107

**Adapter coverage:** Booking.com, Airbnb, Expedia, Agoda, Trip.com, Vrbo, Google Vacation Rentals, Traveloka, MakeMyTrip, Despegar. 10 channels. Global + SE Asia + India + LATAM coverage.

**Operational surfaces:** Reservation timeline, integration health dashboard, admin API, conflict detection, reconciliation layer.

**Financial surfaces:** Booking financial facts (persisted), payment lifecycle states, owner statements.

**Product surfaces:** Guest intake, task automation, owner views.

**Architecture:** Canonical core unchanged — `apply_envelope` still the only write authority. All product layers read from or wrap the canonical spine without mutating it.


## Completed

Phase 21 — External OTA ingestion boundary defined.
Phase 22 — OTA adapter layer introduced with normalization and validation.
Phase 23 — Semantic classification layer introduced for OTA events.
Phase 24 — OTA modification semantic recognition (MODIFY) with deterministic reject-by-default.
Phase 25 — OTA modification resolution rules closed.
Phase 26 — OTA payload contract verification across providers.
Phase 27 — Multi-OTA adapter architecture (shared pipeline, multi-provider registry, Booking.com + Expedia scaffold).
Phase 28–33 — (See phase-timeline.md for full history.)
Phase 34 — OTA canonical emitted event alignment discovery.
Phase 35 — OTA canonical emitted event alignment implementation (BOOKING_CREATED, BOOKING_CANCELED skills).
Phase 36 — Business identity canonicalization (booking_id = {source}_{reservation_ref} verified and locked).
Phase 37 — External event ordering protection discovery.
Phase 38 — Dead Letter Queue implemented (ota_dead_letter table, dead_letter.py).
Phase 39 — DLQ controlled replay (replay_dlq_row, idempotency, outcome persistence).
Phase 40–49 — (See phase-timeline.md for full history.)
Phase 50 — BOOKING_AMENDED event handling: DDL migration, apply_envelope branch, E2E verified.
Phase 51–57 — (See phase-timeline.md for full history.)
Phase 58 — POST /webhooks/{provider} endpoint: signature verify + validate + ingest.
Phase 59 — FastAPI app entrypoint (src/main.py), GET /health, uvicorn runner.
Phase 60 — Request logging middleware: X-Request-ID, duration_ms, structured logging.
Phase 61 — JWT auth middleware: verify_jwt, tenant_id from sub claim, 403 on failure.
Phase 62 — Per-tenant rate limiting: sliding window, IHOUSE_RATE_LIMIT_RPM, 429 + Retry-After.
Phase 63 — OpenAPI docs: BearerAuth scheme, response schemas, /docs + /redoc enriched.
Phase 64 — Enhanced health check: Supabase ping, DLQ count, ok/degraded/unhealthy (503).


---

## Upcoming — Near Term

These are concrete next-phase candidates based on current system state.


### Phase 65 — Financial Data Foundation

Goal:
Begin the financial layer without overloading booking_state.
See `docs/core/improvements/future-improvements.md` → Financial Model Foundation.

Proposed scope:
- Extract and preserve financial fields from all 5 OTA adapter payloads
  (total_price, currency, ota_commission, taxes, fees, net_to_property, etc.)
- Define `BookingFinancialFacts` dataclass — immutable, validated
- Add `source_confidence`: FULL / PARTIAL / ESTIMATED per provider
- No DB write yet — dataclass only in this phase

Constraints:
- booking_state must NEVER contain financial calculations (invariant locked Phase 62+)
- Financial data is provider-specific — no uniform field assumption
- Separate financial data may arrive via Finance APIs (not only webhooks)

---

## Medium Term

These are directions we expect to reach within 10-15 phases from now.


### Operational Observability Layer

Structured logging, ingestion metrics, and DLQ alerting across all OTA adapters.

Will cover:
- Rejection rates by provider and event type
- DLQ accumulation trends
- Replay success/failure rates


### OTA Ingestion Replay Harness

Deterministic replay tools to simulate historical OTA event streams against the canonical pipeline. Used for regression testing and incident recovery.


### External Integration Test Harness

End-to-end verification of OTA ingestion from the provider webhook boundary through to Supabase state, covering rejection scenarios, dedup, and replay safety.


### BOOKING_AMENDED Support (Future)

Full deterministic amendment support. Can only begin after:
- multiple OTA providers are live
- ordering buffer or DLQ retry exists
- out-of-order protections are proven in production
- amendment classification is deterministic

Until then: MODIFY → deterministic reject-by-default.


---

## Future OTA Evolution — Amendment Handling

MODIFY remains deterministic reject-by-default.

This section tracks the formal requirements for BOOKING_AMENDED.
See `improvements/future-improvements.md` for the detailed backlog entry.

Requirements before BOOKING_AMENDED can be introduced:

1. Deterministic amendment classification — adapters must distinguish safe amendments from ambiguous modifications
2. Reservation identity stability — booking_id must be stable across amendment events
3. State-safe amendment application — apply_envelope must safely transition previous_state → amended_state
4. Out-of-order protection — amendments must not corrupt state if events arrive late
5. Projection safety — event log must correctly rebuild amended reservations from history


---

## Forward Planning — Worker Communication & Escalation Layer

> [!IMPORTANT]
> This is a planning direction, not an active phase. It establishes architectural constraints
> that future phases must respect. Full detail in `docs/core/planning/worker-communication-layer.md`.

### Summary of Direction

The system will eventually support **worker-facing operational communication** for roles such as:
cleaner, check-in/check-out staff, operations manager, maintenance worker, garden/pool/repair worker.

Workers will have their own surfaces inside the system (dashboard, mobile view, assigned work, status, acknowledgement, completion, and history).

### The Core Rule — Must Not Be Violated

**iHouse Core is the system of record, always.**

| What lives in iHouse Core | External channels are |
|---|---|
| Task creation, status, acknowledgement, completion, escalation state, audit trail | Fallback / escalation delivery only — never the source of truth |

External channels (LINE → WhatsApp → Telegram → SMS) may only be added as fallback escalation surfaces, not as primary surfaces.

### Graded Escalation Model

Escalation behavior must be **intelligent**, not uniform:

| Urgency | Behavior |
|---|---|
| Low | In-app only, long SLA window |
| Medium | In-app first, external after delay if unacknowledged |
| High | In-app + fast external fallback |
| Critical | Manager escalation + SMS final fallback |

### What Future Schema Decisions Should Preserve Room For

When working on the task system or SLA escalation engine, preserve space for:

- `urgency` field on tasks (low / medium / high / critical)
- `worker_role` on task assignments (role-aware routing without schema migration later)
- `ack_sla_minutes` on tasks (per-task acknowledgement SLA, not global fixed timers)

Adding these fields at the right time costs almost nothing. Retrofitting them later costs significantly more.

### Architectural Guidance for Future Phases

When designing:
- **Task schema changes** → leave room for `urgency`, `worker_role`, `ack_sla_minutes`
- **Escalation engine** → design triggers to accept task-level context, not only fixed timers
- **Worker surfaces** → treat as first-class access points, not secondary admin views
- **Notification infrastructure** → architect as pluggable channels with in-app always first

Full detail: `docs/core/planning/worker-communication-layer.md`
---

## Platform Checkpoint II — Phase 197 (2026-03-10)

### Completed Phases Since Checkpoint I (Phase 175)

| Phase | Title | Type | Status |
|-------|-------|------|--------|
| 176 | Outbound Sync Auto-Trigger for BOOKING_CREATED | Backend | ✅ Closed |
| 177 | SLA→Dispatcher Bridge | Backend | ✅ Closed |
| 178–183 | Notification Delivery Writer + Channel Infra | Backend | ✅ Closed |
| 188 | PDF Owner Statements | Backend+UI | ✅ Closed |
| 189 | Booking Mutation Audit Events | Backend | ✅ Closed |
| 190 | Manager Activity Feed UI | UI | ✅ Closed |
| 191 | Multi-Currency Financial Overview | Backend+UI | ✅ Closed |
| 192 | Guest Profile Foundation | Backend | ✅ Closed |
| 193 | Guest Profile UI | UI | ✅ Closed |
| 194 | Booking→Guest Link | Backend+UI | ✅ Closed |
| 195 | Hostelworld Adapter | Adapter | ✅ Closed |
| 196 | WhatsApp Escalation Channel — Per-Worker Architecture | Backend | ✅ Closed |
| 197 | Platform Checkpoint II | Docs | ✅ Closed |

### System Numbers at Checkpoint II

- **14 OTA adapters** live (Airbnb, Booking.com, Expedia, Agoda, Trip.com, Vrbo, GVR, Traveloka, MakeMyTrip, Klook, Despegar, Rakuten, Hotelbeds, Hostelworld)
- **2 escalation channels** live (LINE + WhatsApp), per-worker preference model
- **CHANNEL_TELEGRAM + CHANNEL_SMS** stubs registered, ready to wire
- **4,906 tests** collected / ~4,900 passing / 6 pre-existing failures / exit 0

### Forward Plan — Directions for Phase 198+

> [!IMPORTANT]
> The next conversation must read the full system first, then propose 20 phases, then get user approval. See `releases/handoffs/handoff_to_new_chat Phase-197.md`.

The following are candidate areas — the next conversation evaluates and orders them:

**Channel & Escalation Completion**
- Telegram real adapter (Bot API, stub ready)
- SMS via Twilio (tier-3 final escalation)
- Per-worker channel preference UI (worker self-selects LINE/WhatsApp)
- Notification history inbox for workers

**Operator & Management Surfaces**
- Booking calendar view (UI for existing availability projection)
- OTA webhook DLQ replay from UI
- Pre-arrival guest task workflow

**Integration Management (Wave 1)**
- Credentials/secrets management UI
- Webhook provisioning UI
- Property-channel mapping UI
- Per-property sync status dashboard

**Platform Reliability**
- Fix 6 pre-existing test failures
- Rakuten replay fixture
- Hostelworld E2E harness extension
- RLS policy systematic audit

**Product Growth**
- Worker mobile foundation (PWA)
- Rate/pricing OTA push (outbound)
- Multi-property onboarding flow
