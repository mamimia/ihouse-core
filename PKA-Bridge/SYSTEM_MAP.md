# System Map

Truthful map of the iHouseCore repository as it exists on 2026-03-28.

Confidence labels used throughout:
- **[PROVEN]** — Directly read in source code or migrations
- **[INFERRED]** — Strongly implied by code patterns and documentation
- **[PARTIAL]** — Code exists but incomplete or not fully wired
- **[CLAIMED]** — Stated in documentation but not independently verified in code

---

## 1. What This System Is

**[PROVEN]** iHouseCore is a multi-tenant short-term rental property management backend and frontend. It is the internal system name. The external product brand is **Domaniqo**.

**[PROVEN]** It is designed for:
- Property managers and operators who manage short-term rental properties listed on platforms like Airbnb, Booking.com, Expedia, and others
- Field staff (cleaners, check-in agents, maintenance workers) who execute daily operational tasks
- Property owners who want financial visibility into their properties
- Guests who need a portal to access their booking details during a stay

**[PROVEN]** The core architectural commitment is **event sourcing with a deterministic kernel**:
- All state changes flow through a single write gate: `apply_envelope`
- The event log is append-only and immutable
- `booking_state` is a derived projection — it is never written to directly
- Financial data is kept in a separate projection (`booking_financial_facts`) and never mixed into booking state

**[PROVEN]** Supabase is the canonical persistence layer for production. SQLite exists as a local dev fallback.

---

## 2. Repository Layout

```
ihouse-core/
  src/                    Python backend (FastAPI)
    api/                  126 router files
    adapters/
      ota/                14+ OTA-specific adapters
      outbound/           4 outbound sync adapters
      pms/                Guesty PMS adapter (deferred)
    core/                 Event engine, ports, executor, runtime
    services/             Domain services (auth, roles, tasks, financials, etc.)
    tasks/                Task model, writer, automator, SLA engine
    channels/             Notification dispatchers (LINE, WhatsApp, Telegram, SMS, Email)
    i18n/                 Internationalization (EN, TH, HE)
    middleware/           Act-as attribution, preview mode, security headers
    schemas/              Response models
  ihouse-ui/              Next.js 16 / React 19 frontend
    app/
      (public)/           Unauthenticated routes (guest portal, onboarding, landing)
      (auth)/             Authentication flows (login, register, reset)
      (app)/              Authenticated staff/admin routes
        admin/            Admin panels (25+ sub-routes)
        ops/              Field operations (checkin, checkout, cleaner, maintenance)
        worker/           Worker role landing page
        tasks/            Task board
        dashboard/        Admin/manager dashboard
        owner/            Owner financial view
  docs/                   Multi-layer documentation system
    core/                 System identity, vision, governance, current state
    vision/               Product vision and gap analysis
    architecture/         Architecture notes
    product/              Product feature specs
    ops/                  Operational runbooks
  supabase/
    migrations/           26 Supabase-format migrations (Phase 39–947)
  migrations/             18 legacy SQL migrations (Phase 135–868)
  domaniqo-site/          Static marketing website (separate from main app)
  .agent/                 AI agent working context and skills
  artifacts/              Backup files, audit notes, phase skill audits
```

---

## 3. Backend Architecture

### Event Kernel

**[PROVEN]** The system has a strict event-sourced kernel:

```
External event (OTA webhook)
  → OTA adapter (provider-specific normalization)
  → Pipeline (6-phase validation: boundary → normalize → structural → semantic classify → semantic validate → canonical envelope)
  → CoreExecutor.execute()
  → EventLogPort.append_event() [immutable write]
  → Skill execution (kind_registry → skill_exec_registry)
  → apply_envelope RPC [Supabase function, updates booking_state]
  → StateStore.commit()
```

**[PROVEN]** Internal events (check-in, check-out, manual booking) also write through `apply_envelope` or equivalent controlled write paths.

