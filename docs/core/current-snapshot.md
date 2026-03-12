# iHouse Core — Current Snapshot

## Current Phase
Phase 323 — (Next)

## Last Closed Phase
Phase 322 — Manager Copilot + AI Layer Operational Readiness (closed) — 14 tests, all pass.

## System Status

**Full HTTP ingestion stack (58–64). Financial Layer (65–67). booking_id Stability (68). BOOKING_AMENDED live (69). Booking Query API (71). Tenant Dashboard (72). Financial Aggregation (116). SLA Engine (117). Financial Dashboard (118). Reconciliation Inbox (119). Cashflow View (120). Owner Statement Generator (121). OTA Financial Health Comparison (122). Worker-Facing Task Surface (123). LINE Escalation Channel (124). Hotelbeds Adapter (125). Availability Projection (126). Integration Health Dashboard (127). Conflict Center (128). Booking Search (129). Properties Summary Dashboard (130). DLQ Inspector (131). Booking Audit Trail (132). OTA Ordering Buffer Inspector (133). Property-Channel Map Foundation (135). Provider Capability Registry (136). Outbound Sync Trigger (137). Outbound Executor (138). Real Outbound Adapters (139). iCal Date Injection (140). Rate-Limit Enforcement (141). Retry + Exponential Backoff (142). Idempotency Key (143). Outbound Sync Result Persistence (144). Outbound Sync Log Inspector (145). Sync Health Dashboard (146). Failed Sync Replay (147). Sync Result Webhook Callback (148). RFC 5545 VCALENDAR Compliance (149). iCal Timezone Support (150). iCal Cancellation Push (151). iCal Sync-on-Amendment Push (152). Operations Dashboard UI (153). API-first Cancel Push (154). API-first Amend Push (155). Worker Task UI (157). Bookings View UI (158). Financial Dashboard UI (163). Owner Statement UI (164). Properties Metadata API (165). Role-Based Scoping (166). Permissions Routing (167). Push Notification Foundation (168). Admin Settings UI (169). Owner Portal UI (170). Admin Audit Log (171). Health Check Enrichment (172). IPI — Proactive Availability Broadcasting (173). Outbound Sync Stress Harness (174). Platform Checkpoint I (175). Outbound Sync Auto-Trigger for BOOKING_CREATED (176). SLA→Dispatcher Bridge (177). Notification Delivery Writer (178–183). PDF Owner Statements (188). Booking Mutation Audit Events (189). Manager Activity Feed UI (190). Multi-Currency Financial Overview (191). Guest Profile Foundation (192). Guest Profile UI (193). Booking→Guest Link (194). Hostelworld Adapter (195). WhatsApp Escalation Channel (196). Platform Checkpoint II (197). Test Suite Stabilization (198). Supabase RLS Audit (199). Booking Calendar UI (200). Worker Channel Preference UI (201). Notification History Inbox (202). Telegram Escalation Channel (203). Docs Sync (204). DLQ Replay from UI (205). Pre-Arrival Guest Task Workflow (206). Conflict Auto-Resolution Engine (207). Platform Checkpoint III (208). Outbound Sync Trigger Consolidation (209). Roadmap & Documentation Cleanup (210). Production Deployment Foundation (211). SMS Escalation Channel (212). Email Notification Channel (213). Property Onboarding Wizard API (214). Automated Revenue Reports (215). Portfolio Dashboard UI (216). Integration Management UI (217). Platform Checkpoint IV (218). Documentation Integrity Repair (219). CI/CD Pipeline Foundation (220). Scheduled Job Runner (221). AI Context Aggregation (222). Manager Copilot v1 (223). Financial Explainer (224). Task Recommendation Engine (225). Anomaly Alert Broadcaster (226). Guest Messaging Copilot v1 (227). Platform Checkpoint V (228). Platform Checkpoint VI (229). AI Audit Trail (230). Worker Task Copilot (231). Guest Pre-Arrival Automation Chain (232). Revenue Forecast Engine (233). Shift & Availability Scheduler (234). Multi-Property Conflict Dashboard (235). Guest Communication History (236). Staging Environment & Integration Tests (237). Ctrip / Trip.com Enhanced Adapter (238). Platform Checkpoint VII (239). Documentation Integrity Sync (240). Booking Financial Reconciliation Dashboard API (241). Booking Lifecycle State Machine Visualization API (242). Property Performance Analytics API (243). OTA Revenue Mix Analytics API (244). Platform Checkpoint VIII (245). Rate Card & Pricing Rules Engine (246). Guest Feedback Collection API (247). Maintenance & Housekeeping Task Templates (248). Booking.com Content API Adapter (250). Dynamic Pricing Suggestion Engine (251). Owner Financial Report API v2 (252). Staff Performance Dashboard API (253). Platform Checkpoint X (254). Bulk Operations API (255). i18n + Language Switcher + Thai/Hebrew RTL UI (256–260). Webhook Event Logging (261). Guest Self-Service Portal API (262). Production Monitoring Hooks (263). Advanced Analytics + Platform Checkpoint XI (264). Test Suite Repair + Documentation Integrity Sync (265). E2E Booking Flow Integration Test (266). E2E Financial Summary Integration Test (267). E2E Task System Integration Test (268). E2E Webhook Ingestion Integration Test (269). E2E Admin & Properties Integration Test (270). E2E DLQ & Replay Integration Test (271). Platform Checkpoint XII (272). Documentation Integrity Sync XIII (273). Supabase Migration Reproducibility (274). Deployment Readiness Audit (275). Real JWT Authentication Flow (276). Supabase RPC + Schema Alignment (277). Production Environment Configuration (278). CI Pipeline Hardening (279). Real Webhook Endpoint Validation (280). First Live OTA Integration Test (281). Platform Checkpoint XIII (282). Test Suite Isolation Fix + conftest.py (283). Supabase Schema Truth Sync (284). Documentation Integrity Sync XIV (285). Production Docker Hardening (286). Frontend Foundation (287). Operations Dashboard UI (288). Booking Management UI (289). Worker Task View UI (290). Financial Dashboard UI (291). Platform Checkpoint XIV (292). Price Deviation Detector (293). History & Configuration Truth Sync (294). Documentation Truth Sync XV + Branding Update (295). Multi-Tenant Organization Foundation (296). Auth Session Management + Real Login Flow (297). Guest Portal + Owner Portal Real Authentication (298). Notification Layer SMS/Email Dispatch (299). Platform Checkpoint XIV (300). Owner Portal Rich Data Service (301). Guest Token Flow E2E Tests (302). Booking State Seeder for Owner Portal (303). Platform Checkpoint XV (304). Documentation Truth Sync XVI (305). Real-Time Event Bus — SSE 6 named channels (306). Frontend Real Data — Dashboard + Bookings SSE (307). Frontend Real Data — Financial + Tasks SSE (308). Owner Portal Frontend SSE + Cashflow (309). Guest Portal Frontend SSE (310). Admin Notification Dashboard (311). Manager Copilot UI — Morning Briefing Widget (312). Production Readiness — CORS + Frontend Docker (313). Platform Checkpoint XVI (314). Layer C Documentation Sync XVII (315).**


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
| 66 | booking_financial_facts Supabase projection | ✅ |
| 67 | Financial Facts Query API — GET /financial/{booking_id} | ✅ |
| 68 | booking_id Stability — normalize_reservation_ref, all adapters | ✅ |
| 69 | BOOKING_AMENDED Python Pipeline | ✅ |
| 71 | Booking State Query API — GET /bookings/{booking_id} | ✅ |
| 72 | Tenant Summary Dashboard — GET /admin/summary | ✅ |
| 73 | Ordering Buffer Auto-Route | ✅ |
| 74 | OTA Date Normalization | ✅ |
| 75 | Production Hardening — error_models.py, X-API-Version | ✅ |
| 76 | occurred_at vs recorded_at Separation | ✅ |
| 77 | OTA Schema Normalization (3 keys) | ✅ |
| 78 | OTA Schema Normalization (Dates + Price) | ✅ |
| 79 | Idempotency Monitoring | ✅ |
| 80 | Structured Logging Layer | ✅ |
| 81 | Tenant Isolation Audit | ✅ |
| 82 | Admin Query API | ✅ |
| 83 | Vrbo Adapter | ✅ |
| 84 | Reservation Timeline | ✅ |
| 85 | Google Vacation Rentals Adapter | ✅ |
| 86 | Conflict Detection Layer | ✅ |
| 87 | Tenant Isolation Hardening | ✅ |
| 88 | Traveloka Adapter | ✅ |
| 89 | OTA Reconciliation Discovery | ✅ |
| 90 | External Integration Test Harness | ✅ |
| 91 | OTA Replay Fixture Contract | ✅ |
| 92 | Roadmap + System Audit | ✅ |
| 93 | Payment Lifecycle / Revenue State Projection | ✅ |
| 94 | MakeMyTrip Adapter (Tier 2 India) | ✅ |
| 95 | MakeMyTrip Replay Fixture Contract | ✅ |
| 96 | Klook Adapter (Tier 2 Asia activities) | ✅ |
| 97 | Klook Replay Fixture Contract | ✅ |
| 98 | Despegar Adapter (Tier 2 Latin America) | ✅ |
| 99 | Despegar Replay Fixture Contract | ✅ |
| 100 | Owner Statement Foundation | ✅ |
| 101 | Owner Statement Query API | ✅ |
| 102 | E2E Harness Extension (MakeMyTrip+Klook+Despegar) | ✅ |
| 103 | Payment Lifecycle Query API | ✅ |
| 104 | Amendment History Query API | ✅ |
| 105 | Admin Router Contract Tests | ✅ |
| 106 | Booking List Query API | ✅ |
| 107 | Roadmap Refresh | ✅ |
| 108 | Financial List Query API | ✅ |
| 109 | Booking Date Range Search | ✅ |
| 110 | OTA Reconciliation Implementation | ✅ |
| 111 | Task System Foundation | ✅ |
| 112 | Task Automation from Booking Events | ✅ |
| 113 | Task Query API | ✅ |
| 114 | Task Persistence Layer (Supabase DDL) | ✅ |
| 115 | Task Writer | ✅ |
| 116 | Financial Aggregation API | ✅ |
| 117 | SLA Escalation Engine | ✅ |
| 118 | Financial Dashboard API | ✅ |
| 119 | Reconciliation Inbox API | ✅ |
| 120 | Cashflow / Payout Timeline | ✅ |
| 121 | Owner Statement Generator (Ring 4) | ✅ |
| 122 | OTA Financial Health Comparison | ✅ |
| 123 | Worker-Facing Task Surface | ✅ |
| 124 | LINE Escalation Channel | ✅ |
| 125 | Hotelbeds Adapter (Tier 3 B2B Bedbank) | ✅ |
| 126 | Availability Projection | ✅ |
| 127 | Integration Health Dashboard | ✅ |
| 128 | Conflict Center | ✅ |
| 129 | Booking Search Enhancement | ✅ |
| 130 | Properties Summary Dashboard | ✅ |
| 131 | DLQ Inspector | ✅ |
| 132 | Booking Audit Trail | ✅ |
| 133 | OTA Ordering Buffer Inspector | ✅ |
| 135 | Property-Channel Map Foundation | ✅ |
| 136 | Provider Capability Registry | ✅ |
| 137 | Outbound Sync Trigger | ✅ |
| 138 | Outbound Executor | ✅ |
| 139 | Real Outbound Adapters (4 providers) | ✅ |
| 140 | iCal Date Injection | ✅ |
| 141 | Rate-Limit Enforcement | ✅ |
| 142 | Retry + Exponential Backoff | ✅ |
| 143 | Idempotency Key | ✅ |
| 144 | Outbound Sync Result Persistence | ✅ |
| 145 | Outbound Sync Log Inspector | ✅ |
| 146 | Sync Health Dashboard | ✅ |
| 147 | Failed Sync Replay | ✅ |
| 148 | Sync Result Webhook Callback | ✅ |
| 149 | RFC 5545 VCALENDAR Compliance | ✅ |
| 150 | iCal VTIMEZONE Support | ✅ |
| 151 | iCal Cancellation Push | ✅ |
| 152 | iCal Sync-on-Amendment Push | ✅ |
| 153 | Operations Dashboard UI | ✅ |
| 154 | API-first Cancel Push | ✅ |
| 155 | API-first Amend Push | ✅ |
| 157 | Worker Task UI | ✅ |
| 158 | Bookings View UI | ✅ |
| 163 | Financial Dashboard UI | ✅ |
| 164 | Owner Statement UI | ✅ |
| 165 | Properties Metadata API | ✅ |
| 166 | Role-Based Scoping | ✅ |
| 167 | Permissions Routing | ✅ |
| 168 | Push Notification Foundation | ✅ |
| 169 | Admin Settings UI | ✅ |
| 170 | Owner Portal UI | ✅ |
| 171 | Admin Audit Log | ✅ |
| 172 | Health Check Enrichment | ✅ |
| 173 | IPI — Proactive Availability Broadcasting | ✅ |
| 174 | Outbound Sync Stress Harness | ✅ |
| 175 | Platform Checkpoint I | ✅ |
| 176 | Outbound Sync Auto-Trigger for BOOKING_CREATED | ✅ |
| 177 | SLA→Dispatcher Bridge | ✅ |
| 178–183 | Notification Delivery Writer + Channel Infra | ✅ |
| 188 | PDF Owner Statements | ✅ |
| 189 | Booking Mutation Audit Events | ✅ |
| 190 | Manager Activity Feed UI | ✅ |
| 191 | Multi-Currency Financial Overview | ✅ |
| 192 | Guest Profile Foundation | ✅ |
| 193 | Guest Profile UI | ✅ |
| 194 | Booking→Guest Link | ✅ |
| 195 | Hostelworld Adapter (Tier 3, 13th adapter) | ✅ |
| 196 | WhatsApp Escalation Channel — Per-Worker Architecture | ✅ |
| 197 | Platform Checkpoint II — docs sync, handoff | ✅ |
| 198 | Test Suite Stabilization — 4903 passing, 0 failed | ✅ |
| 199 | Supabase RLS Systematic Audit — 0 security findings | ✅ |
| 200 | Booking Calendar UI — `/calendar` month-view + filters | ✅ |
| 201 | Worker Channel Preference UI — notification_channels table, GET/PUT/DELETE /worker/preferences, Channel 🔔 tab | ✅ |
| 202 | Notification History Inbox — notification_delivery_log table, GET /worker/notifications, history in Channel tab | ✅ |
| 203 | Telegram Escalation Channel — telegram_escalation.py pure module, dispatcher upgraded | ✅ |
| 204 | Docs Sync — live-system.md, current-snapshot.md refreshed | ✅ |
| 205 | DLQ Replay from UI — POST /admin/dlq/{envelope_id}/replay, /admin/dlq page | ✅ |
| 206 | Pre-Arrival Guest Task Workflow — GUEST_WELCOME kind, pre_arrival_tasks.py, POST /tasks/pre-arrival/{booking_id} | ✅ |
| 207 | Conflict Auto-Resolution Engine — conflict_auto_resolver.py, POST /conflicts/auto-check/{booking_id}, service.py auto-hooks | ✅ |
| 208 | Platform Checkpoint III — docs audit, handoff, forward plan | ✅ |
| 209 | Outbound Sync Trigger Consolidation — dual-trigger tech debt closed | ✅ |
| 210 | Roadmap & Documentation Cleanup — audit, archive stale files, AI strategy | ✅ |
| 211 | Production Deployment Foundation — Dockerfile, docker-compose, .dockerignore, requirements.txt, GET /readiness | ✅ |
| 212 | SMS Escalation Channel — sms_escalation.py, sms_router.py (GET + POST), registered in main.py, python-multipart | ✅ |
| 213 | Email Notification Channel — email_escalation.py, email_router.py (GET health + GET /email/ack one-click token ACK) | ✅ |
| 214 | Property Onboarding Wizard API — onboarding_router.py (POST /start, POST /{id}/channels, POST /{id}/workers, GET /{id}/status) | ✅ |
| 215 | Automated Revenue Reports — revenue_report_router.py (GET /revenue-report/portfolio + GET /revenue-report/{id}, monthly breakdown + cross-property portfolio, mgmt fee) | ✅ |
| 216 | Portfolio Dashboard UI — portfolio_dashboard_router.py (GET /portfolio/dashboard: occupancy + revenue + tasks + sync health per property, sorted by urgency) | ✅ |
| 217 | Integration Management UI — integration_management_router.py (GET /admin/integrations: all OTA connections grouped by property + sync status; GET /admin/integrations/summary) | ✅ |
| 218 | Platform Checkpoint IV — full audit + docs sync (current-snapshot, work-context, roadmap), handoff_to_new_chat_Phase-218.md | ✅ |
| 219 | Documentation Integrity Repair — missing phase-timeline entries for 211–218 | ✅ |
| 220 | CI/CD Pipeline Foundation — `.github/workflows/ci.yml`, 3-job pipeline | ✅ |
| 221 | Scheduled Job Runner — APScheduler (SLA sweep, DLQ alert, health log) + `GET /admin/scheduler-status` | ✅ |
| 222 | AI Context Aggregation — `GET /ai/context/property/{id}` + `GET /ai/context/operations-day` | ✅ |
| 223 | Manager Copilot v1 — `POST /ai/copilot/morning-briefing`, 5 languages, LLM + heuristic | ✅ |
| 224 | Financial Explainer — 7 anomaly flags, A/B/C tiers, LLM + heuristic | ✅ |
| 225 | Task Recommendation Engine — deterministic scoring + LLM rationale | ✅ |
| 226 | Anomaly Alert Broadcaster — 3-domain scanner, health score 0–100 | ✅ |
| 227 | Guest Messaging Copilot v1 — 6 intents, 5 langs, 3 tones, draft-only | ✅ |
| 228 | Platform Checkpoint V | ✅ |
| 229 | Platform Checkpoint VI | ✅ |
| 230 | AI Audit Trail | ✅ |
| 231 | Worker Task Copilot | ✅ |
| 232 | Guest Pre-Arrival Automation Chain | ✅ |
| 233 | Revenue Forecast Engine | ✅ |
| 234 | Shift & Availability Scheduler | ✅ |
| 235 | Multi-Property Conflict Dashboard | ✅ |
| 236 | Guest Communication History | ✅ |
| 237 | Staging Environment & Integration Tests | ✅ |
| 238 | Ctrip / Trip.com Enhanced Adapter | ✅ |
| 239 | Platform Checkpoint VII — full audit, phase-timeline/construction-log fixed, handoff created | ✅ |
| 240 | Documentation Integrity Sync — work-context, roadmap, live-system updated to Phase 239 reality | ✅ |
| 241 | Booking Financial Reconciliation Dashboard API — GET /admin/reconciliation/dashboard, 28 tests | ✅ |
| 242 | Booking Lifecycle State Machine Visualization API — GET /admin/bookings/lifecycle-states, 32 tests | ✅ |
| 243 | Property Performance Analytics API — GET /admin/properties/performance (booking_state + financial_facts), 35 tests | ✅ |
| 244 | OTA Revenue Mix Analytics API — GET /admin/ota/revenue-mix (all-time gross/net/commission per OTA), 41 tests | ✅ |
| 245 | Platform Checkpoint VIII — docs audit, canonical docs updated, ~5,695 tests passing | ✅ |
| 246 | Rate Card & Pricing Rules Engine — rate_cards table, GET/POST, price deviation alerts, 35 tests | ✅ |
| 247 | Guest Feedback Collection API — guest_feedback table, GET/POST/DELETE, 30 tests | ✅ |
| 248 | Maintenance & Housekeeping Task Templates — task_templates table, GET/POST/DELETE, 26 tests | ✅ |
| 250 | Booking.com Content API Adapter — bookingcom_content.py, POST /admin/content/push, 32 tests | ✅ |
| 251 | Dynamic Pricing Suggestion Engine — pricing_engine.py, GET /pricing/suggestion, 37 tests | ✅ |
| 252 | Owner Financial Report API v2 — GET /owner/financial-report, drill-down, 31 tests | ✅ |
| 253 | Staff Performance Dashboard API — GET /admin/staff/performance, 24 tests | ✅ |
| 254 | Platform Checkpoint X — full audit + handoff | ✅ |
| 255 | Bulk Operations API — bulk cancel/assign/sync, 16 tests | ✅ |
| 256–260 | i18n Foundation + Language Switcher + Thai/Hebrew RTL UI — EN/TH/HE, localStorage, auto-RTL | ✅ |
| 261 | Webhook Event Logging — append-only in-memory log, no PII, 19 tests | ✅ |
| 262 | Guest Self-Service Portal API — X-Guest-Token gated, /booking/wifi/rules, 22 tests | ✅ |
| 263 | Production Monitoring Hooks — /admin/monitor, health probe 200/503, latency p95, 18 tests | ✅ |
| 264 | Advanced Analytics + Platform Checkpoint XI — top-properties/ota-mix/revenue-summary, 20 tests | ✅ |

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

