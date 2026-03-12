# iHouse Core – Roadmap

> [!NOTE]
> This document is a living directional guide, not a binding contract.
> Updated every checkpoint to reflect what has been learned and where the system is headed.
> Last updated: Phase 273 (2026-03-11). [Antigravity]


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
| `payload_validator` recognizes: reservation_id, booking_ref, order_id | Phase 90 | GVR/Traveloka require reservation_id duplication |
| `semantics.py` maps a fixed set of event_type strings | Phase 90 | Adapter event_types must match the known set |
| iHouse Core is the system of record, always | Phase 124 | External channels (LINE/WhatsApp/Telegram/SMS) are escalation surfaces only |
| Outbound sync is best-effort, never blocking | Phase 135 | Sync failures are swallowed — apply_envelope is never called from outbound paths |


---

## System Numbers — Phase 292 (2026-03-12)

| Metric | Value |
|--------|-------|
| **OTA Adapters** | 15 (14 unique + ctrip alias): Airbnb, Booking.com, Expedia, Agoda, Trip.com/Ctrip, Traveloka, Vrbo, GVR, MakeMyTrip, Klook, Despegar, Rakuten, Hotelbeds, Hostelworld |
| **Escalation Channels** | 5 live (LINE, WhatsApp, Telegram, SMS, Email) |
| **Task Kinds** | 6 (CLEANING, CHECKIN_PREP, CHECKOUT_VERIFY, MAINTENANCE, GENERAL, GUEST_WELCOME) |
| **API Routers** | 77 files in `src/api/` |
| **Financial Rings** | 6 complete (extraction → persistence → aggregation → reconciliation → cashflow → owner statement) |
| **AI Copilot Endpoints** | 8 (context aggregation, morning briefing, financial explainer, task recommendations, anomaly alerts, guest messaging, AI audit trail, worker copilot) |
| **Tests** | 6,216 collected / 6,216 passing / 0 failures / exit 0 |
| **Supabase Tables** | 33 tables + 1 view (`ota_dlq_summary`), 29 migrations |
| **E2E Test Files** | 6 files (booking, financial, task, webhook, admin, DLQ) — 159 tests added in Phases 265–271 |
| **Staging Infra** | docker-compose.staging.yml + 10 integration smoke tests |
| **Production Infra** | Dockerfile, docker-compose.production.yml, .env.production.example, deploy_checklist.sh (Phases 275-278, 286) |
| **CI Pipeline** | Python 3.14, blocking ruff lint, migrations validation, security gate (Phase 279) |
| **Brand** | External: **Domaniqo** (domaniqo.com) — internal codename remains iHouse Core |
| **Frontend** | Next.js 16 / React 19, 18 pages, Domaniqo branding, 60s auto-refresh, SSE live worker, OTA donut (ihouse-ui/) |

---

## ✅ Completed Phases (1–272)

### Foundation (Phases 21–64)
OTA ingestion boundary, adapter layer, DLQ, replay, canonical events (BOOKING_CREATED/CANCELED/AMENDED), service pipeline, FastAPI app, JWT auth, rate limiting, OpenAPI, health checks.

### Financial Layer (Phases 65–66, 93, 100–101, 108, 116, 118–122)
BookingFinancialFacts extraction + persistence, payment lifecycle (7 states), owner statements, financial aggregation APIs, cashflow projections, OTA financial health comparison.

### Schema + Monitoring (Phases 77–82)
Canonical schema normalization, idempotency monitoring, structured logging, integration health dashboard, admin query API.

### Adapters (Phases 83, 85, 88, 94, 96, 98, 125, 187, 195, 238)
Vrbo, GVR, Traveloka, MakeMyTrip, Klook, Despegar, Hotelbeds, Rakuten, Hostelworld — 14 unique adapters live. Phase 238 added Ctrip alias with enhanced Chinese market support.

### Test Infrastructure (Phases 84, 86–87, 89–92, 105, 174)
Audit trail, conflict detection, tenant isolation, reconciliation discovery, E2E harness (11 providers), replay fixtures, outbound stress harness (449 tests).

### Task System (Phases 111–115, 117, 123, 206)
Task model (5 kinds, 5 statuses, 4 priorities), automator, writer, query API, worker-facing API, SLA engine, pre-arrival guest workflow.

