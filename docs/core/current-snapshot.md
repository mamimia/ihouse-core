## Current Phase
Phase 1041 — P1: OM Hub and Next-Layer Product Depth

## Last Closed Phase
Phase 1040 — P0: System Closure, Regression, Docs Alignment

## System Status

**[...System status through Phase 958 unchanged...] Phase 979 Guest Dossier & Worker Check-in Hardening: Full Guest Dossier system — `/guests/{guest_id}` backend endpoint with denormalized response (stays, check-in records, portal data), tabbed frontend dossier page (Current Stay, Activity, Contact), timeline-aware status badges (In Stay / Past Stay / Upcoming), compact metadata layout, Guest Portal QR/Send Link actions, full-row clickability on Guest Directory. Worker check-in lifecycle: self-healing mechanism auto-completes orphaned ACKNOWLEDGED tasks via `forceCompleteTask()` state-machine walk when booking is already `checked_in`. Breadcrumb navigation leak suppressed on all mobile staff routes. MobileStaffShell horizontal gutter (`paddingInline: var(--space-4)`). LiveCountdown human-readable tiered format: `>48h→13d`, `24-48h→1d 6h`, `<24h→18h 20m`, `<1h→42m 08s`; adaptive tick rate. Worker Home broken modal removed (source of `worker.btn_complete` i18n token leak) — Next Up cards now navigate to role-specific task flows. Deployed to Railway + Vercel.**

**Phase 1003 Canonical Block Classification & Bookings UX:** Established functional dual-surface Bookings page separating true operating stays from Calendar Blocks. Viewport-safe Status Modal completely replaces fragile popover logic. All sync-based availability rows labeled explicitly with `is_calendar_block = true`.

**Phase 1021 Owner Bridge Flow:** Replaced the misleading "Go to Owners" CTA for role=Owner staff users with a real `LinkOwnerModal`. Modal carries over personal details and all property assignments from the staff record into the owner create/link flow.

**Phase 1022 Operational Manager Takeover Gate:** Full end-to-end task takeover model. `MANAGER_EXECUTING` status in task state machine. Audit chain: `original_worker_id`, `taken_over_by`, `taken_over_reason`, `taken_over_at`. Permission guards: Operational Manager scoped to assigned properties; Admin global fallback. Responsive execution drawer keeps manager on their board surface. All four worker wizards (`CheckinWizard`, `CheckoutWizard`, `CleanerWizard`, `MaintenanceWizard`) extracted and embedded in manager drawer via `TaskWizardRouter`. Build clean. Deployed commit `91f7114`. Staging visual verification pending for next session.

**Phase 1023 Staff Onboarding Error Clarity & Role Integrity:** UNKNOWN_ERROR masking removed — frontend now surfaces real backend error codes. Combined (checkin+checkout) role normalized to `[checkin, checkout]` array. Operational Manager invite route separated from worker sub-role logic.

**Phase 1024 Identity Mismatch & Auth-Email Repair Path:** Hardened auth-email repair flow for cases where staff card email is corrected but auth identity remains on old email. Admin surface surfaces identity mismatch state.

**Phase 1025 Public Property Submission Flow Hardening:** Stale-state blocking in public submission flow fixed. My Properties delete affordance added with confirmation dialog. Intake queue now shows submitter phone.

**Phase 1026 Operational Truth Semantics Lock:** Canonical semantics locked: PENDING includes ACKNOWLEDGED and IN_PROGRESS. COMPLETED and CANCELED excluded from default Pending view at backend level. Applies to all surfaces.

**Phase 1027 Stale Task & Past-Task Hygiene:** Historical task bleed-through fixed. ZTEST- hygiene rule established. `scripts/cleanup_probe_tasks.sql` created.

**Phase 1028 Primary/Backup Model Decision & Baton-Transfer Architecture:** `priority` INTEGER column added to `staff_property_assignments`. Primary/Backup model locked per property + lane. Baton-transfer designed: PENDING tasks may move, ACKNOWLEDGED/IN_PROGRESS tasks must not. INV-1010, INV-1011, INV-1012 locked.