## OTA Adapters — 14 Live

| Adapter | Market | Tier |
|---------|--------|------|
| Airbnb | Global | 1 |
| Booking.com | Global | 1 |
| Expedia | Global | 1 |
| Agoda | Asia | 1.5 |
| Trip.com / Ctrip | China / Global | 2 |
| Traveloka | SE Asia | 1.5 |
| Vrbo | Global vacation | 2 |
| Google Vacation Rentals | Global | 2 |
| MakeMyTrip | India | 2 |
| Klook | Asia activities | 2 |
| Despegar | Latin America | 2 |
| Rakuten Travel | Japan | 2 |
| Hotelbeds | B2B bedbank | 3 |
| Hostelworld | Budget/hostel global | 3 |

## Escalation Channel Architecture (Phase 196 — Per-Worker)

```
Tier 1 — in-app (always first, iHouse task acknowledgement)
Tier 2 — preferred external channel (per worker, one of:)
            LINE       → channel_type="line"      (Thailand/JP dominant)
            WhatsApp   → channel_type="whatsapp"  (SEA/EU/Global)
            Telegram   → channel_type="telegram"  (live — Phase 203)
Tier 3 — External (one of:)
            SMS        → channel_type="sms"       (Phase 212)
            Email      → channel_type="email"     (Phase 213)
```