### Outbound Sync (Phases 135–155, 173, 176, 182, 209)
Property-channel map, provider capability registry, sync planner, executor, 4 outbound adapters, rate-limit, retry, idempotency, sync log, inspector, health dashboard, replay, webhook callback, iCal RFC 5545 compliance, VTIMEZONE, cancel/amend push, availability broadcasting, auto-triggers for all 3 event types. **Phase 209: dual-trigger tech debt closed** — single guaranteed path via `execute_sync_plan`.

### Channels + Notifications (Phases 124, 168, 177, 183, 196, 203)
LINE escalation, notification dispatch (LINE>FCM>email), SLA→dispatcher bridge, delivery status tracking, WhatsApp per-worker channel, Telegram channel.

### API + Product Surfaces (Phases 103–104, 106, 109–110, 126–133, 145–148, 156–169, 171–172)
Payment status, amendment history, booking list+search, reconciliation, conflict center, DLQ inspector, booking audit trail, buffer inspector, outbound log inspector, sync health, property metadata, guest profiles, permissions, admin audit log, health enrichment.

### UI (Phases 153, 157–158, 160, 163–164, 169–170, 178–179, 190, 193, 200–202, 205)
Operations dashboard, worker mobile, booking view, guest profile, financial dashboard, owner statement, admin settings, owner portal, auth flow, manager feed, booking calendar, channel preferences, notification inbox, DLQ replay UI.

### Platform Checkpoints (Phases 92, 107, 175, 180, 191, 197, 204, 208, 218, 228, 229, 239)
Roadmap refreshes, system audits, documentation sync, handoff documents.

### AI Assistive Layer (Phases 220–231)
CI/CD pipeline, scheduled job runner, AI context aggregation, Manager Copilot v1 (morning briefing), Financial Explainer, Task Recommendation Engine, Anomaly Alert Broadcaster, Guest Messaging Copilot v1, AI Audit Trail, Worker Task Copilot. All AI reads from or wraps the canonical spine — never mutates it.

### Recent — Phases 198–272
Test suite stabilization, Supabase RLS audit, conflict auto-resolution engine, outbound sync trigger consolidation (tech debt closure, Phase 209), documentation cleanup (Phase 210), production deployment foundation (Phase 211), SMS+Email channels (Phases 212-213), property onboarding wizard (Phase 214), revenue reports + portfolio dashboard + integration management (Phases 215-217), CI/CD pipeline (Phase 220), scheduled job runner (Phase 221), full AI copilot suite (Phases 222-227), AI audit trail + worker copilot (Phases 230-231), guest pre-arrival automation (Phase 232), revenue forecast engine (Phase 233), shift & availability scheduler (Phase 234), multi-property conflict dashboard (Phase 235), guest communication history (Phase 236), staging environment (Phase 237), Ctrip/Trip.com enhanced adapter (Phase 238). Platform Checkpoint VII (Phase 239). Documentation Integrity Sync (240). Reconciliation Dashboard API (241). Booking Lifecycle Visualization API (242). Property Performance Analytics API (243). OTA Revenue Mix Analytics API (244). Platform Checkpoint VIII (245). Rate Card & Pricing Rules Engine (246). Guest Feedback Collection API (247). Maintenance Task Templates (248). Booking.com Content Push Adapter (250). Dynamic Pricing Suggestion Engine (251). Owner Financial Report API v2 (252). Staff Performance Dashboard API (253). Platform Checkpoint X: Audit & Handoff (254). Bulk Operations (255). i18n + Language Switcher + Thai/Hebrew RTL UI (256–260). Webhook Event Logging (261). Guest Self-Service Portal (262). Production Monitoring (263). Advanced Analytics (264). Test Suite Repair + Doc Sync (265). **E2E Testing Sprint (266–271):** 159 new integration tests covering booking flow, financial summary, task system, webhook ingestion, admin/properties, DLQ/replay. Platform Checkpoint XII (272).

---

## Tech Debt — Closed

| Debt | Opened | Closed | Resolution |
|------|--------|--------|------------|
| Dual outbound sync triggers (fast-path + guaranteed-path) | Phase 182 | **Phase 209** | Deprecated `cancel_sync_trigger.py` + `amend_sync_trigger.py` deleted. Sole path: `fire_*_sync()` → `build_sync_plan` → `execute_sync_plan`. |

