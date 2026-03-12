# Phase 392 — Role-Based Entry Routing

**Status:** Closed
**Prerequisite:** Phase 391 (Property Onboarding)
**Date Closed:** 2026-03-13

## Goal

Route users to role-appropriate landing page after login based on JWT role claim.

## Design / Files

| File | Change |
|------|--------|
| `ihouse-ui/lib/roleRoute.ts` | NEW — JWT role→route mapping (admin→dashboard, ops→ops, worker→worker, etc.). Falls back to /dashboard |
| `ihouse-ui/app/(public)/login/page.tsx` | MODIFIED — Uses getRoleRoute() instead of hardcoded /dashboard redirect |

## Invariant

Current JWT payload (session_router.py) has NO role claim (sub, iat, exp, token_type only). roleRoute.ts always falls back to /dashboard until backend adds a role field to the JWT.

## Result

TypeScript 0 errors. Role routing is structurally correct but non-functional due to missing JWT role claim.
