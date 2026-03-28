> ⚠️ FIRST: Read `docs/core/BOOT.md` before doing anything else.

# Handoff — Post Phase 859

**Date:** 2026-03-21
**Last Closed Phase:** Phase 859 — Admin Intake Queue + Property Submit API + Login UX + Draft Expiration
**Current Phase:** Phase 860 — Not yet defined (user has pending items to add before numbering)
**Staging:** https://domaniqo-staging.vercel.app

---

## What Was Done This Session

### 1. Auth Path Audit (Google Sign-In → Admin Access)

Full audit of the Google OAuth → admin access chain:

```
Google Sign-In (Supabase Auth)
  → /auth/callback (frontend — app/(public)/auth/callback/page.tsx)
    → POST /auth/google-callback (backend — src/api/auth_login_router.py:242)
      → lookup_user_tenant() (src/services/tenant_bridge.py:99)
        → queries tenant_permissions table by user_id (Supabase Auth UUID)
        → Found? → Issue iHouse JWT with {role, tenant_id} → middleware allows access
        → Not found? → Return 403 → redirect to /no-access
```

**Findings:**
- ✅ Auth is correctly gated — new users without `tenant_permissions` row get 403 → `/no-access`
- ✅ Phase 856A auto-provision vulnerability is fixed — `register/profile` returns 403, no provisioning
- 🔴 **Middleware vulnerability (must fix next):** In `middleware.ts` line 132, `if (!role || FULL_ACCESS_ROLES.has(role))` — empty role grants full access

**Key files audited:**
- `ihouse-ui/middleware.ts` — route protection + role check
- `ihouse-ui/app/(public)/auth/callback/page.tsx` — Google OAuth callback handler
- `src/api/auth_login_router.py` — `/auth/login` + `/auth/google-callback` + `/auth/register/profile`
- `src/services/tenant_bridge.py` — `lookup_user_tenant()` + `provision_user_tenant()`

### 2. Intake Page Layout Fix

Moved intake page from `(public)` to `(app)` layout group:
- **Before:** Dark theme, public marketing header, no sidebar
- **After:** White admin theme (ForceLight), admin sidebar (AdaptiveShell), breadcrumbs
- All dark-mode hardcoded colors replaced with admin CSS variable tokens
- Added "← Back to Properties" + "↺ Refresh" buttons in header
- Verified on staging with screenshot proof

### 3. Intake Queue Button on Properties Page

Added amber-accented "📋 Intake Queue" button to Properties page header row between "+ Add Property" and "🗄 Archived".

---

## Open Work Items — Carry Forward (No Phase Numbers Yet)

The user explicitly requested these not be numbered yet — they have additional items to add.

### 🔴 Must Fix — Auth & Security

1. **Middleware empty-role vulnerability**
   - `middleware.ts` line 132: `!role` → full access
   - Must change to: empty role → redirect to login, not grant admin
   - File: `ihouse-ui/middleware.ts`

2. **Intake API email whitelist → role-based check**
   - `app/api/admin/intake/route.ts` lines 27-29 hardcode `admin@domaniqo.com` and `amir@domaniqo.com`
   - Should verify admin role from iHouse JWT instead of Supabase access token
   - File: `ihouse-ui/app/api/admin/intake/route.ts`

### 🟠 Core Product — Operations Build

3. **iCal Feed Connection (Real)**
   - UI exists ("Connect your calendar"), no backend
   - Needs: URL input, fetch, parse, validate, periodic sync, booking import

4. **Property Detail Deep: House Info**
   - GPS save, check-in/out times, deposit config, house rules, WiFi/door code
   - Phase A gaps (A-1 through A-4 in work-context.md)

5. **Reference Photos Upload & Display**
   - Gap A-1: backend ready, no upload widget
   - File picker + upload to Supabase Storage

6. **Cleaning Checklist System**
   - Cleaner mobile page exists but checklist is presentational
   - Template CRUD, progress tracking, room photos, supply check, complete blocking

7. **Check-in Form System (Backend)**
   - Mobile check-in flow (Phase D) is UI stub — passport, deposit, signature not persisted
   - Gaps D-1 through D-6 in work-context.md

8. **Checkout Flow (Backend + Mobile)**
   - Gap D-7: entirely missing
   - Inspection → Issues → Deposit Resolution → Complete

### 🟢 Admin & Staff UX

9. **Staff Onboarding Admin UI**
   - Pipeline B API works and is runtime-proven, but no admin UI to view/approve applications
   - File: `src/api/staff_onboarding_router.py` (backend ready)

10. **Problem Reporting Module**
    - Phase F in Operational Core — `problem_reports` table exists, no API or UI
    - Worker reports problem → auto-create maintenance task → admin tracks resolution

### 🟢 Deferred Items (from earlier phases)

11. **Staff photo bucket migration (857-F1)** — bucket created, upload/display missing
12. **Email activation click-through proof (857-F2)** — needs real inbox
13. **Pre-Arrival Email SMTP (Phase 614)** — needs SMTP config
14. **Wire Form → Checkin Router (Phases 617-618)** — needs live booking flow
15. **Property URL Extraction** — UI stub, no real scraping (859-F1)

---

## Document Status

All canonical docs have been updated:

| Document | Status |
|----------|--------|
| `docs/core/phase-timeline.md` | ✅ Appended — session entry added |
| `docs/core/construction-log.md` | ✅ Appended — session entry added |
| `docs/core/current-snapshot.md` | ✅ Current — Phase 860 active |
| `docs/core/work-context.md` | ✅ Updated — auto-provision vulnerability marked fixed |

---

## Key Architecture — Quick Reference

| Component | Location | Notes |
|-----------|----------|-------|
| Middleware (auth) | `ihouse-ui/middleware.ts` | Route protection, JWT decode, role check |
| Auth callback | `ihouse-ui/app/(public)/auth/callback/page.tsx` | Google OAuth → backend |
| Backend auth | `src/api/auth_login_router.py` | Login + Google callback + register + change-password |
| Tenant bridge | `src/services/tenant_bridge.py` | UUID → tenant_id + role lookup |
| Intake page | `ihouse-ui/app/(app)/admin/intake/page.tsx` | Now in (app) layout group |
| Intake API | `ihouse-ui/app/api/admin/intake/route.ts` | GET/POST with admin check |
| Properties page | `ihouse-ui/app/(app)/admin/properties/page.tsx` | Has Intake Queue button |
| App layout | `ihouse-ui/app/(app)/layout.tsx` | AdaptiveShell + ForceLight |

---

## Staging Deployment

| Component | URL | Status |
|-----------|-----|--------|
| Frontend | https://domaniqo-staging.vercel.app | ✅ Latest deployed |
| Backend | Railway | ✅ Running |
| Database | Supabase (`reykggmlcehswrxjviup`) | ✅ Connected |

---

## Git Status

All work committed and pushed to branch `checkpoint/supabase-single-write-20260305-1747`.