---

## Active Direction — Phase 285+

Phase 284 (Supabase Schema Truth Sync) aligned the live Supabase database with all documented migrations (33 tables + 1 view, 29 migrations). Phase 283 fixed all test isolation failures (conftest.py, rate limiter, env var leakage). 6,216 tests passing, exit 0.

The current wave (Phases 285–292) continues with **documentation sync**, **production Docker hardening**, and the **first real Domaniqo frontend** (Operations Dashboard, Booking Management, Worker Task View, Financial Dashboard).

Full plan: `docs/core/planning/next-10-phases-283-292.md`

### Phase 283 — Test Suite Isolation Fix + conftest.py *(closed)*
Created `tests/conftest.py` with session-scoped env var management. Fixed 4 root causes: IHOUSE_DEV_MODE leaking from module-level `os.environ.setdefault`, 7 test files missing dev mode fixtures, auth enforcement tests not disabling dev mode, InMemoryRateLimiter singleton (60 RPM) accumulating hits across full suite. 16 files modified. +0 tests, 0 failures.

### Phase 284 — Supabase Schema Truth Sync *(closed)*
Applied 5 missing migrations to live Supabase: `worker_availability` (Phase 234), `guest_messages_log` (Phase 236), `rate_cards` (Phase 246), `guest_feedback` (Phase 247), `task_templates` (Phase 248). Re-exported `artifacts/supabase/schema.sql` (34 objects). Updated `BOOTSTRAP.md`. Fixed `test_stale_property_sorted_first` datetime bug. 33 tables + 1 view, 29 migrations. 6,216 tests, 0 failures.

### Phase 210 — Roadmap & Documentation Cleanup *(closed)*
Full audit of 20 canonical documents. Archived 10 stale files. Fixed Layer A claims (BOOKING_AMENDED, MODIFY semantics). Created AI strategy canonical document (`docs/core/planning/ai-strategy.md`).

### Phase 211 — Production Deployment Foundation *(closed)*
Dockerfile (multi-stage), docker-compose.yml, .dockerignore, requirements.txt. Added `GET /readiness` Kubernetes-style probe. +6 tests → 5,033.


### Phase 212 — SMS Escalation Channel *(closed)*
`sms_escalation.py` pure module (mirrors WhatsApp/Telegram pattern), `sms_router.py` (GET challenge + POST inbound ACK via Twilio form fields), registered in `main.py`. `python-multipart` added to `requirements.txt`. +31 tests → 5,064.

### Phase 213 — Email Notification Channel *(closed)*
`email_escalation.py` pure module (mirrors SMS/WhatsApp/Telegram pattern), `email_router.py` (GET /email/webhook health + GET /email/ack one-click token ACK), registered in `main.py`. +35 tests → 5,099.

### Phase 214 — Property Onboarding Wizard API *(closed)*
`onboarding_router.py` — 4-endpoint stateless wizard: `POST /onboarding/start` (Step 1: property + active-bookings safety gate), `POST /{id}/channels` (Step 2: OTA channel mappings, upsert), `POST /{id}/workers` (Step 3: notification channels, upsert), `GET /{id}/status` (derived completion state). +20 tests → 5,119.

### Phase 215 — Automated Revenue Reports *(closed)*
`revenue_report_router.py` — `GET /revenue-report/portfolio` (cross-property, sorted by gross DESC) + `GET /revenue-report/{property_id}` (single-property monthly breakdown). `from_month`/`to_month` range, max 24 months, optional `management_fee_pct`. Reuses owner-statement dedup + tier + OTA_COLLECTING exclusion logic. +24 tests → 5,143.

### Phase 216 — Portfolio Dashboard UI *(closed)*
`portfolio_dashboard_router.py` — `GET /portfolio/dashboard`. Single endpoint aggregating occupancy (booking_state), revenue (booking_financial_facts, current month), pending tasks (tasks), and sync health (outbound_sync_log) per property. Property list derived from union of all four sources. Sorted by urgency: stale sync → pending tasks → active bookings. +21 tests → 5,164.

### Phase 217 — Integration Management UI *(closed)*
`integration_management_router.py` — `GET /admin/integrations` (cross-property OTA connection view, grouped by property, enriched with last sync status/stale flag, filtered by provider/enabled) + `GET /admin/integrations/summary` (tenant totals: enabled, disabled, stale, failed, provider distribution). In-memory join of `property_channel_map` + `outbound_sync_log`. +15 tests → 5,179.

