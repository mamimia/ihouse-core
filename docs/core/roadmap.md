# iHouse Core – Roadmap

> [!NOTE]
> This document is a living directional guide, not a binding contract.
> Updated every checkpoint to reflect what has been learned and where the system is headed.
> Last updated: Phase 814 (2026-03-17). [Antigravity]


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

## System Numbers — Phase 814 (2026-03-17)

| Metric | Value |
|--------|-------|
| **OTA Adapters** | 15 (14 unique + ctrip alias): Airbnb, Booking.com, Expedia, Agoda, Trip.com/Ctrip, Traveloka, Vrbo, GVR, MakeMyTrip, Klook, Despegar, Rakuten, Hotelbeds, Hostelworld |
| **Escalation Channels** | 5 live (LINE, WhatsApp, Telegram, SMS, Email) |
| **Task Kinds** | 6 (CLEANING, CHECKIN_PREP, CHECKOUT_VERIFY, MAINTENANCE, GENERAL, GUEST_WELCOME) |
| **API Router Files** | 126 files in `src/api/` |
| **Service Files** | 55 files in `src/services/` |
| **Financial Rings** | 6 complete (extraction → persistence → aggregation → reconciliation → cashflow → owner statement) |
| **AI Copilot Endpoints** | 8 (context aggregation, morning briefing, financial explainer, task recommendations, anomaly alerts, guest messaging, AI audit trail, worker copilot) |
| **Tests** | 7,765 passed / 0 failed / 12 skipped |
| **Test Files** | 281 test files |
| **Supabase Migrations** | 16 migration files (includes 1 baseline that consolidated early schemas) |
| **E2E Test Files** | 6 files (booking, financial, task, webhook, admin, DLQ) |
| **Production Infra** | Dockerfile, docker-compose.production.yml (frontend included Phase 313), .env.production.example, deploy_checklist.sh |
| **CI Pipeline** | Python 3.14, blocking ruff lint, migrations validation, security gate (Phase 279) |
| **Brand** | External: **Domaniqo** (domaniqo.com) — internal codename remains iHouse Core |
| **Frontend** | Next.js 16 / React 19, 63 pages, Domaniqo branding, 60s auto-refresh, SSE 6-channel live events |
| **CORS** | CORSMiddleware via `IHOUSE_CORS_ORIGINS` env var (Phase 313) |
| **Auth** | JWT with role claim (admin/manager/worker/owner), HMAC-SHA256 access tokens, real login/session endpoints, 7 auth UI screens |

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

## Active Direction — Operational Core Wave

> [!IMPORTANT]
> As of 2026-03-16, the system focus has shifted from deployment/PMS expansion to **product-facing operational surfaces**.
> A full architecture-aware audit revealed that the backend is strong but critical product layers are missing.

### Wave 1 Foundation (Phases 586-605) — ✅ COMPLETE
21 new tables, 37 new columns across 3 existing tables. All RLS-enabled with tenant isolation.

### Operational Core Sequence

| Phase | Surface | Architecture Source | Status |
|-------|---------|-------------------|--------|
| A | Property Detail (6-tab view) | `.agent/architecture/property-detail.md` | ✅ Done (gaps A-1 to A-4) |
| B | Staff Management (Manage Users) | `.agent/architecture/manage-users.md` | ✅ Done (gaps B-1 to B-5) |
| C | Dashboard Flight Cards (Admin + Ops) | `.agent/architecture/dashboard-flight-mode.md` | ✅ Done |
| — | **Checkpoint: Operational Awareness** | — | ✅ Passed |
| D | Mobile Check-in Flow (6-step) | `.agent/architecture/mobile-checkin.md` | ✅ Done (gaps D-1 to D-7) |
| E | Mobile Cleaner Flow (checklist+photos) | `.agent/architecture/mobile-cleaner.md` | 🔧 In Progress |
| F | Problem Reporting UI _(backend built: Phases 598, 647–652)_ | `.agent/architecture/mobile-maintenance.md` | ⬜ Next |
| — | **Checkpoint: One Property, End-to-End** | — | ⬜ Pending |

### PMS / Channel Manager — DEFERRED (NOT DISCARDED)

The PMS layer (Guesty adapter, Hostaway adapter, PMS Connect UI, channel mapping) is **deferred**, not removed.
- All PMS code, schemas, and documentation remain in the codebase
- PMS resumes after the "One Property, End-to-End" checkpoint
- No PMS code or docs should be deleted

### Previous Completed Directions

Phases 445–504: Docker staging, Supabase Auth, first live operations.
Phases 505–584: Brand identity, payment and subscription system, onboarding and access link flows, admin dashboard, frontend infrastructure.
Phases 585–605: Wave 1 Foundation schema extensions (21 tables, full operational data model).
Phases 730–800: Pre-801 auth identity fix, PII document security, guest token system, webhook infrastructure, channel map system.

---

## Where We're Headed

**Immediate (Operational Core A-C):** Build the three missing product-facing surfaces that block operational use: Property Detail (6-tab), Staff Management, Dashboard Flight Cards. Target: "Operational Awareness" — admin/manager can see properties, staff, and today's operations.

**Short-term (Operational Core D-F):** Build the three field operations: Check-in (6-step), Cleaner (checklist+photos), Problem Reports. Target: "One Property, End-to-End" — a single property can be operated from booking to checkout through the UI.

**After Operational Core:** PMS / Channel Manager layer resumes. Live PMS credentials integration. Production multi-property scaling.

**Architecture:** The canonical core remains unchanged — `apply_envelope` is still the only write authority. All new surfaces consume projections and write through existing API patterns.

### Workflow Rules (Permanently Locked)

1. **UI proof every 1–3 phases** — no invisible progress
2. **Architecture-first** — check `.agent/architecture/` before building
3. **Docs-first wave changes** — full gap analysis before starting new waves
4. **Gap prevention checklist** at every Phase 20 audit
5. **PMS deferred, not discarded** — resumes after Operational Core


