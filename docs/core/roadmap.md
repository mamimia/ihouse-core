# iHouse Core – Roadmap

> [!NOTE]
> This document is a living directional guide, not a binding contract.
> Updated every checkpoint to reflect what has been learned and where the system is headed.
> Last updated: Phase 415 (2026-03-13). [Antigravity]


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

## System Numbers — Phase 444 (2026-03-13)

| Metric | Value |
|--------|-------|
| **OTA Adapters** | 15 (14 unique + ctrip alias): Airbnb, Booking.com, Expedia, Agoda, Trip.com/Ctrip, Traveloka, Vrbo, GVR, MakeMyTrip, Klook, Despegar, Rakuten, Hotelbeds, Hostelworld |
| **Escalation Channels** | 5 live (LINE, WhatsApp, Telegram, SMS, Email) |
| **Task Kinds** | 6 (CLEANING, CHECKIN_PREP, CHECKOUT_VERIFY, MAINTENANCE, GENERAL, GUEST_WELCOME) |
| **API Router Files** | 87 files in `src/api/` |
| **Service Files** | 29 files in `src/services/` |
| **Financial Rings** | 6 complete (extraction → persistence → aggregation → reconciliation → cashflow → owner statement) |
| **AI Copilot Endpoints** | 8 (context aggregation, morning briefing, financial explainer, task recommendations, anomaly alerts, guest messaging, AI audit trail, worker copilot) |
| **Tests** | 7,187 passed / 9 failed (pre-existing Supabase infra) / 17 skipped |
| **Test Files** | 251 test files |
| **Supabase Migrations** | 16 migration files (includes 1 baseline that consolidated early schemas) |
| **E2E Test Files** | 6 files (booking, financial, task, webhook, admin, DLQ) |
| **Production Infra** | Dockerfile, docker-compose.production.yml (frontend included Phase 313), .env.production.example, deploy_checklist.sh |
| **CI Pipeline** | Python 3.14, blocking ruff lint, migrations validation, security gate (Phase 279) |
| **Brand** | External: **Domaniqo** (domaniqo.com) — internal codename remains iHouse Core |
| **Frontend** | Next.js 16 / React 19, 37 pages (24 protected + 13 public), Domaniqo branding, 60s auto-refresh, SSE 6-channel live events |
| **CORS** | CORSMiddleware via `IHOUSE_CORS_ORIGINS` env var (Phase 313) |
| **Auth** | JWT with role claim (admin/manager/worker/owner), HMAC-SHA256 access tokens, real login/session endpoints |

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

## Active Direction — Phase 445+

Phases 355–374: Cancel/Amend adapter repair, Layer C alignment, Supabase schema sync, production readiness hardening, frontend error boundaries, rate limiter hardening, Platform Checkpoints XVIII-XIX.

Phases 375–394: 20-phase frontend platform consolidation — route group split, responsive adaptation, mobile role surfaces, access-link system, shared component extraction.

Phases 395–404: Hard Truth Audit recovery — Property Onboarding, Admin Dashboard, JWT enforcement, Checkin/Checkout backend, Access Token System, Guest/Invite/Onboard flows, E2E tests.

Phases 405–414: Foundation Checkpoint (405–408), Product Connection (409–413), Closing Audit (414).

Phases 415–424: Production readiness block — dead code cleanup, schema reference, env validation, error handling tests, E2E smoke tests, staging guide.

Phases 425–444: Production readiness verification — 4 blocks: document truth + test green (425-429), production infrastructure (430-434), real integration + monitoring (435-439), hardening + closing audit (440-444). 7,200 passed, zero regressions. Supabase live with 5,335 events, 1,516 bookings, 14 tenants.

### Next Direction — Phase 445+

Focus: **First real deployment and live operations** — Docker build + deploy to staging, Supabase Auth first user, first real notification dispatch, real OTA provider webhook, production scaling, multi-property onboarding.

---

## Where We're Headed

**Short-term (Phase 445+):** First Docker build + staging deploy. First Supabase Auth user. First real notification dispatch (LINE or email). First real OTA webhook from a live provider. Multi-property scaling.

**Architecture:** The canonical core remains unchanged — `apply_envelope` is still the only write authority. The system is verified production-ready from code and architecture perspective. Focus shifts to **real deployment and real operations**.

