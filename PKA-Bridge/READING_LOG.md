# Reading Log

Ordered record of what was read during the initial system audit.
Session date: 2026-03-28

---

## Pass 1 — Repository Structure

- Top-level directory tree (maxdepth 2)
- `ihouse-ui/app/` directory tree (full route structure)
- `src/` directory tree (all Python source files)

**Observation:** This is a two-part system — a Python FastAPI backend (`src/`) and a Next.js frontend (`ihouse-ui/`). Both are sizeable. There is also a static marketing site (`domaniqo-site/`) and a documentation tree (`docs/`) with clear layering.

---

## Pass 2 — Core Documentation

Files read:

- `docs/core/` — all files (BOOT.md, vision.md, system-identity.md, canonical-event-architecture.md, governance.md, current-snapshot.md, work-context.md, live-system.md, phase-timeline.md, roadmap.md, IDENTITY.md, auth-closure.md, admin-preview-and-act-as.md, RULE_staffing_task_backfill.md)
- `docs/product/` — all files
- `docs/vision/` — product_vision.md, system_vs_vision_audit.md, master_roadmap.md, phase-chain-protocol.md
- `docs/architecture/` — Architecture.md
- `docs/operator-runbook.md`
- `docs/deploy-quickstart.md`
- `.agent/PROJECT_CONTEXT.md`
- `.agent/progress.md`
- `.agent/findings.md`

**Key finding:** Documentation is deliberately layered into immutable (Layer A), governance (Layer B), current-state (Layer C), and history (Layer D). The team has enforced append-only rules on history files and locked certain architectural documents. This is unusual discipline for a project this size.

---

## Pass 3 — Role and Authorization Model

Files read:

- `src/services/canonical_roles.py`
- `src/services/role_authority.py`
- `src/services/delegated_capabilities.py`
- `src/api/permissions_router.py`
- `src/api/auth.py`
- `src/api/auth_router.py`
- `src/api/capability_guard.py`
- `src/core/kind_registry.core.json`
- `src/core/skill_exec_registry.core.json`
- `src/api/invite_router.py`
- `src/api/staff_onboarding_router.py`

**Key finding:** Role model is mature and security-conscious. DB-authoritative roles, capability delegation for managers, two distinct onboarding pipelines (invite vs. staff self-apply), and an identity-only signup model that prevents auto-provisioning. Admin cannot be created via invite — this is a hard guard.

---

## Pass 4 — Check-in, Guest Portal, Worker, and Task Flows

Files read:

- `src/api/booking_checkin_router.py`
- `src/api/guest_checkin_form_router.py`
- `src/api/guest_portal_router.py`
- `src/api/guest_token_router.py`
- `src/services/guest_portal.py`
- `src/services/guest_token.py`
- `src/api/worker_router.py`
- `src/api/worker_copilot_router.py`
- `src/api/cleaning_task_router.py`
- `src/tasks/task_model.py`
- `src/tasks/task_writer.py`
- `src/tasks/task_automator.py`
- `src/api/checkin_identity_router.py`
- `src/api/pii_document_router.py`
- `src/api/operations_router.py`

**Key finding:** The backend task and check-in flows are well-built. The guest token system is cryptographically sound (HMAC-SHA256, constant-time comparison, hash-only storage). The cleaning checklist router (Phase 626–632) is real and functional. The passport capture system exists in the backend but has a `DEV_PASSPORT_BYPASS` flag that is still active.

---

## Pass 5 — UI Routes and Pages

Files read (via agent):

- Full `ihouse-ui/app/` route listing (all page.tsx locations)
- `app/(public)/guest/[token]/page.tsx` — Guest portal (public, token-gated)
- `app/(app)/worker/page.tsx` — Worker role landing page
- `app/(app)/ops/page.tsx` — Operations dashboard
- `app/(app)/ops/cleaner/page.tsx` — Cleaner workflow
- `app/(app)/ops/checkin/page.tsx` — Check-in 6-step flow
- `app/(app)/ops/checkout/page.tsx` — Check-out 4-step flow
- `app/(app)/checkin/page.tsx` — Redirect to /ops/checkin
- `app/(app)/checkout/page.tsx` — Redirect to /ops/checkout
- `app/(app)/dashboard/page.tsx` — Admin/manager landing
- `app/(app)/owner/page.tsx` — Owner financial dashboard
- `app/(public)/onboard/[token]/page.tsx` — Property owner onboarding
- `app/(public)/invite/[token]/page.tsx` — Staff invitation acceptance
- `app/(app)/admin/staff/page.tsx` — Staff roster management
- `app/(app)/admin/intake/page.tsx` — Property intake review queue
- `app/(app)/tasks/page.tsx` — Task board