**No global fallback chain.** Each worker has their own `channel_type` in `notification_channels`. The dispatcher reads it and routes there only.

## Key Files — Channel Layer (Phases 124 + 168 + 177 + 196)

| File | Role |
|------|------|
| `src/channels/line_escalation.py` | LINE pure module — should_escalate, build_line_message, HMAC-SHA256 verify |
| `src/api/line_webhook_router.py` | GET+POST /line/webhook |
| `src/channels/whatsapp_escalation.py` | WhatsApp pure module — same pattern as LINE |
| `src/api/whatsapp_router.py` | GET+POST /whatsapp/webhook |
| `src/channels/telegram_escalation.py` | Telegram pure module — should_escalate, build_telegram_message, format_telegram_text (Markdown), is_priority_eligible (Phase 203) |
| `src/channels/notification_dispatcher.py` | Core dispatcher — routes by worker's channel_type. CHANNEL_LINE/WHATSAPP/TELEGRAM/SMS constants. No global chain. |
| `src/channels/sla_dispatch_bridge.py` | Connects sla_engine.evaluate() → dispatch_notification(). Per-worker routing. |
| `src/channels/notification_delivery_writer.py` | Best-effort delivery log writer (notification_delivery_log table) |

## Key Files — API Layer

| File | Role |
|------|------|
| `src/api/webhooks.py` | POST /webhooks/{provider} — OTA ingestion |
| `src/api/financial_router.py` | GET /financial/{booking_id} |
| `src/api/auth.py` | JWT verification |
| `src/api/rate_limiter.py` | Per-tenant rate limiting |
| `src/api/health.py` | Dependency health checks |
| `src/schemas/responses.py` | OpenAPI Pydantic response models |
| `src/main.py` | FastAPI app entrypoint (all routers registered) |

