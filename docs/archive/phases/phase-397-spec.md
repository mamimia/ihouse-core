# Phase 397 — JWT Role Claim + Route Enforcement

**Status:** Closed
**Prerequisite:** Phase 396 (Property Admin Approval Dashboard)
**Date Closed:** 2026-03-13

## Goal

Add role claims to JWT tokens and enforce route-level access based on roles. The login page now includes a role selector. Middleware validates role against protected route groups.

## Invariant

JWT tokens always include a `role` claim. Route groups enforce role-based access.

## Design / Files

| File | Change |
|------|--------|
| `src/api/auth.py` | MODIFIED — role claim in JWT |
| `ihouse-ui/middleware.ts` | MODIFIED — route-level role enforcement |
| `ihouse-ui/app/(public)/login/page.tsx` | MODIFIED — role selector |

## Result

**14 tests pass, 0 skipped.**