**Phase 1029 Default Worker Task Filter COMPLETED Exclusion Hardened:** `GET /worker/tasks` default now excludes both COMPLETED and CANCELED at backend-canonical level. Regression test A8 added.

**Phase 1030 Task Lifecycle & Assignment Hardening:** All task creation, rescheduling, and baton-transfer paths enforce Primary/Backup model. Amendment reschedule healing, ad-hoc cleaning Primary selection, early-checkout healing, lane-aware baton-transfer, and promotion notice JSONB write all implemented. Commit `7732ab4`. Admin Pending exclusion of COMPLETED tasks staging-proven. INV-1010/1011/1012 extended.

**Phase 1031 Assignment Priority Normalization & Canonical Lane Protection (3 sub-commits):**
- `b5f5e8f` — Code-level gaps closed: early-checkout healing walks priority-ordered candidates (Primary first); backfill Primary-existence guard (Backup cannot steal NULL tasks when Primary exists in lane); ownerless-task guard emits `ERROR OWNERLESS_TASK_CREATED` on all failure paths. 161 tests pass.
- `7dcb4da` — DB + API normalization: `chk_priority_positive` constraint; trigger `fn_guard_assignment_priority_uniqueness` (blocks (property, lane, priority) collision); DB function `get_next_lane_priority()`. API write path now lane-aware: resolves worker lane from `worker_roles`, computes MAX(priority)+1, sets correct priority at insert. UNKNOWN-lane hard block replaces silent priority>=100 path.
- `89d3f45` — Canonical no-lane enforcement: trigger `fn_guard_assignment_requires_operational_lane` blocks INSERT for any worker without cleaner/maintenance/checkin/checkout. Removed 11 invalid rows (manager_not_worker ×8, ghost_no_permission_record ×2, owner_not_worker ×1). Audit table `phase_1031c_removed_assignments` created. DB proofs: invalid_rows=0, all 14 assignment rows in real operational lanes, zero priority collisions.
- Lane model locked: CLEANING / MAINTENANCE / CHECKIN_CHECKOUT only. UNKNOWN is not a valid product concept. No operational assignment without a valid lane.
- INV-1031-A/B/C/D added.

**Phase 1032 — Live Staging Proof + Baton-Transfer Closure (3 sub-commits):**
- `fb5b3ea` — Trigger race fix: `fn_guard_assignment_priority_uniqueness` was blocking baton-transfer promotions. Exempted UPDATE operations from the collision guard — atomic Backup→Primary promotion (priority=1) now succeeds.
- `6eedbda` — `POST /staff/assignments` 500 fix: PostgREST upsert was sending absent `priority` as NULL, violating `chk_priority_positive`. Fixed: `permissions_router.py` always includes `priority` in upsert payload (idempotent for existing rows, lane-aware for new rows).
- `a414a8c` — `GET /permissions/me` added to `permissions_router.py`: returns the caller's own `tenant_permissions` row including `comm_preference._promotion_notice`. Registered before `GET /permissions/{user_id}` to avoid path shadowing. Root cause of silent banner failure — endpoint was 404.
- **Live staging proofs (all confirmed):** baton-transfer E2E (KPG-500: Joey→Backup, แพรวา→Primary), promotion notice JSONB write in DB, `GET /permissions/me` HTTP 200, worker promotion banner visible in `/worker` UI (screenshot), `POST /staff/assignments` existing-row returns 201.
- **Final staging state:** KPG-500 CLEANING lane — แพรวา=Primary (priority=1), Joey=Backup (priority=2). This is a real live state change from the proof pass.
- **Open (not blocking):** promotion notice acknowledgement PATCH not built; legacy KPG-500 task distribution is pre-guard artifact, not a current write-path failure.