**Key finding:** UI pages are more complete than the documentation gap analysis suggests for some areas, but several critical flows (deposit persistence, passport storage wire-up, messaging integration) are rendered but not connected to backend storage.

---

## Pass 6 — Backend Pipeline, OTA Adapters, Migrations

Files read:

- `src/adapters/ota/pipeline.py`
- `src/adapters/ota/registry.py`
- `src/api/bookings_router.py`
- `src/api/booking_lifecycle_router.py`
- `src/api/intake_router.py`
- `src/services/booking_writer.py`
- `src/main.py` (full router mount list)
- `migrations/` — 18 files (first and last described)
- `supabase/migrations/` — 26 files (first and last described)
- `src/core/runtime.py`
- `src/core/executor.py`
- `src/core/ports.py`

**Key finding:** The backend is architecturally solid. Supabase is the single canonical source. The event log is append-only. There are 44 migration files across two directories (18 legacy + 26 Supabase-format). The most recent Supabase migration (Phase 947) adds a worker identity integrity audit view — showing active attention to data quality.

---

## Pass 7 — Remaining Ops and Admin UI Pages

Files read directly:

- `app/(app)/ops/maintenance/page.tsx` — Maintenance worker mobile flow
- `app/(app)/ops/checkin-checkout/page.tsx` — Combined role hub page
- `app/(app)/manager/page.tsx` — Manager audit trail + morning briefing
- `app/(app)/admin/managers/page.tsx` — Manager capability toggles
- `app/(app)/admin/owners/page.tsx` — Owner CRUD with property assignment
- `app/(app)/admin/portfolio/page.tsx` — Cross-property overview dashboard
- `app/(app)/admin/page.tsx` — Integrations configuration (LINE, WhatsApp, OTA channels)
- `app/(app)/admin/layout.tsx` — Layout wrapper (minimal stub)
- `app/(app)/admin/settings/page.tsx` — Property ID auto-generation settings
- `app/(app)/admin/more/page.tsx` — Navigation hub to additional admin pages

**Key corrections from this pass:**

1. **Maintenance page is real and functional.** It calls `/worker/tasks?worker_role=MAINTENANCE` AND `/problem-reports` — meaning a `/problem-reports` endpoint exists or is expected. This contradicts the documentation claim of "0% implemented" for problem reporting. The UI is wired to call this endpoint.

2. **`/admin` page is NOT a generic admin dashboard.** It is specifically the integrations configuration hub — LINE credentials, WhatsApp token, Telegram bot, SMS, email sender identities, and OTA channel overview.

3. **Manager page is specifically an audit trail + AI morning briefing.** Not a generic management screen. It shows live mutations (action, entity, actor, timestamp) with filter pills and a morning briefing copilot widget.

4. **`/admin/managers`** is the capability delegation surface — one card per manager with 7 toggleable capability checkboxes. This is real and working.

5. **`/admin/owners`** is a full CRUD surface with property assignment (dropdown + chips). This is real and working.

6. **`/admin/settings`** is specifically about property ID auto-generation (prefix + starting number). Minimal scope.

---

## Pass 8 — Frontend Auth, Middleware, Hooks, and Components

Files read directly:

- `ihouse-ui/middleware.ts` — Edge-level route guard (full)
- `ihouse-ui/lib/tokenStore.ts` — Tab-aware token storage
- `ihouse-ui/lib/api.ts` — Admin API client
- `ihouse-ui/lib/staffApi.ts` — Worker API client
- `ihouse-ui/lib/ActAsContext.tsx` — Act As session management
- `ihouse-ui/lib/supabaseClient.ts` — Supabase OAuth client
- `ihouse-ui/lib/roleRoute.ts` — Post-login redirect mapping
- `ihouse-ui/lib/identityLinking.tsx` — Google + password identity linking
- `ihouse-ui/lib/capabilityCheck.ts` — Capability denial detection
- `ihouse-ui/lib/apiCache.ts` — Stale-while-revalidate cache
- `ihouse-ui/lib/LanguageContext.tsx` — i18n state
- `ihouse-ui/lib/PreviewContext.tsx` — Admin preview-as mode
- `ihouse-ui/hooks/useIdentity.ts` — Canonical identity hook
- `ihouse-ui/hooks/usePasswordRules.ts` — Password policy hook
- `ihouse-ui/hooks/useMediaQuery.ts` — Responsive breakpoints
- `ihouse-ui/components/AdaptiveShell.tsx` — Responsive layout wrapper
- `ihouse-ui/components/Sidebar.tsx` — Role-filtered navigation
- `ihouse-ui/components/ActAsSelector.tsx` — Impersonation entry point
- `ihouse-ui/components/SignedInShell.tsx` — Header for public auth surfaces
- `ihouse-ui/components/MobileStaffShell.tsx` — Mobile staff frame
- `ihouse-ui/components/ActAsWrapper.tsx` — Context provider wrapper
- `ihouse-ui/components/AccessDenied.tsx` — Capability denial UI

**Key findings from this pass:**

1. **Middleware.ts gives the authoritative route access matrix.** This is more precise than any documentation. Key facts:
   - `admin` and `manager` have unrestricted access to all routes.
   - `owner` is restricted to `/owner` and `/dashboard` only.
   - `worker` accesses: `/worker`, `/ops`, `/maintenance`, `/checkin`, `/checkout`.
   - `cleaner` accesses: `/worker`, `/ops` only (notably NOT `/dashboard`).
   - `ops` accesses: `/ops`, `/dashboard`, `/bookings`, `/tasks`, `/calendar`, `/guests`.
   - `checkin` accesses: `/checkin`, `/ops/checkin` only.
   - `checkout` accesses: `/checkout`, `/ops/checkout` only.
   - `maintenance` accesses: `/maintenance`, `/worker` only.
   - `identity_only` accesses: `/welcome`, `/profile`, `/get-started`, `/my-properties` only.
   - Missing/empty role → `/no-access` (not admin fallback).

2. **Two distinct API clients for two distinct user types.** `lib/api.ts` uses localStorage (admin/manager). `lib/staffApi.ts` uses sessionStorage-first via getTabToken() (workers). These must NEVER be mixed — mixing causes 401 errors.

3. **Act As is real, complete, and tab-isolated.** New tab gets scoped JWT with `token_type: "act_as"`. Admin tab never touched. Timer countdown is live. END SESSION cleans up correctly.

4. **Token expiration is enforced at the edge** (middleware decodes and checks `exp` claim). Expired tokens: cookie cleared, redirect to `/login`. No need for JS-side checks on every request.

5. **`dashboard` route is more broadly accessible than assumed.** Sidebar shows Dashboard for: admin, manager, owner, worker, cleaner, checkin, maintenance. But middleware restricts `owner` to `/owner` + `/dashboard`. So owner can reach `/dashboard` but middleware shows `dashboard` in their allowed prefix list.

6. **Preview As is server-enforced.** Server returns `PREVIEW_READ_ONLY` (403) on mutations during preview. Client disables buttons AND the server rejects mutations. Both layers work.

---

## Pass 9 — SLA, Scheduler, Notifications, Admin API, Financial

Files read directly:

- `src/tasks/sla_engine.py` — Pure SLA evaluation logic
- `src/tasks/sla_trigger.py` — Periodic SLA batch sweep
- `src/channels/notification_dispatcher.py` — Channel routing
- `src/channels/sla_dispatch_bridge.py` — SLA→notification bridge
- `src/tasks/pre_arrival_tasks.py` — Pre-arrival task generation
- `src/services/scheduler.py` — Background job scheduler
- `src/api/admin_router.py` — Admin query and config API
- `src/api/owner_portal_router.py` — Owner portal endpoints
- `src/api/owner_portal_v2_router.py` — Owner portal v2 + maintenance specialists
- `src/services/owner_portal_data.py` — Owner data assembly
- `src/api/financial_dashboard_router.py` — Financial dashboard API
- `src/api/financial_router.py` — Financial catch-all API
- `src/services/financial_writer.py` — Manual payment write
- `src/api/manager_copilot_router.py` — Manager AI copilot
- `src/api/staff_performance_router.py` — Staff metrics API
- `ihouse-ui/app/(app)/financial/statements/page.tsx` — Owner statement UI
- `ihouse-ui/app/(app)/financial/page.tsx` — Financial dashboard UI

**Key findings and corrections from this pass:**

1. **Notification channels: only LINE and Telegram are live.** WhatsApp API call is a stub (future: `graph.facebook.com/...` is in comments, not wired). FCM, Email (notifications), SMS (notifications) are all stubs in `notification_dispatcher.py`. The dispatch chain exists but most channels beyond LINE and Telegram are not connected to real APIs.

2. **Scheduler runs 5 jobs:** SLA sweep (2 min), DLQ alert (10 min), health log (15 min), pre-arrival scan (daily at 06:00 UTC), iCal resync (15 min). The iCal resync at 15-minute intervals is the primary booking intake mechanism for iCal-based OTA channels.

3. **SLA escalation dispatch targets `ops` role (which maps to role IN ('worker', 'manager'))** — not just `admin`. This means workers and managers both receive escalations.

4. **Financial writer `generate_payout_record` does not persist.** It calculates the payout but returns the dict without writing to any table. The caller is expected to persist it — but there is no evidence that any caller does.

5. **Owner portal v2 visibility toggles exist** (bookings, financial_summary, occupancy_rates, maintenance_reports, guest_details, task_details, worker_info, cleaning_photos) but the filtered summary endpoint does not appear to actively apply them to the query — the framework is defined but the filtering logic is incomplete.

6. **Maintenance specialist sub-system (Phases 725–728) is built.** Specialties can be created, assigned to workers, and used to filter maintenance tasks. External worker task push exists with financial data sanitization.

7. **Financial reads are mature and production-quality.** Epistemic tier (A/B/C for measured/calculated/incomplete) is a real system concept enforced across both API and UI.

8. **`staff_performance_router` admin endpoints lack explicit role guards** — JWT is checked but role is not validated against "admin" or "manager". Any authenticated user could potentially query staff performance metrics.

9. **Admin audit log is append-only** and confirmed from multiple angles — admin_router.py writes to it on integration changes and flag updates, and the route for reading it has no delete path.

---

## Reading Coverage Summary (Updated)

| Area | Depth |
|------|-------|
| Core documentation | Deep — all Layer A, B, C files read |
| Role and auth model | Deep — all auth/permission source files read |
| Backend API surface | Deep — 20+ routers read directly |
| Task and check-in flows | Deep — all task/check-in source files |
| Guest portal and token | Deep — all guest-facing source files |
| OTA adapters | Medium — pipeline, registry read; individual adapters not read |
| UI pages — worker/ops | Deep — all ops/* pages read directly |
| UI pages — admin | Deep — most admin/* pages read directly |
| UI pages — financial | Deep — both financial pages read |
| UI pages — public | Medium — guest portal, invite, onboard read |
| Frontend auth system | Deep — middleware, lib/, hooks/, key components all read |
| Database migrations | Medium — first and last in each directory; middle not read |
| Financial layer | Deep — dashboard, catch-all, writer, UI all read |
| SLA and scheduler | Deep — engine, trigger, scheduler, bridge all read |
| Notification dispatch | Deep — dispatcher, bridge read; only LINE and Telegram confirmed live |
| AI copilot layer | Medium — manager copilot read; other copilots known from main.py only |
| Owner portal | Deep — v1, v2, data service, UI all read |
| Staff performance | Deep — backend router and metrics confirmed |
