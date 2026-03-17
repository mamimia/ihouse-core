> ⚠️ FIRST: Read `docs/core/BOOT.md` before doing anything else.

# Handoff — Phase 830 → Next Chat (Post-Recovery)

**Date:** 2026-03-17 (updated after power outage recovery)
**Last Closed Phase:** 830 — System Re-Baseline + Data Seed + Zero-State Reset
**Last Commit:** `2542be7` — WIP: Post-830 exploration (uncommitted at power outage)

---

## System State — True Zero + WIP Code Changes

### Database: True Zero-State
All data tables = 0 rows. No properties, no bookings, no tasks, no events.

### Code: Phase 830 committed + 8 WIP files committed as exploration
The WIP commit (`2542be7`) contains 8 files modified AFTER Phase 830 closure but BEFORE the power outage. These changes are **not assigned to any phase yet**:

| File | Change | Needs Phase |
|------|--------|-------------|
| `src/api/auth_login_router.py` | Added `cleaner` role, removed hardcoded `tenant_e2e_amended` fallback | Yes |
| `src/api/session_router.py` | Added `cleaner` to valid roles | Yes |
| `src/api/worker_router.py` | Added `PATCH /worker/tasks/{id}/start` endpoint (ACK→IN_PROGRESS) | Yes |
| `src/api/bookings_router.py` | Added `guest_name` to booking list + detail responses | Yes |
| `src/services/role_authority.py` | Minor role authority adjustments | Yes |
| `ihouse-ui/middleware.ts` | Added `/dev-login` as public, cleaner role access rules | Yes |
| `ihouse-ui/lib/roleRoute.ts` | Cleaner → `/ops/cleaner` landing | Yes |
| `ihouse-ui/app/(public)/dev-login/page.tsx` | Minor dev-login page update | Yes |

> [!WARNING]
> These changes MUST be assigned to numbered phases in the next chat before any new work begins.

---

## Phase Numbering — Current Truth

| Phase | Status | Title |
|-------|--------|-------|
| 830 | ✅ Closed | System Re-Baseline + Data Seed + Zero-State Reset |
| 831–841 | ❌ Not started | Numbers reserved in implementation_plan.md (old plan, needs revision) |
| 842 | ❌ Not started | Discussed as "Critical Surface Localization + Language Selector Fix" |
| 843 | ❌ Not started | Discussed as "Guest Portal Enhancement" |
| 844 | ❌ Not started | Discussed as "Owner Mobile Optimization" |

> [!IMPORTANT]
> The implementation_plan.md artifact still contains the OLD 830–844 plan. It was NOT updated to reflect the revised 842–844 direction discussed just before the power outage. The next chat must reconcile phase numbering.

---

## Direction Discussed Before Power Outage

1. **i18n should NOT be a full-system phase** — only critical surfaces first
2. **Phase 842** — Critical Surface Localization (cleaner, guest portal, login, worker) + language selector redesign (top-right, small, mobile-first)
3. **Phase 843** — Guest Portal Enhancement (QR, token delivery, richer data)
4. **Phase 844** — Owner Mobile Optimization (layout/actions/nav)
5. Phase numbering needs correction since 831–841 in the old plan may conflict
6. The user wants mobile-first thinking for all non-admin surfaces

---

## What Must Be Fixed/Verified First in Next Chat

1. **Assign phase numbers** to the 8 WIP changes from `2542be7`
2. **Reconcile phase numbering** — old plan has 831–844, new direction redefines 842–844
3. **Verify zero-state** — confirm DB is still empty after power outage
4. **Update implementation_plan.md** — reflect the revised phase direction
5. **Then proceed** with the intake proof sequence (create first property from zero)

---

## Key Files

| File | Purpose |
|------|---------|
| `docs/core/BOOT.md` | Start here |
| `docs/core/current-snapshot.md` | Phase 831+ — true zero-state |
| `docs/core/work-context.md` | Active objectives + deferred items |
| `docs/core/phase-timeline.md` | Phase 830 is last closed entry |
| `src/scripts/seed_demo.py` | Seed + reset (4 modes, 5 guardrails) |
| `releases/handoffs/handoff_to_new_chat Phase-830.md` | Original Phase 830 handoff |

## Environment

- Branch: `checkpoint/supabase-single-write-20260305-1747`
- FastAPI: `cd src && uvicorn main:app --reload --port 8000`
- Frontend: `cd ihouse-ui && npm run dev`
- Supabase project: `reykggmlcehswrxjviup`
- `.env` at project root must be sourced