**[PROVEN]** The skill registry maps event kinds to Python modules:
- `BOOKING_CREATED` → booking_created skill
- `BOOKING_CANCELED` → booking_canceled skill
- `BOOKING_AMENDED` → booking_amended skill
- `BOOKING_CONFLICT` → conflict resolver skill
- `sla-escalation-engine` → SLA engine skill
- `state-transition-guard` → state transition validator
- `task-completion-validator` → task completion validator

### FastAPI Application

**[PROVEN]** `src/main.py` mounts 53+ routers with explicit ordering rules (financial-specific routes must come before the financial catch-all).

**[PROVEN]** Middleware stack (in order):
1. CORS
2. Security Headers
3. Preview Mode (read-only enforcement for admin-preview-as sessions)
4. Act As Attribution (mutation tracking for admin-act-as sessions)
5. Response Envelope exception handlers

**[PROVEN]** Scheduler runs background tasks on startup (`start_scheduler()`) — this drives SLA monitoring and scheduled jobs.

### OTA Integration

**[PROVEN]** 14 unique OTA adapters (15 with Ctrip alias for Trip.com):

Tier 1 (major global): Airbnb, Booking.com, Expedia
Tier 1.5 (major Asia): Agoda, Traveloka
Tier 2 (significant): Trip.com/Ctrip, Vrbo, Google Vacation Rentals, MakeMyTrip, Klook, Despegar, Rakuten
Tier 3 (niche): Hotelbeds, Hostelworld

**[PROVEN]** All 14 support BOOKING_CREATED, BOOKING_CANCELED, BOOKING_AMENDED.

**[PROVEN]** Outbound sync (push back to OTAs via iCal RFC 5545) exists for: Airbnb, Booking.com, Expedia, Vrbo.

### Database Schema (Key Tables)

**[PROVEN]** Core tables confirmed in source and migrations:

| Table | Purpose |
|-------|---------|
| `event_log` | Immutable event stream (source of truth) |
| `booking_state` | Derived projection (operational read model) |
| `booking_financial_facts` | Financial projection (never in booking_state) |
| `booking_flags` | Operator annotations (VIP, disputed, review) |
| `tenant_permissions` | RBAC (role, capabilities, comm_preference JSONB) |
| `tasks` | Task queue with SLA and assignment tracking |
| `properties` | Property metadata |
| `property_channel_map` | OTA channel mapping per property |
| `guest_checkin_forms` | Check-in form master |
| `guest_checkin_guests` | Guest roster per form |
| `guest_deposit_records` | Cash deposit records and signatures |
| `guest_qr_tokens` | Short QR tokens for pre-arrival forms |
| `guest_tokens` | HMAC guest portal token hashes |
| `notification_channels` | Worker notification preferences (LINE/WhatsApp/etc.) |
| `notification_delivery_log` | Delivery history |
| `access_tokens` | Invite and onboarding tokens |
| `intake_requests` | Property intake funnel submissions |
| `acting_sessions` | Admin "Act As" session audit trail |
| `ota_dead_letter` | Failed OTA webhook events for replay |
| `staff_property_assignments` | Worker-to-property mapping |
| `cleaning_task_progress` | Checklist state per cleaning task |
| `cleaning_photos` | Photos per cleaning task |
| `identity_repair_log` | Audit trail of worker identity fixes |

---

## 4. Frontend Architecture

**[PROVEN]** Next.js 16 / React 19 app located in `ihouse-ui/`.

**[PROVEN]** Route groups:
- `(public)` — unauthenticated pages (guest portal, onboarding, invite acceptance, landing)
- `(auth)` — authentication flows
- `(app)` — authenticated staff and admin surfaces (uses `AdaptiveShell` layout)

**[PROVEN]** Two separate API client modules with different token storage — these must not be mixed:
- `lib/api.ts` — reads from `localStorage`. Used by admin/manager surfaces.
- `lib/staffApi.ts` — reads from `sessionStorage` first (Act As isolation), then `localStorage`. Used by all ops/worker surfaces.
- Mixing the two causes silent 401 errors (confirmed staging incident 2026-03-26).