**Phase 1033 — Canonical Task Timing Hardening (+ OM Surface, Act As, Staff Onboarding):**
Implementation landed across multiple workstreams. Documentation closure was incomplete — now completed.
- **Worker Timing Gate Model (BUILT + STAGING-PROVEN):** `src/tasks/timing.py` — `compute_task_timing()`: `effective_due_at`, `ack_allowed_at` = due−24h, `start_allowed_at` = due−2h. CRITICAL priority bypasses all gates unconditionally. MAINTENANCE/GENERAL: no start gate. `due_time` kind-defaults written at task creation (`_KIND_DUE_TIME` map) and preserved on amendment reschedule. Worker router enriches every task response with 4 timing fields; `/acknowledge` and `/start` enforce hour-level UTC gates; structured errors `ACKNOWLEDGE_TOO_EARLY` / `START_TOO_EARLY` with `opens_in`.
- **Server-Driven Frontend Gates (BUILT + STAGING-PROVEN for checkin/checkout):** `WorkerTaskCard.tsx` — `AckButton` + `StartButton` components read server-provided fields. "Opens in Xh Ym" flash on early press (3s then revert). `computeOpensIn()` replaces local date math. All 3 worker op pages (`cleaner`, `checkout`, `checkin`) extended with 4 timing props threaded to `WorkerTaskCard`. Maintenance timing gate: BUILT but staging proof 🔲 (no live task available during session).
- **Operational Manager Surface (BUILT, SURFACED — not screenshot-proven):** OM shell + 6-page navigation (Hub, Alerts, Stream, Team, Bookings, Calendar). Hub is cockpit-first: Alert rail → Metrics → Task Board → Stream. `task_takeover_router.py` expanded: `/manager/alerts`, `/manager/team-overview`, `/tasks/{id}/notes` endpoints. `DraftGuard` on all OM draft pages (admin-only access while surface matures). Team page: real data — property names, lane coverage matrix, worker roster.
- **Person-Specific Act As / Preview As (BUILT, SURFACED — not screenshot-proven):** Both surfaces carry `name` + `user_id` query params. Banners display "Role · [Person Name]". `checkin_checkout` dual-role validation fixed (requires BOTH checkin AND checkout). Auth fixes: `/act-as` + `/preview` added to `PUBLIC_PREFIXES`; `apiFetch` logout on 401 only (never 403).
- **Staff Onboarding Hardening (BUILT, SURFACED — not screenshot-proven):** Manager role validation, canonical role lock enforced, approval history always visible, Work Permit rule, combined checkin+checkout tile.
- **Product Decision Locked:** OM task model. Worker layer = Acknowledge/Start/Complete. Manager layer = Monitor/Takeover/Reassign/Note. `ManagerTaskCard` as drill-down intervention layer only. Phase 1034 (OM-1) spec approved — not yet built.
- **INV-1033-TIMING:** `ack_allowed_at` = `effective_due_at` − 24h; `start_allowed_at` = `effective_due_at` − 2h. CRITICAL bypasses all gates. Frontend timing state is derived exclusively from server-provided fields — no local computation.
- Commits: `305a083` → `e79adb2` (OM surface + Act As + staff onboarding), `cd8a04a`, `1480f03` (timing model). Branch: `checkpoint/supabase-single-write-20260305-1747`.

## Deferred Items — Managed Open Items Registry

> Items deferred from closed phases. Each item must specify: status, reason, unblock condition, and planned resolution phase.
> This section must be reviewed and updated at every phase closure.