### Phase 218 — Platform Checkpoint IV *(closed)*
Full system audit (Phases 210–217), documentation sync across all canonical docs (`current-snapshot.md`, `work-context.md`, `roadmap.md`), handoff to next AI session. 0 new code files.

### Phase 219 — Documentation Integrity Repair *(closed)*
Repaired missing phase-timeline + construction-log entries for Phases 211–218. Updated live-system.md with 11 missing endpoints. All canonical docs synced. 0 new code files.

### Phase 220 — CI/CD Pipeline Foundation *(closed)*
`.github/workflows/ci.yml` upgraded to 3-job pipeline: `test` (pip cache, e2e ignores), `lint` (ruff, non-blocking), `smoke` (secrets-guarded HTTP). 0 new source files.

### Phase 221 — Scheduled Job Runner *(closed)*
`AsyncIOScheduler` (APScheduler 3.x) wired into FastAPI lifespan. 3 jobs: SLA sweep (2min), DLQ threshold alert (10min), health log (15min). `GET /admin/scheduler-status` added. 32 contract tests.

### Phase 222 — AI Context Aggregation Endpoints *(closed)*
`GET /ai/context/property/{property_id}` + `GET /ai/context/operations-day`. Read-only composition layer, no new tables. 9 best-effort sub-query helpers. `ai_hints` flags for LLM conditional logic. PII-free. 32 contract tests.

### Phase 223 — Manager Copilot v1: Morning Briefing *(closed)*
`POST /ai/copilot/morning-briefing`. First LLM integration. OpenAI via `services.llm_client` (provider-agnostic). Heuristic static briefing fallback when unconfigured. 5-language support (en/th/ja/es/ko). `action_items` always deterministic. 21 contract tests.

### Phase 224 — Financial Explainer *(closed)*
`GET /ai/copilot/financial/explain/{booking_id}` + `GET /ai/copilot/financial/reconciliation-summary`. 7 deterministic anomaly flags. Confidence tier (A/B/C) explanation. LLM overlay + heuristic fallback. Source: `booking_financial_facts` only. 37 contract tests.

### Phase 225 — Task Recommendation Engine *(closed)*
`POST /ai/copilot/task-recommendations`. Deterministic scoring: CRITICAL=1000, HIGH=500, MEDIUM=200, LOW=50 + SLA breach +800 + recency +50. LLM JSON-array rationale overlay (5 tasks, per-task). 26 contract tests.

### Phase 226 — Anomaly Alert Broadcaster *(closed)*
`POST /ai/copilot/anomaly-alerts`. 3-domain scanner (tasks SLA breach + financial 7 flags + booking confidence). Severity: CRITICAL→HIGH→MEDIUM→LOW. Health score 0–100. LLM summary overlay. 26 contract tests.

### Phase 227 — Guest Messaging Copilot v1 *(closed)*
`POST /ai/copilot/guest-message-draft`. 6 intents. Context: booking_state + properties (access code, Wi-Fi, check-in/out times). 5-language salutation/closing. 3 tones. Email subject line. LLM prose overlay + template fallback. 26 contract tests.

### Phase 228 — Platform Checkpoint V *(closed)*
Full audit + doc sync. 8 discrepancies fixed across all canonical docs. Test count corrected 5,179→5,382. AI table realigned. Next 10 phases plan written. 0 new code files.

### Phase 229 — Platform Checkpoint VI *(closed)*
Verification audit. All docs confirmed. Phase plan shifted (229→checkpoint, old 229–238→230–239). Handoff written. 0 new code files.

### Phase 230 — AI Audit Trail *(closed)*
`ai_audit_log` Supabase table + `GET /ai/audit-log` endpoint. Records AI decisions: request context, suggestion, confidence, approval status. Append-only. 26 contract tests.

### Phase 231 — Worker Task Copilot *(closed)*
`POST /ai/copilot/worker-assist` — mobile contextual assists for field workers. Task-aware suggestions based on current assignment, property context, and historical patterns. LLM + heuristic fallback. 23 contract tests.