**[PROVEN]** Authentication layers:
- Edge: `middleware.ts` enforces route access by role, checks JWT expiry, deactivation, and force-reset at every request
- Client: `api.ts` auto-logs out on 401/403 (except CAPABILITY_DENIED and PREVIEW_READ_ONLY)
- Tab isolation: Act As sessions live in `sessionStorage` only; admin `localStorage` is never touched by Act As

**[PROVEN]** Internationalization: EN, TH, HE supported. Hebrew uses RTL (opt-in per surface).

**[PROVEN]** Theming: Global light default. Mobile staff shell forces dark theme. Admin layout is light (Phase 957 removed per-component overrides).

**[PROVEN]** Key UI surfaces and their actual state (read directly):

| Route | Designed for | Actual state |
|-------|------------|--------------|
| `/dashboard` | Admin, Manager, Owner (limited), Workers (limited) | Functional — stats, tasks, sync health, DLQ |
| `/manager` | Manager | Functional — audit trail feed + morning briefing copilot |
| `/admin` (the page itself) | Admin | Functional — integrations config (LINE, WhatsApp, OTA credentials) |
| `/admin/managers` | Admin | Functional — per-manager capability toggles |
| `/admin/owners` | Admin | Functional — owner CRUD with property assignment |
| `/admin/staff` | Admin | Functional — staff roster with role/sub-role display |
| `/admin/intake` | Admin | Functional — intake review queue with approve/reject |
| `/admin/settings` | Admin | Functional — property ID prefix configuration |
| `/admin/portfolio` | Admin | Functional (display-only) — cross-property overview |
| `/admin/more` | Admin | Navigation hub — links to sub-pages |
| `/ops` | Ops, Workers | Functional — today's stats + links to ops hubs |
| `/ops/checkin` | Check-in worker | Functional UI (6 steps with real data), storage wiring partial |
| `/ops/checkout` | Check-out worker | Functional UI (4 steps), built |
| `/ops/cleaner` | Cleaner | Functional UI with checklist |
| `/ops/maintenance` | Maintenance | Functional UI — calls `/worker/tasks` and `/problem-reports` |
| `/ops/checkin-checkout` | Combined role | Functional hub — navigation to /ops/checkin and /ops/checkout with live task counts |
| `/worker` | All workers | Functional role router with countdown |
| `/tasks` | Workers, Admin | Functional task board with SLA countdown |
| `/owner` | Owner | Functional financial summary |
| `/financial` | Admin (capability-gated) | Functional — provider/property breakdown, lifecycle chart |
| `/financial/statements` | Admin (capability-gated) | Functional — line items, CSV/PDF/email export |
| `/guest/[token]` | Guest (public) | Functional multi-section portal |
| `/invite/[token]` | New staff (public) | Functional invite acceptance |
| `/onboard/[token]` | New property owner (public) | Functional onboarding form |

---

## 5. Role Model

**[PROVEN]** Canonical roles (defined in `src/services/canonical_roles.py` as the single source of truth):

| Role | Type | Description |
|------|------|-------------|
| `admin` | Staff | Full tenant governance. Cannot be created via invite. |
| `manager` | Staff | Operational management. Can receive delegated capabilities. |
| `ops` | Staff | Operations team member with broader surface access. |
| `owner` | External | Property owner. Read-only financial visibility. |
| `worker` | Field | General field staff. Task-assignable. |
| `cleaner` | Field | Housekeeping. Routed to `/ops/cleaner`. |
| `checkin` | Field | Check-in agent. Routed to `/ops/checkin`. |
| `checkout` | Field | Check-out agent. Routed to `/ops/checkout`. |
| `maintenance` | Field | Maintenance technician. Routed to `/ops/maintenance`. |
| `identity_only` | System | Authenticated user with no tenant membership yet. |

