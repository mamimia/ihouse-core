# Phase 1033 — Canonical Task Timing Hardening (+ OM Surface, Act As, Staff Onboarding)

**Status:** Closed
**Prerequisite:** Phase 1032 — Live Staging Proof + Baton-Transfer Closure
**Date opened:** 2026-03-31
**Date closed:** 2026-04-01
**Branch:** `checkpoint/supabase-single-write-20260305-1747`
**Commits:** `305a083` → `e79adb2` (OM surface + Act As + onboarding), `cd8a04a` (backend timing), `1480f03` (frontend timing)

> Note: Implementation landed across multiple workstreams in this session.
> Documentation closure was incomplete at the time of commit — completed via the Phase 1033 closure pass on 2026-04-01.

---

## Goal

Standardize task-action timing across all worker-facing surfaces by implementing a
backend-canonical, hour-level UTC timing model (primary workstream). Additionally landed
in this phase: Operational Manager surface shell, person-specific Act As / Preview As,
and staff onboarding hardening.

---

## Invariants (Timing)

- `ack_allowed_at` = `effective_due_at` − 24h (UTC-aware)
- `start_allowed_at` = `effective_due_at` − 2h (UTC-aware)
- MAINTENANCE and GENERAL tasks: no start gate (start always open)
- CRITICAL priority: bypasses all gates unconditionally
- Frontend timing state is derived exclusively from server-provided fields — no local computation
- `due_time` is written at task creation and preserved during reschedule
- Structured errors `ACKNOWLEDGE_TOO_EARLY` / `START_TOO_EARLY` include `opens_in` duration

---

## Workstream 1: Worker Timing Gate Model

**Status: BUILT + STAGING-PROVEN (checkin ✅ checkout ✅ / maintenance 🔲 no task available)**

| File | Change |
|------|--------|
| `src/tasks/timing.py` | NEW — `compute_task_timing()` canonical module. Calculates `effective_due_at`, `ack_is_open`, `ack_allowed_at`, `start_is_open`, `start_allowed_at`. CRITICAL bypass, MAINTENANCE/GENERAL no start gate. |
| `src/api/worker_router.py` | MODIFIED — All `/worker/tasks` responses enriched with 4 timing fields. `/acknowledge` + `/start` enforce hour-level UTC gates; return structured `ACKNOWLEDGE_TOO_EARLY` / `START_TOO_EARLY` errors with `opens_in`. |
| `src/tasks/task_writer.py` | MODIFIED — `_task_to_row` writes `due_time` at creation using kind-based defaults (`_KIND_DUE_TIME` map: Cleaning=10:00, Checkout=11:00, Checkin=14:00, Maintenance=09:00). Reschedule path preserves `due_time`. |
| `ihouse-ui/components/WorkerTaskCard.tsx` | MODIFIED — `AckButton` + new `StartButton` components read server timing fields. On early press → flash "Opens in Xh Ym" for 3s then revert. `computeOpensIn()` replaces frontend date math. 4 new props on `WorkerTaskCardProps`. |
| `ihouse-ui/app/(app)/ops/cleaner/page.tsx` | MODIFIED — `CleaningTask` type extended with 4 timing fields; both `WorkerTaskCard` usages (today + upcoming) pass timing props. |
| `ihouse-ui/app/(app)/ops/checkout/page.tsx` | MODIFIED — `CheckoutTask` type extended with 4 timing fields; `startIsOpen` conditioned on `isActionable`. |
| `ihouse-ui/app/(app)/ops/checkin/page.tsx` | MODIFIED — `Booking` type extended with 4 timing fields; propagated through `bookingMap` merge loop; `BookingCardList` → `WorkerTaskCard` passes timing props. |

---

## Workstream 2: Operational Manager Surface

**Status: BUILT, SURFACED on Vercel — not screenshot-proven on staging**

OM shell with 6-page navigation. Hub is cockpit-first (Alert rail → Metrics → Task Board → Stream).
`DraftGuard` on all OM pages (admin-only access while surface matures).