| Phase | Title | Status | Reason | Unblock Condition | Planned Phase |
|-------|-------|--------|--------|-------------------|---------------|
| 614 | Pre-Arrival Email (SMTP) | 🟡 Deferred | Requires live SMTP configuration | `SMTP_HOST/PORT/USER/PASS` env vars configured + verified | TBD — when email infra provisioned |
| 617 | Wire Form → Checkin Router | 🟡 Deferred | Requires live booking flow | Real check-in data flowing through `booking_checkin_router.py` | TBD — when live check-in activated |
| 618 | Wire QR → Checkin Response | 🟡 Deferred | Requires live booking flow (same as 617) | Same as Phase 617 | TBD — together with Phase 617 |
| — | Supabase Storage Buckets (5) | ✅ Resolved (Phase 764) | 4 buckets created: pii-documents, property-photos, guest-uploads, exports | N/A | Resolved |
| 857-F1 | Staff photo bucket migration | ✅ Resolved (Phase 863) | All files migrated to `staff-documents`. Upload routing fixed. Signed URLs implemented. DB references updated. | N/A | Resolved |
| 857-F2 | Full email click-through activation proof | 🟡 Pending | Supabase sent invite email to `phase857-test@domaniqo.com`. No real inbox available to verify click-through. | Human inbox verification of full activation flow | TBD |
| 857-F3 | Pipeline A runtime proof (role validation, generate_link lookup, is_active) | ✅ Closed | All three items runtime-proven on staging | N/A | Resolved |
| 859-F1 | Property URL extraction (scraping) | 🟡 Stub | UI field exists in Get Started wizard. No real scraping engine behind it — requires OTA API keys or reverse engineering. | OTA API access or headless scraping implementation | TBD |


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
| 375–380 | Platform Surface Consolidation Wave 1 — route group split, AdaptiveShell, tokens, ThemeProvider, login redesign, landing page, early-access, SEO | ✅ |
| 381–385 | Platform Surface Consolidation Wave 2 — responsive adaptation for 15+ pages (auto-fit grids, scroll wrappers) | ✅ |
| 386 | Mobile Ops Command Surface — stat grid, task feed, arrivals/departures from real endpoints | ✅ |
| 387 | Check-in/Check-out/Maintenance Mobile — 3 field-staff pages. Maintenance is E2E real; checkin/checkout read-only | ✅ |
| 388 | Access-Link System Foundation — guest/invite/onboard token pages (UI only, no backend endpoints) | ✅ |
| 389 | Worker Brand Alignment + 5 Shared Components (StatusBadge, DataCard, TouchCard, DetailSheet, SlaCountdown) — created but unused | ✅ |
| 390 | Checkpoint C — TypeScript 0 errors | ✅ |
| 391 | Property Onboarding Remote Flow — auto-closed (delivered in 388) | ✅ |
| 392 | Role-Based Entry Routing — roleRoute.ts (non-functional: JWT has no role claim) | ✅ |
| 393 | Platform Polish — verification sweep (IDs, fonts, emails) | ✅ |
| 394 | Platform Checkpoint XX — full multi-surface audit, 28 pages, TypeScript 0 errors | ✅ |
| 395 | Property Onboarding QuickStart + Marketing Pages | ✅ |
| 396 | Property Admin Approval Dashboard — 5 endpoints, 21 tests | ✅ |
| 397 | JWT Role Claim + Route Enforcement — role in JWT, middleware, 14 tests | ✅ |
| 398 | Checkin + Checkout Backend — POST /bookings/{id}/checkin + /checkout, 10 tests | ✅ |
| 399 | Access Token System Foundation — HMAC-SHA256 tokens, admin router, 12 tests | ✅ |
| 400 | Guest Portal Backend — GET /guest/portal/{token}, PII-scoped, 6 tests | ✅ |
| 401 | Invite Flow Backend — create/validate/accept, fixed UI deception, 6 tests | ✅ |
| 402 | Onboard Token Flow — validate + submit, pending_review, 6 tests | ✅ |
| 403 | E2E + Shared Component Adoption — 6 E2E tests, DataCard in dashboard | ✅ |
| 404 | Property Onboarding Pipeline — approve → channel_map bridge, 4 tests | ✅ |
| 855E | Onboarding Pipeline Audit — full current-state audit of Pipeline A/B, cross-pipeline conflict analysis | ✅ |
| 857 | Onboarding Remediation Wave — 7 critical fixes (runtime-proven on staging) | ✅ |
| 857.1 | `tenant_bridge.py` — explicit `is_active=True` on provision (audit D8) | ✅ |
| 857.2 | `invite_router.py` — role validation via `_VALID_ROLES` at accept time (audit B6) | ✅ |
| 857.3 | `invite_router.py` — replaced O(N) `list_users()` with `generate_link` lookup (audit B2) | ✅ |
| 857.4 | `staff_onboarding_router.py` — auto-delivery via `invite_user_by_email` (audit C1/C2/C6) | ✅ Runtime-proven |
| 857.5 | `staff_onboarding_router.py` — removed legacy `invite` type from Pipeline B (audit C3) | ✅ Runtime-proven |
| 857.6 | DDL migration — `date_of_birth` + `id_photo_url` columns on `tenant_permissions` (audit C8) | ✅ Runtime-proven |
| 857.7 | `staff_onboarding_router.py` — clear `410 APPLICATION_REJECTED` for rejected candidates (audit C9) | ✅ Runtime-proven |
| 857.8 | DB constraint fix — `access_tokens_token_type_check` updated to include `staff_onboard` (bug found during runtime verification) | ✅ Applied + committed |
| 858 | Product Language Correction + Google Auth Path Separation | ✅ |
| 859 | Admin Intake Queue + Property Submit API + Login UX + Draft Expiration | ✅ |

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

