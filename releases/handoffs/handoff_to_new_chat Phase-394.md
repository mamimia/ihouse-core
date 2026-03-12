> ⚠️ FIRST: Read `docs/core/BOOT.md` before doing anything else.

# Handoff — Phase 394 → Phase 395

## Current Phase
Phase 394 — Platform Checkpoint XX: Full Multi-Surface Audit (closed).

## Last Closed Phase
Phase 394.

## Next Session Starts At
Phase 395.

## What Was Done (Phases 375–394)

20-phase Platform Surface Consolidation across 4 waves:

**Wave 1 (375–380):** Route group split `(public)/`+`(app)/`, AdaptiveShell, BottomNav, DMonogram, design token extensions, ThemeProvider, login redesign, landing page (7 sections), early-access form, sitemap, robots.

**Wave 2 (381–385):** Responsive adaptation for 15+ pages — auto-fit grids, scroll wrappers for tables, flexWrap headers.

**Wave 3 (386–390):** Mobile role surfaces (ops, checkin, checkout, maintenance), access-link system (guest/invite/onboard token pages), 5 shared components extracted, worker page partial token migration.

**Wave 4 (391–394):** Role-based entry routing (roleRoute.ts), polish sweep, full multi-surface audit.

## Current State

- **28 frontend pages** (22 protected + 6 public)
- **Backend test suite:** ~7,069 collected, pre-existing infra failures only, no new regressions
- **TypeScript:** 0 errors across 4 checkpoints (A, B, C, XX)
- **394 phase specs** in `docs/archive/phases/`

## Critical Known Gaps — Must Read

1. **3 public token pages have NO backend endpoints:** `/guest/[token]`, `/invite/[token]`, `/onboard/[token]` call endpoints that don't exist. They always show the error/expired view.

2. **Role routing is dead code:** JWT payload has no `role` claim (only `sub`, `iat`, `exp`, `token_type`). `lib/roleRoute.ts` always falls back to `/dashboard`.

3. **Checkin/Checkout confirm actions are client-only:** "Guest Arrived" and "Confirm Checkout" buttons set local state, make no API call. Data lost on refresh. Checkout page falsely displays "cleaning task created."

4. **5 shared components are unused:** `StatusBadge`, `DataCard`, `TouchCard`, `DetailSheet`, `SlaCountdown` exist in `components/` but are not imported by any page.

5. **Worker page still ~95% hardcoded colors:** Only 4 of ~50+ hex values were migrated to design tokens.

6. **No RTL, no Thai, no Hebrew:** All text is hardcoded English. Zero `dir=` or `direction: rtl` anywhere.

7. **No route-level role gating:** Any authenticated user can access any `(app)` route by direct navigation.

## Suggested Next Objectives (Phase 395+)

1. **Backend endpoints for token pages** — Build `/guest/portal/{token}`, `/invite/validate/{token}`, `/onboard/validate/{token}`, `/onboard/submit` with token generation, storage, expiration, and revocation.

2. **Add `role` claim to JWT** — Update `session_router.py` to include user role in the JWT payload. This will activate `roleRoute.ts`.

3. **Backend actions for checkin/checkout** — Create API endpoints for "guest arrived" confirmation and "checkout + cleaning task" creation.

4. **Adopt shared components** — Refactor existing pages to use `StatusBadge`, `DataCard`, etc. instead of inline implementations.

5. **Complete token migration** — Migrate remaining hardcoded colors across all pages to `var(--color-*)` tokens.

6. **RTL + i18n** — Add `dir` attribute switching and translate strings for Thai/Hebrew.

7. **Route-level role gating** — Add middleware or layout-level checks to restrict routes by user role.

## Key Files for Next Session

| File | Purpose |
|------|---------|
| `docs/core/BOOT.md` | Protocol rules — read FIRST |
| `docs/core/current-snapshot.md` | System state at Phase 394 |
| `docs/core/work-context.md` | Context, invariants, key files |
| `ihouse-ui/lib/roleRoute.ts` | Role-based routing (inactive) |
| `ihouse-ui/lib/api.ts` | Frontend API client |
| `src/api/session_router.py` | JWT auth — no role claim |
| `ihouse-ui/components/StatusBadge.tsx` | Shared component (unused) |
| `ihouse-ui/app/(app)/ops/page.tsx` | Ops command surface |
| `ihouse-ui/app/(public)/guest/[token]/page.tsx` | Guest portal (no backend) |

## Test Summary

- Backend: ~7,069 collected, pre-existing infra failures (health/Supabase connectivity). No new regressions from Phases 375–394 (frontend-only).
- Frontend: TypeScript `tsc --noEmit` → 0 errors.
- No browser testing was performed. No API integration tests for new frontend pages.