**[PROVEN]** Key authorization rules:
- DB-stored role always wins over client-declared role
- Admin cannot be provisioned via invite
- Signup creates identity only — no auto-provisioning to tenant
- Unknown roles default to NONE (reject, don't promote)

**[PROVEN]** Delegated capabilities (for `manager` role only):

| Capability | Meaning |
|-----------|---------|
| `financial` | View/export financial reports and owner statements |
| `staffing` | Invite/deactivate workers, manage schedules |
| `properties` | Edit property details, manage listings |
| `bookings` | Modify bookings, handle cancellations |
| `maintenance` | Approve maintenance requests, assign priorities |
| `settings` | Edit tenant settings |
| `intake` | Review and approve intake requests |

**[PROVEN]** Worker sub-roles (within the `worker` role, stored in `tenant_permissions.permissions.worker_roles[]`):
- `cleaner` → CLEANING tasks
- `checkin` → CHECKIN_PREP tasks
- `checkout` → CHECKOUT_VERIFY tasks
- `maintenance` → MAINTENANCE tasks

**[PROVEN]** Route access by role — read directly from `middleware.ts`:

| Route prefix | admin | manager | ops | owner | worker | cleaner | checkin | checkout | maintenance | identity_only |
|---|---|---|---|---|---|---|---|---|---|---|
| `/dashboard` | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ | ✓ | — |
| `/admin/*` | ✓ | ✓ | — | — | — | — | — | — | — | — |
| `/owner` | ✓ | ✓ | — | ✓ | — | — | — | — | — | — |
| `/bookings` | ✓ | ✓ | ✓ | — | — | — | — | — | — | — |
| `/tasks` | ✓ | ✓ | ✓ | — | ✓ | — | ✓ | ✓ | ✓ | — |
| `/calendar` | ✓ | ✓ | ✓ | — | — | — | — | — | — | — |
| `/guests` | ✓ | ✓ | ✓ | — | — | — | — | — | — | — |
| `/worker` | ✓ | ✓ | — | — | ✓ | ✓ | — | — | ✓ | — |
| `/ops` | ✓ | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| `/ops/checkin` | ✓ | ✓ | ✓ | — | ✓ | — | ✓ | — | — | — |
| `/ops/checkout` | ✓ | ✓ | ✓ | — | ✓ | — | — | ✓ | — | — |
| `/ops/maintenance` | ✓ | ✓ | ✓ | — | ✓ | — | — | — | ✓ | — |
| `/checkin` | ✓ | ✓ | — | — | ✓ | — | ✓ | — | — | — |
| `/checkout` | ✓ | ✓ | — | — | ✓ | — | — | ✓ | — | — |
| `/maintenance` | ✓ | ✓ | — | — | ✓ | — | — | — | ✓ | — |
| `/welcome`, `/profile` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `/get-started`, `/my-properties` | Public + ✓ identity_only | | | | | | | | | ✓ |

Notes from middleware.ts:
- `cleaner` role cannot reach `/dashboard` directly (restricted to `/worker`, `/ops`)
- `owner` can reach `/dashboard` but cannot reach any `/admin/*` or `/ops/*` routes
- `ops` role has broader access than any individual field role: dashboard, bookings, tasks, calendar, guests, ops
- `checkin_checkout` combined role routes to `/ops/checkin-checkout` (confirmed in `roleRoute.ts`)

---

## 6. Task System

**[PROVEN]** Six task kinds:
- `CLEANING` — post-checkout housekeeping
- `CHECKIN_PREP` — pre-arrival preparation
- `CHECKOUT_VERIFY` — inspection before departure
- `MAINTENANCE` — repairs
- `GENERAL` — catch-all
- `GUEST_WELCOME` — pre-arrival guest onboarding

**[PROVEN]** Task state machine:
```
PENDING → ACKNOWLEDGED → IN_PROGRESS → COMPLETED
PENDING → CANCELED
ACKNOWLEDGED → CANCELED
IN_PROGRESS → CANCELED
```

**[PROVEN]** SLA acknowledgement windows:
- CRITICAL: 5 minutes (locked, never changes)
- HIGH: 15 minutes
- MEDIUM: 60 minutes
- LOW: 240 minutes

**[PROVEN]** Task automation (triggered by booking events):
- `BOOKING_CREATED` → auto-generates CHECKIN_PREP + CLEANING + CHECKOUT_VERIFY tasks
- `BOOKING_CANCELED` → cancels PENDING tasks
- `BOOKING_AMENDED` → reschedules affected tasks

**[PROVEN]** Task IDs are deterministic: `sha256(kind:booking_id:property_id)[:16]` — idempotent on retry.

**[PROVEN]** Staff task backfill (Phase 888, LOCKED):
- When worker assigned to property: future PENDING tasks with matching role → assigned to worker
- ACKNOWLEDGED+ tasks are never touched

---

## 7. Check-in Flow (Actual State)

**[PROVEN]** Backend check-in endpoint (`POST /bookings/{booking_id}/checkin`) is functional:
- Transitions booking status to `checked_in`
- Auto-issues 30-day HMAC guest token
- Sets `properties.operational_status` → `occupied`
- Writes audit events

**[PROVEN]** Guest check-in form backend exists with full endpoint suite:
- Form creation, guest adding, passport photo URL recording, deposit collection, signature capture, QR generation

**[PARTIAL]** Frontend check-in flow (`/ops/checkin`) is a 6-step wizard that renders correctly with real data, but:
- Passport capture: `DEV_PASSPORT_BYPASS` flag still active in staging — camera not wired to storage
- Deposit: UI renders but persistence not confirmed wired
- Messaging (welcome step): Buttons exist, backend integration not confirmed

**[PROVEN]** Guest identity capture (`/worker/documents/upload` + `/worker/checkin/save-guest-identity`) exists and is functional. Document-verified identity canonically overrides booking name.

---

## 8. Guest Portal Flow (Actual State)

**[PROVEN]** Token-gated guest portal is functional:
- HMAC-SHA256 signed token, hash-only storage, constant-time comparison
- Multi-section portal: Wi-Fi, house rules, appliance instructions, contact, location, messaging
- Multi-language UI label endpoint exists

**[PROVEN]** Guest can send messages to host via the portal. Messages stored in `guest_chat_messages`, SSE notification to manager.

**[PARTIAL]** Guest extras catalog is mentioned in the portal schema (`extras_available` field) but the extras catalog backend is noted as 0% implemented in the gap analysis.

---

## 9. Notification Architecture

**[PROVEN]** Five claimed escalation channels. **Actual live API integration status:**

| Channel | Status | Evidence |
|---------|--------|---------|
| In-app (SSE) | [PROVEN live] | SSE broker wired, 6 named channels |
| LINE | [PROVEN live] | `notification_dispatcher.py` calls `api.line.me/v2/bot/message/push` with tenant credentials |
| Telegram | [PROVEN live] | `notification_dispatcher.py` calls `api.telegram.org/bot{token}/sendMessage` |
| WhatsApp | [PARTIAL] | Adapter exists in dispatcher, API URL is in comments as "future: graph.facebook.com/..." — not wired |
| FCM | [STUB] | Adapter present but is a no-op stub |
| Email (notifications) | [STUB] | Adapter present but is a no-op stub |
| SMS | [STUB] | Adapter present but is a no-op stub |

**[PROVEN]** No global fallback chain. Each worker has an explicit `channel_type` in `notification_channels`. Dispatcher routes to that channel only. If the registered channel fails, others are not tried.

**[PROVEN]** SLA escalation targets are resolved by role: `ops` target maps to `role IN ('worker', 'manager')` in `tenant_permissions`. `admin` target maps to `role = 'admin'`.

**[PROVEN]** SLA sweep runs every 120 seconds (configurable via `IHOUSE_SLA_SWEEP_INTERVAL_S`). Queries up to 500 tasks per run.

**[PROVEN]** Scheduler background jobs:
- SLA sweep: every 2 minutes
- DLQ threshold alert: every 10 minutes
- Health log: every 15 minutes
- Pre-arrival scan: daily at 06:00 UTC (creates CHECKIN_PREP + GUEST_WELCOME tasks for bookings 1–3 days out)
- iCal resync: every 15 minutes (primary intake path for iCal-based channels)

---

## 10. Financial Architecture

**[PROVEN]** Six-ring financial model:
1. Extraction (gross, net, commission per OTA)
2. Persistence (7 payment lifecycle states)
3. Aggregation (portfolio dashboards, OTA revenue mix)
4. Reconciliation (stale/missing payment detection)
5. Cashflow (weekly buckets, 30/60/90-day projection)
6. Owner Statement (line items, PDF export)

**[PROVEN]** Hard invariants:
- `booking_state` never contains financial data
- `OTA_COLLECTING` net never included in owner totals
- Management fee applied after OTA commission

---

## 11. AI Copilot Layer

**[PROVEN]** AI copilot endpoints exist and are registered in `main.py`:
- Morning briefing (5 languages)
- Financial anomaly explainer
- Task recommendations with LLM rationale
- Anomaly alerts (cross-domain health scan)
- Guest message draft (6 intents, 5 languages, 3 tones)
- Worker assist (contextual field card)
- AI audit log

**[PROVEN]** LLM is optional — heuristic fallback is always available. `OPENAI_API_KEY` gates the LLM overlay.

---

## 12. What Appears Complete

- Event-sourced booking kernel with 14 OTA adapters
- Financial layer (6 rings, extraction through owner statement)
- Task automation + SLA escalation system
- Role and permission model (canonical, DB-authoritative)
- Two staff onboarding pipelines (invite + self-apply)
- Admin preview-as and act-as architecture
- Guest HMAC token system
- Outbound sync to 4 OTAs via iCal
- Multi-language support (EN, TH, HE)
- Staging deployment (Vercel + Railway + Supabase)
- Auth: email/password + Google OAuth, E2E proven on staging
- Admin UI (intake queue, staff roster, booking management, analytics, DLQ)
- Worker home with role-aware routing
- Task board with SLA countdown
- Ops dashboard (arrivals/departures/SLA breaches)
- Guest portal (token-gated, multi-section, messaging)
- Owner financial dashboard

---

## 13. What Is Partial

- **Check-in 6-step flow** — Renders correctly. Backend endpoints exist. Passport storage wiring disabled (DEV_BYPASS). Deposit persistence not confirmed. Messaging buttons not wired.
- **Cleaning checklist** — Backend checklist router (Phase 626–632) is built. Frontend cleaner page exists. Connection between them is unclear from reading alone.
- **Check-out flow** — 4-step UI exists at `/ops/checkout`. Backend check-out endpoint exists. The internal linkage (inspection record, deposit settlement, cleaning task trigger) is not fully confirmed.
- **Staff property assignment UI** — Backend `staff_property_assignments` table exists. Route `/admin/staff` exists. Property-to-worker assignment surface is described as a gap in the gap analysis.
- **Worker notification channel config** — Backend `notification_channels` table and endpoints exist. UI surface for configuring per-worker channel preference is not confirmed built.

---

## 14. What Is Missing (Per Gap Analysis Documentation)

The following are gaps stated in `docs/vision/system_vs_vision_audit.md`. These were not independently verified in code — treating as **[CLAIMED]** until verified:

- **Problem reporting** — 0% implemented (no model, no API, no UI)
- **Guest extras catalog** — 0% (no ordering, no delivery tracking)
- **Checklist/photo enforcement for cleaning** — Backend may exist, frontend completion unclear
- **Deposit persistence** — UI present, backend persistence not confirmed
- **Worker ID cards** — 0%
- **Passport capture in production** — DEV_BYPASS still active
- **PMS/channel manager layer** (Guesty, Hostaway) — deferred, code exists but not active

---

## 15. Corrections to Documentation Claims

The following are cases where direct code reading contradicts or meaningfully qualifies what the documentation states. These are not errors in the documentation — they likely reflect documentation written at a point in time that the code has since moved past, or vice versa.

**Claim: "Problem reporting is 0% implemented."**
**[PROVEN INCORRECT]** `src/api/problem_report_router.py` exists, is mounted in `main.py` (Phase 598), and is a complete, functional implementation:
- `POST /problem-reports` — create report (property_id, category, description, priority, reported_by)
- `GET /problem-reports` — list with filters (property_id, status, priority)
- `GET /problem-reports/{id}` — single report
- `PATCH /problem-reports/{id}` — update status, assign, resolve
- `POST /problem-reports/{id}/photos` — add photo URL
- `GET /problem-reports/{id}/photos` — list photos

Phase 648: On creation, a MAINTENANCE task is auto-created and linked. Priority maps: urgent→CRITICAL (5-min SLA), normal→MEDIUM.
Phase 650: Audit event on status change.
Phase 651: SSE alert emitted to admin+ops on urgent problems.
Phase 652: Category→maintenance specialty mapping (pool, plumbing, electrical, etc.).
i18n: `description_original_lang` field supports multilingual reports.

14 categories: pool, plumbing, electrical, ac_heating, furniture, structure, tv_electronics, bathroom, kitchen, garden_outdoor, pest, cleanliness, security, other.
4 statuses: open, in_progress, resolved, dismissed.

**This system is substantially more complete than the documentation gap analysis claims.** The documentation's "0%" appears to have been written at an earlier point in development and not updated.

**Claim: "WhatsApp, LINE, Telegram, SMS, Email are all live escalation channels."**
Correction found: `notification_dispatcher.py` confirms LINE and Telegram are live (real HTTP API calls). WhatsApp has an adapter but the API URL is in a comment as "future." FCM, Email (for notifications), SMS (for notifications) are stubs. SendGrid and Twilio credentials exist in env config, but the notification dispatcher stubs do not call them. Note: separate Email and SMS routers exist in main.py (`email_router`, `sms_router`) — these may be for different purposes (inbound webhooks, not outbound notifications).

**Claim: "Owner portal has configurable transparency toggles."**
Qualification found: `owner_portal_v2_router.py` defines the visibility toggle endpoints and the data model (8 visibility flags). However, the filtered summary endpoint does not appear to actively filter data based on these toggles — the framework is defined but the actual filtering in query logic is unclear from reading alone. **Status: PARTIAL — toggles exist, filtering integration unconfirmed.**

**Claim: "Manager has full access."**
Correction found: Middleware gives manager unrestricted route access. However, manager capability checks at the API level mean that a manager without delegated `financial` capability cannot access financial endpoints even though they can reach the `/financial` route. Route access and API access are separate layers. A manager might see a blank financial page or an AccessDenied component depending on their capabilities.

**Claim: "5 escalation channels."**
Correction: There are 3 real notification dispatch channels (LINE, Telegram, in-app SSE) and 4 stubs (WhatsApp, FCM, SMS, Email). The architecture supports 5+ channels but the implementation has 3 live.

**`checkin_checkout` combined role — backend canonical status.**
`checkin_checkout` is NOT in `canonical_roles.py`. It is a frontend routing concept handled in `roleRoute.ts` and `worker/page.tsx`. It routes workers to `/ops/checkin-checkout`, which is a hub page that links to both check-in and check-out flows. Backend role resolution does not recognize `checkin_checkout` as a canonical role — a worker with this label would need to have both `checkin` and `checkout` in their `worker_roles[]` array in `tenant_permissions`.

---

## 16. Deployment Reality

**[PROVEN]** Three environments confirmed:
- Local dev: SQLite + `IHOUSE_DEV_MODE=true`
- Staging: Supabase + Railway (backend) + Vercel (frontend) — live and E2E proven
- Production: Docker Compose v2 template exists

**[PROVEN]** Critical environment variables: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `IHOUSE_JWT_SECRET`, `IHOUSE_GUEST_TOKEN_SECRET`, `IHOUSE_ACCESS_TOKEN_SECRET`

**[PROVEN]** `IHOUSE_DEV_MODE=true` is blocked in production by `env_validator.py`. `IHOUSE_ENV=production` is required.

**[CLAIMED]** 7,765 tests passing — stated in documentation, not independently run.
