# Phase 855C — Google OAuth E2E Proof

**Status:** Closed
**Prerequisite:** Phase 855B (Google OAuth Staging Setup)
**Date Closed:** 2026-03-20

## Goal

Complete a full end-to-end Google sign-in on staging: from the login page through Google consent, callback handling, backend token issuance, session creation, and authenticated dashboard landing.

## Design / Files

| File | Change |
|------|--------|
| `ihouse-ui/app/(public)/auth/callback/page.tsx` | No change — existing callback handler worked correctly |
| `src/api/auth_login_router.py` | No change — `/auth/google-callback` correctly resolved tenant and issued JWT |
| Supabase `tenant_permissions` | MODIFIED — manual row inserted for `esegeve@gmail.com` test account to bind tenant + role |

## Invariant

Google OAuth does not auto-provision `tenant_permissions`. A user must have an existing binding (via invite, onboarding, or manual insert) to complete sign-in. Without a binding, the system returns 403 and redirects to `/register/profile`.

## Result

End-to-end proven:
- Google sign-in from staging login page
- Supabase callback → backend `/auth/google-callback`
- iHouse JWT issued with correct tenant_id and role
- Session cookie set, dashboard loaded with real data
- Language preference stored
- Role-based routing to correct surface

Key finding: The test required a manual `tenant_permissions` insert because the Google account email (`esegeve@gmail.com`) did not match the existing admin email (`admin@domaniqo.com`). This confirms that Google OAuth cannot automatically infer role from a different email — explicit identity binding is required.
