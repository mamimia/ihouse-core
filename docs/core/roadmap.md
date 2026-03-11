# iHouse Core – Roadmap

> [!NOTE]
> This document is a living directional guide, not a binding contract.
> Updated every checkpoint to reflect what has been learned and where the system is headed.
> Last updated: Phase 218 (2026-03-11). [Antigravity]


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

## System Numbers — Phase 218 (2026-03-11)

| Metric | Value |
|--------|-------|
| **OTA Adapters** | 14 live (Airbnb, Booking.com, Expedia, Agoda, Trip.com, Traveloka, Vrbo, GVR, MakeMyTrip, Klook, Despegar, Rakuten, Hotelbeds, Hostelworld) |
| **Escalation Channels** | 5 live/stubbed (LINE, WhatsApp, Telegram, SMS — Phase 212, Email — Phase 213) |
| **Task Kinds** | 6 (CLEANING, CHECKIN_PREP, CHECKOUT_VERIFY, MAINTENANCE, GENERAL, GUEST_WELCOME) |
| **UI/Product Surfaces** | 16 (ops dashboard, bookings, calendar, tasks, worker, financial, owner statement, owner portal, guests, admin settings, manager feed, admin DLQ, onboarding wizard, revenue reports, portfolio dashboard, integration management) |
| **Financial Rings** | 6 complete (extraction → persistence → aggregation → reconciliation → cashflow → owner statement) |
| **Tests** | 5,179 collected / 5,179 passing / 0 failures |

---

## ✅ Completed Phases (1–209)

### Foundation (Phases 21–64)
OTA ingestion boundary, adapter layer, DLQ, replay, canonical events (BOOKING_CREATED/CANCELED/AMENDED), service pipeline, FastAPI app, JWT auth, rate limiting, OpenAPI, health checks.

### Financial Layer (Phases 65–66, 93, 100–101, 108, 116, 118–122)
BookingFinancialFacts extraction + persistence, payment lifecycle (7 states), owner statements, financial aggregation APIs, cashflow projections, OTA financial health comparison.

### Schema + Monitoring (Phases 77–82)
Canonical schema normalization, idempotency monitoring, structured logging, integration health dashboard, admin query API.

### Adapters (Phases 83, 85, 88, 94, 96, 98, 125, 187, 195)
Vrbo, GVR, Traveloka, MakeMyTrip, Klook, Despegar, Hotelbeds, Rakuten, Hostelworld — 14 total adapters live.

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

### Platform Checkpoints (Phases 92, 107, 175, 180, 191, 197, 204, 208)
Roadmap refreshes, system audits, documentation sync, handoff documents.

### Recent — Phases 198–209
Test suite stabilization, Supabase RLS audit, conflict auto-resolution engine, Phase 209 outbound sync trigger consolidation (tech debt closure).

---

## Tech Debt — Closed

| Debt | Opened | Closed | Resolution |
|------|--------|--------|------------|
| Dual outbound sync triggers (fast-path + guaranteed-path) | Phase 182 | **Phase 209** | Deprecated `cancel_sync_trigger.py` + `amend_sync_trigger.py` deleted. Sole path: `fire_*_sync()` → `build_sync_plan` → `execute_sync_plan`. |

---

## Active Direction — Phase 210+

Phase 209 closed the last open tech debt item. The system is architecturally clean. The next wave focuses on **documentation hygiene, production deployment foundation, and expanding communication channels**.

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


---

## AI Assistive Layer (Phases 220+)

> [!IMPORTANT]
> Full detail: `docs/core/planning/ai-strategy.md`
>
> Core principle: **Deterministic core = truth. AI = explanation, prioritization, recommendation, drafting.**

| Phase | Title | Key Deliverable |
|-------|-------|----------------|
| 220 | AI Strategy Document | Canonical placement (done — Phase 210) |
| 221 | AI Context Aggregation Endpoints | Composite read endpoints assembling booking/property/financial/task snapshots |
| 222 | Manager Copilot v1 | 7AM morning briefing — explains urgent items, blocked tasks, sync health |
| 223 | Financial Explainer | Confidence tier explanations, reconciliation narration |
| 224 | Guest Messaging Copilot v1 | Context-aware draft replies using booking + property + guest data |
| 225 | AI Audit Trail | Log what AI saw, suggested, who approved, what happened |


---

## Forward Planning — Worker Communication & Escalation Layer

> [!IMPORTANT]
> Full detail: `docs/core/planning/worker-communication-layer.md`

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

**Short-term (Phases 219+):** AI assistive layer — Manager Copilot, Financial Explainer, Guest Messaging Copilot. Alternative: additional channel integrations, CI/CD pipeline, staging environment.

**Medium-term (Phases 220–225):** AI assistive layer — Manager Copilot, Financial Explainer, Guest Messaging Copilot. AI explains and prioritizes; deterministic system executes.

**Long-term:** CI/CD pipeline, staging environment, advanced conflict resolution UX, revenue analytics, Tier 3 adapter expansion, guest-facing pre-arrival flows, multi-language support, mobile PWA.

**Architecture:** The canonical core remains unchanged — `apply_envelope` is still the only write authority. All product layers (including AI) read from or wrap the canonical spine without mutating it.