## Key Files — Task Layer (Phases 111–117)

| File | Role |
|------|------|
| `src/tasks/task_model.py` | TaskKind (6 kinds incl GUEST_WELCOME), TaskStatus, TaskPriority, WorkerRole, Task dataclass |
| `src/tasks/task_automator.py` | Pure tasks_for_booking_created / canceled / amended |
| `src/tasks/pre_arrival_tasks.py` | Pure tasks_for_pre_arrival — GUEST_WELCOME + enriched CHECKIN_PREP (Phase 206) |
| `src/tasks/task_writer.py` | Supabase upsert/cancel/reschedule |
| `src/tasks/task_router.py` | GET /tasks, GET /tasks/{id}, PATCH /tasks/{id}/status, POST /tasks/pre-arrival/{booking_id} |
| `src/tasks/sla_engine.py` | evaluate() — ACK_SLA_BREACH + COMPLETION_SLA_BREACH. CRITICAL_ACK_SLA_MINUTES=5. |
| `src/services/conflict_auto_resolver.py` | Phase 207 — run_auto_check() — auto-conflict on BOOKING_CREATED/AMENDED |

## Key Invariants (Locked — Do Not Change)

- `apply_envelope` is the single write authority — no adapter reads/writes booking_state directly
- `event_log` is append-only — no updates, no deletes ever
- `booking_id = "{source}_{reservation_ref}"` — deterministic, canonical (Phase 36)
- `reservation_ref` normalized by `normalize_reservation_ref()` before use (Phase 68)
- HTTP endpoint routes through `ingest_provider_event` → pipeline → `apply_envelope`
- `tenant_id` from verified JWT `sub` claim only — NEVER from payload body (Phase 61+)
- `booking_state` is a read model ONLY — must NEVER contain financial calculations
- All financial read endpoints query `booking_financial_facts` ONLY — never `booking_state`
- Deduplication: most-recent `recorded_at` per `booking_id`
- Epistemic tier: FULL→A, ESTIMATED→B, PARTIAL→C. Worst tier wins in aggregated endpoints.
- OTA_COLLECTING net is NEVER included in owner_net_total — honesty invariant
- External channels (LINE, WhatsApp, Telegram) are escalation fallbacks ONLY — never source of truth
- `notification_channels` is the per-worker channel preference store — no global fallback chain

