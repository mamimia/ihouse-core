# Phase 855E — Onboarding Pipeline Audit

**Status:** Closed
**Prerequisite:** Phase 855D (Auth Identity Model Design)
**Date Closed:** 2026-03-20

## Goal

Audit the existing invite/onboarding/approval/activation system before making any auth or identity changes. Understand the two existing pipelines, identify where Google OAuth conflicts or complements them, and determine the minimum safe path forward.

## Design / Files

| File | Change |
|------|--------|
| `onboarding_pipeline_audit.md` (artifact) | NEW — Full audit: Pipeline A (simple invite, Phase 401), Pipeline B (staff self-onboarding, Phase 844), conflict analysis, admin email strategy |
| `src/api/invite_router.py` | Audited — no changes |
| `src/api/staff_onboarding_router.py` | Audited — no changes |
| `src/services/access_token_service.py` | Audited — no changes |
| `src/services/tenant_bridge.py` | Audited — no changes |
| `src/api/auth_login_router.py` | Audited — no changes |
| `ihouse-ui/app/(public)/staff/apply/page.tsx` | Audited — no changes |
| `ihouse-ui/app/(public)/invite/[token]/page.tsx` | Audited — no changes |
| `ihouse-ui/app/(app)/admin/staff/requests/page.tsx` | Audited — no changes |
| `ihouse-ui/app/(public)/onboard/[token]/page.tsx` | Audited — no changes |
| `ihouse-ui/app/(public)/auth/callback/page.tsx` | Audited — no changes |
| `ihouse-ui/lib/roleRoute.ts` | Audited — no changes |

## Result

Key findings:
1. Two fully functional onboarding pipelines already exist and are live
2. Six specific conflict points identified between Google OAuth and existing pipelines
3. The `/auth/register/profile` auto-provision is the real vulnerability (any Google user becomes manager)
4. Changing admin Supabase email to Gmail is the simplest safe path (avoids linked identities entirely)
5. The Phase 855D architecture document is over-engineered for current needs — deferred
6. Existing Pipeline A (simple invite) and Pipeline B (staff onboarding) should remain untouched

Recommended next actions:
- Change admin email in Supabase to actual Gmail
- Delete orphan `tenant_permissions` row for `esegeve@gmail.com`
- Close the auto-provision vulnerability in `/auth/register/profile`
- Keep all existing pipelines as-is