### Phase 232 — Guest Pre-Arrival Automation Chain *(closed)*
`pre_arrival_scanner.py` — chains pre-arrival task generation (Phase 206) with guest message drafting (Phase 227). Scheduled via job runner. `pre_arrival_queue` Supabase table. 28 contract tests.

### Phase 233 — Revenue Forecast Engine *(closed)*
`GET /revenue/forecast/{property_id}` — 30/60/90-day forward projection from booking pipeline + historical patterns. Heuristic confidence scoring. 22 contract tests.

### Phase 234 — Shift & Availability Scheduler *(closed)*
`worker_shifts` Supabase table + 3 endpoints (GET/POST/DELETE /worker/availability). Worker availability windows for task assignment optimization. 30 contract tests.

### Phase 235 — Multi-Property Conflict Dashboard *(closed)*
`GET /admin/conflicts/dashboard` — cross-property conflict aggregation with grouping, severity, age, and 30-day timeline. 20 contract tests.

### Phase 236 — Guest Communication History *(closed)*
`guest_messages_log` Supabase table + `POST/GET /guest-messages/{booking_id}`. Persistence layer for guest messaging timeline. 19 contract tests.

### Phase 237 — Staging Environment & Integration Tests *(closed)*
`docker-compose.staging.yml` + `.env.staging.example` + 10 integration smoke tests (auto-skipped unless `IHOUSE_ENV=staging`). First staging layer.

### Phase 238 — Ctrip / Trip.com Enhanced Adapter *(closed)*
Upgraded `tripcom.py` for Chinese market: CTRIP- prefix stripping, CNY currency default, Chinese name romanization fallback, Ctrip cancellation codes (NC/FC/PC). Added "ctrip" alias to registry. 16 tests.

### Phase 239 — Platform Checkpoint VII *(closed)*
Full system audit. 5 snapshot fixes. Wrote `next-15-phases-240-254.md` and handoff document. ~5,559 tests, 0 failures.


---

## AI Assistive Layer (Phases 220–227) — Complete ✅

> [!IMPORTANT]
> Full detail: `docs/core/planning/ai-strategy.md`
>
> Core principle: **Deterministic core = truth. AI = explanation, prioritization, recommendation, drafting.**

| Phase | Title | Status |
|-------|-------|--------|
| 221 | Scheduled Job Runner (SLA sweep, DLQ alerts, health log) | ✅ Closed |
| 222 | AI Context Aggregation — `/ai/context/property` + `/ai/context/operations-day` | ✅ Closed |
| 223 | Manager Copilot v1 — Morning Briefing (`POST /ai/copilot/morning-briefing`) | ✅ Closed |
| 224 | Financial Explainer — 7 anomaly flags, A/B/C tiers | ✅ Closed |
| 225 | Task Recommendation Engine — deterministic scoring | ✅ Closed |
| 226 | Anomaly Alert Broadcaster — 3-domain health scanner | ✅ Closed |
| 227 | Guest Messaging Copilot v1 — 6 intents, 5 languages, 3 tones | ✅ Closed |


---

## Forward Planning — Worker Communication & Escalation Layer

> [!IMPORTANT]
> Full detail: `docs/core/planning/worker-communication-layer.md`
>
> **Status (Phase 229):** This plan has been largely realized. All 5 escalation channels are live (LINE Phase 124, WhatsApp Phase 196, Telegram Phase 203, SMS Phase 212, Email Phase 213). The graded urgency pattern below describes the target model; the current system routes by worker `channel_type` preference.

The escalation model follows a **graded urgency pattern**:

| Urgency | Behavior |
|---------|----------|
| Low | In-app only, long SLA window |
| Medium | In-app first, external after delay if unacknowledged |
| High | In-app + fast external fallback |
| Critical | Manager escalation + SMS final fallback |

Schema fields already in place: `urgency`, `worker_role`, `ack_sla_minutes` — designed for per-task SLA, not global fixed timers.


---

## Where We're Headed

**Short-term (Phases 295+):** Guest portal frontend, owner portal frontend, multi-tenant org structure, production monitoring consumers, ML-based anomaly detection.

**Architecture:** The canonical core remains unchanged — `apply_envelope` is still the only write authority. All product layers (including AI) read from or wrap the canonical spine without mutating it. The focus shifts from API surface expansion to real product surfaces and operational depth.