## Environment Variables

| Var | Default | Effect |
|-----|---------|--------|
| `IHOUSE_WEBHOOK_SECRET_{PROVIDER}` | unset | sig verification skipped when unset |
| `IHOUSE_JWT_SECRET` | unset | 503 if unset and IHOUSE_DEV_MODE≠true |
| `IHOUSE_API_KEY` | unset | API key for external integrations |
| `IHOUSE_DEV_MODE` | unset | "true" = skip JWT auth, return dev-tenant. MUST be false in production (Phase 276) |
| `IHOUSE_RATE_LIMIT_RPM` | 60 | req/min per tenant, 0 = disabled |
| `IHOUSE_ENV` | "development" | health response label |
| `IHOUSE_TENANT_ID` | unset | production tenant UUID |
| `SUPABASE_URL` | required | Supabase project URL |
| `SUPABASE_KEY` | required | Supabase anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | required | Used by all financial/admin routers (Phases 116+) |
| `IHOUSE_LINE_SECRET` | unset | LINE channel secret (sig verify) |
| `IHOUSE_LINE_CHANNEL_TOKEN` | unset | LINE channel access token |
| `IHOUSE_WHATSAPP_TOKEN` | unset | production WhatsApp dispatch |
| `IHOUSE_WHATSAPP_PHONE_NUMBER_ID` | unset | Meta Cloud API phone ID |
| `IHOUSE_WHATSAPP_APP_SECRET` | unset | HMAC sig verification |
| `IHOUSE_WHATSAPP_VERIFY_TOKEN` | unset | Meta webhook challenge token |
| `IHOUSE_TELEGRAM_BOT_TOKEN` | unset | Telegram bot API token |
| `IHOUSE_SMS_TOKEN` | unset | SMS provider API token (Phase 212) |
| `IHOUSE_EMAIL_TOKEN` | unset | Email provider API token (Phase 213) |
| `IHOUSE_DRY_RUN` | unset | skip real outbound API calls |
| `IHOUSE_THROTTLE_DISABLED` | unset | skip rate limiting in outbound |
| `IHOUSE_RETRY_DISABLED` | unset | skip exponential backoff |
| `IHOUSE_SYNC_LOG_DISABLED` | unset | skip persistence of sync results |
| `IHOUSE_SYNC_CALLBACK_URL` | unset | webhook URL for sync.ok events |
| `IHOUSE_SCHEDULER_ENABLED` | unset | enable APScheduler jobs (Phase 221) |
| `IHOUSE_SLA_SWEEP_INTERVAL` | 120 | SLA sweep interval in seconds |
| `IHOUSE_DLQ_ALERT_INTERVAL` | 600 | DLQ alert check interval in seconds |
| `OPENAI_API_KEY` | unset | OpenAI API key for AI copilot endpoints |
| `SENTRY_DSN` | unset | Sentry error tracking DSN |
| `PORT` | 8000 | uvicorn port |
| `UVICORN_WORKERS` | 1 | number of uvicorn worker processes |
| `IHOUSE_GUEST_TOKEN_SECRET` | required | HMAC-SHA256 secret for guest portal tokens (Phase 298) |
| `IHOUSE_TWILIO_SID` | unset | Twilio Account SID (Phase 299) |
| `IHOUSE_TWILIO_TOKEN` | unset | Twilio Auth Token (Phase 299) |
| `IHOUSE_TWILIO_FROM` | unset | Sending phone number E.164 (Phase 299) |
| `IHOUSE_SENDGRID_KEY` | unset | SendGrid API key (Phase 299) |
| `IHOUSE_SENDGRID_FROM` | unset | Sending email address (Phase 299) |
| `IHOUSE_CORS_ORIGINS` | unset | Comma-separated allowed CORS origins for frontend (Phase 313) |

Phase 315 — see `docs/core/planning/` for next cycle.

## Tests

**6,406 collected. ~6,385 passing (~17 skipped). 4 pre-existing health/Supabase failures (env-dependent, not regressions). Exit 0 on code tests. (Phase 304 — no new backend tests in Phases 305-314, all frontend-only)**