## OTA Adapters — 15 (14 unique + ctrip alias)

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

Phase 345 — see `docs/core/planning/` for next cycle.

**Phase 1034 — OM-1 Manager Task Intervention Model (CLOSED):** `POST /tasks/{id}/takeover-start` (timing-gate bypass, atomic walk, audit), `POST /tasks/{id}/reassign` (property-scoped workers, handoff note), `POST /tasks/{id}/notes` (source-typed), `ManagerTaskCard.tsx` + `ManagerTaskDrawer` (read-only timing strip, Takeover/Reassign/Note), `ReassignPanel` (named workers, kind-filtered). `jwt_auth` vs `jwt_identity` bug fixed. `task_id`/`id` field normalized. Backend-proven in DB. End-to-end UI proof pending.

**Phase 1035 — OM-1 Stream Redesign (CLOSED — Backend Proven):** Data source migrated from `audit_events` to live `tasks` + `bookings` tables. Tasks tab: `GET /manager/tasks` (live operational queue, urgency sort). Bookings tab: `GET /manager/stream/bookings` (yesterday → +7d, confirmed only). Sessions tab: removed. Human-first property naming enforced everywhere. Property name resolution bug fixed: backend was joining `properties.id` (bigint) instead of `properties.property_id` (text). `ReassignPanel` empty state fixed. DB SQL proofs pass. UI visual proof pending.

**Phase 1036 — OM-1: Stream Hardening (CLOSED):** `POST /tasks/adhoc` — generic ad-hoc task creation (CLEANING/MAINTENANCE/GENERAL), CHECKIN_PREP/CHECKOUT_VERIFY blocked, duplicate guardrail (409 + `?force=true` override), lane-aware auto-assign, audit log. Stream: canonical ordering (CHECKOUT→CLEAN→CHECKIN within same property+day), `KindSequenceBadge`, Add Task button in header wired to `/tasks/adhoc`, conflict guardrail UI, scope-aware booking empty state. Build clean. Deployed `054c83a`.

**Phase 1037 — Staff Onboarding Access Hardening (CLOSED):** Resolves the staff onboarding 500 error and email deliverability chain. Four sub-commits on branch `checkpoint/supabase-single-write-20260305-1747`:
- **1037a** `POST /admin/staff`: New manual create endpoint provisions a real Supabase Auth UUID via `generate_link(type=invite)` before writing `tenant_permissions`. Identity invariant: `comm_preference.email == auth_email` always maintained.
- **1037b** SMTP bypass: switched from `invite_user_by_email` (sends spam-prone Supabase email) to `generate_link` (returns raw URL, no email sent). Admin sees copyable link + ✉ Email button in success overlay.
- **1037c** True hard delete: `DELETE /admin/staff/{user_id}` atomically removes from `tenant_permissions`, `staff_assignments`, AND `auth.users` (via `admin.delete_user()`). Previously only `tenant_permissions` was removed, leaving orphaned auth records that blocked re-invite.
- **1037d** Bulletproof two-pass auth: Pass A = `generate_link(type=invite)` for new users; Pass B = `generate_link(type=magiclink)` for any existing-user signal (7 error variants including 422, 'in use', 'duplicate'). Last resort: `422 USER_ALREADY_EXISTS` with clear human message — never a raw 500. Orphaned `esweb3@gmail.com` auth record cleaned from `auth.users` directly.