| File | Change |
|------|--------|
| `ihouse-ui/app/(app)/manager/page.tsx` | NEW — OM Hub: cockpit-first layout |
| `ihouse-ui/app/(app)/manager/alerts/page.tsx` | NEW — wired to `/manager/audit` endpoint |
| `ihouse-ui/app/(app)/manager/stream/page.tsx` | NEW — stream surface |
| `ihouse-ui/app/(app)/manager/team/page.tsx` | NEW — property names, lane coverage matrix, worker roster |
| `ihouse-ui/app/(app)/manager/bookings/page.tsx` | NEW — bookings surface draft |
| `ihouse-ui/app/(app)/manager/calendar/page.tsx` | NEW — calendar surface draft |
| `ihouse-ui/app/(app)/manager/tasks/page.tsx` | NEW — tasks surface draft |
| `ihouse-ui/app/(app)/manager/profile/page.tsx` | NEW — profile surface draft |
| `src/api/task_takeover_router.py` | MODIFIED — expanded: `POST /tasks/{id}/notes`, `GET /manager/alerts`, `GET /manager/team-overview` added to existing takeover/reassign/context/tasks endpoints |

---

## Workstream 3: Person-Specific Act As / Preview As

**Status: BUILT, SURFACED on Vercel — not screenshot-proven on staging**

| File | Change |
|------|--------|
| `ihouse-ui/app/(app)/act-as/page.tsx` | MODIFIED — reads `name` + `user_id` query params; banner shows "Role · [Person Name]"; `checkin_checkout` requires BOTH roles |
| `ihouse-ui/app/(app)/preview/page.tsx` | MODIFIED — reads `name` + `user_id`; stores `ihouse_preview_display_name`, `ihouse_preview_user_id`; emits `PREVIEW_OPENED`/`PREVIEW_CLOSED` audit |
| `ihouse-ui/middleware.ts` | MODIFIED — `/act-as` + `/preview` added to `PUBLIC_PREFIXES` |
| `ihouse-ui/lib/apiFetch.ts` | MODIFIED — logout only on 401, never on 403 |
| Auth / sub-role fix | `checkin_checkout` ActAs now validates BOTH checkin AND checkout worker roles are present |

---

## Workstream 4: Staff Onboarding Hardening

**Status: BUILT, SURFACED on Vercel — not screenshot-proven on staging**

- Manager role validation added to onboarding flow
- Canonical role lock enforced (UNKNOWN / invalid roles blocked)
- Approval history always visible
- Work Permit rule enforced
- Combined checkin+checkout tile (visually unified)

---

## Staging Proof Summary

| Item | Status |
|------|--------|
| Check-in timing gate | ✅ Proven |
| Check-out timing gate | ✅ Proven |
| Maintenance timing gate | 🔲 Not proven (no live task available) |
| OM Hub / Alerts / Stream / Team pages | 🔲 Surfaced — no screenshot |
| Act As "Role · [Name]" banner | 🔲 Surfaced — no screenshot |
| Staff onboarding hardening | 🔲 Surfaced — no screenshot |

---

## OM Task Model — Product Decision Lock (Carried into Phase 1034)

The following was fully designed and approved in Phase 1033 as the next phase (Phase 1034 = OM-1).

### Separation

- Worker layer = `Acknowledge → Start → Complete` (execution, time-gated by backend)
- Manager layer = `Monitor · Takeover · Reassign · Note` (oversight, no timing gates)

### Phase 1034 (OM-1) — Approved Spec

**Backend:**
1. `POST /worker/tasks/{id}/takeover-start` — manager/admin only; PENDING→ACKNOWLEDGED→IN_PROGRESS atomic walk; bypasses timing gates; audit: `TASK_TAKEOVER_STARTED`
2. `PATCH /worker/tasks/{id}/reassign` — updates `assigned_to`; property-scoped Tier 1 / explicit tenant-wide Tier 2 opt-in; audit: `TASK_REASSIGNED`
3. `PATCH /worker/tasks/{id}/notes` — appends `{text, author_id, author_name, created_at, source}` to `tasks.notes[]`

**Frontend:**
4. `ManagerTaskCard.tsx` — timing strip (read-only informational), `[Takeover] [Reassign] [Note ✎]`, no worker execution buttons
5. Reassign panel — Tier 1: property-scoped workers; Tier 2: explicit "Show all eligible" opt-in
6. Note inline input — persistent write on confirm
7. Stream page: task event expand → `ManagerTaskCard` drill-down layer
8. `ManagerExecutionDrawer`: route to `takeover-start` endpoint, not `forceCompleteTask`

**4 locked constraints:**
1. Takeover bypass via dedicated route ONLY — no global role bypass on ack/start endpoints
2. Reassign Tier 1 = property-scoped; Tier 2 = explicit tenant-wide opt-in
3. Notes: `author_id` + `author_name` + `created_at` + `source` — not ephemeral
4. `ManagerTaskCard` in drill-down layer only — Hub/Stream/Alerts/Team remain primary OM surfaces

**Not in scope (Phase 1034 and beyond):** Force Advance.