**Phase 1038 — Supervisory Role Assignment Hardening (CLOSED):** Fixes root cause of OM assignment failure. `POST /staff/assignments` was applying worker-lane validation to supervisory roles — now bypasses for manager/admin/owner with `priority=100`. `GET /staff/property-lane/{id}` returns `supervisors[]` alongside worker lanes. Frontend property rows branch on role: supervisory → supervisor name chips (👤 Name); workers → Primary/Backup badges unchanged. Real backend errors surfaced in UI (`apiFetch` reads body before throw; `handleSave` catch uses `e.message`). Orphaned `0330` rows cleaned. Commit `b4150cf`.

**Phase 1038b — Mobile Stream Responsive Hardening + Multi-Supervisor Chips (CLOSED):** (1) `activeTab` persisted to `sessionStorage` — survives orientation change/resize, no more Bookings→Tasks reset. (2) `BookingRow` isMobile prop: mobile portrait renders vertical card layout (3 rows); desktop unchanged. (3) Supervisor chip strip shows ALL supervisors for property — first 2 as chips, `+N` overflow, current user highlighted purple. `No supervisor yet` only when truly empty. Commit `eae8705`.

**Phase 1039 — OM Role & Assignment Inline Help (CLOSED):** Two UI additions to `[userId]/page.tsx`: (1) OM info block — renders when `role === 'manager'`, explains supervisory scope model in 5 bullets (what OM is, multi-villa, multi-OM, no Primary/Backup, what chips mean). (2) Supervisory context note — renders for manager/admin, placed above Assigned Properties list. UI-only change. TypeScript 0 errors. Staging proof captured on Nana G (Operational Manager) — desktop + mobile. Commits `cb51bf8` (code) + `22c8815` (spec closed).

**Phase 1040 — P0: System Closure, Regression, Docs Alignment (CLOSED):** Docs aligned: Phase 1039 closed in current-snapshot, work-context, phase sequence. Regression pass on staging — 4 tests / 5 items, all PASS: OM assignment save (Test 1a), supervisor chips render (Test 1b), specific backend error message not generic (Test 2), mobile Bookings portrait card layout (Test 3), Bookings tab retained after orientation change (Test 4). Phase 1037 spec annotated (Part A = planning-only, Part B = delivered). Anti-Gravity troubleshooting note confirmed in docs. Commit `7703f39`.

## Operational Troubleshooting Note

> **Anti-Gravity workspace freeze root cause (2026-04-02):** `.git/config` contained `extensions.worktreeconfig=true` which caused Anti-Gravity to become silent/unresponsive inside this repo. Fixed by: `git config --local --unset extensions.worktreeconfig`. **Do not reintroduce this setting.** If Anti-Gravity becomes silent again inside this repo, check `.git/config` first.


## Tests

**8,144 passed, 18 failed (pre-existing mock stubs — wave7 takeover + guest_owner_auth), 22 skipped. TypeScript 0 errors. 294 test files. 126 API router files. 63 frontend pages. 48 RLS-protected tables. 6 storage buckets. Phases 981–1040 closed. Active: Phase 1041.**

> ⚠️ The 18 failures are pre-existing test mock mismatches in `test_wave7_manual_booking_takeover.py` (8), `test_guest_owner_auth.py` (1), `test_task_system_e2e.py` (1), `test_task_writer_contract.py` (1) — none introduced by Phase 1038/1038b. Tracked for repair in next test hardening pass.


## Environment Variables (continued)

| Var | Default | Effect |
|-----|---------|--------|
| `IHOUSE_ACCESS_TOKEN_SECRET` | required | HMAC-SHA256 secret for access tokens (Phase 399) |
