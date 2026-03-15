# Phase 800 — Worker & Manager Invite Flow + Pre-801 Auth Identity Fix

**Status:** Closed
**Prerequisite:** Phase 799 (First Notification Dispatch)
**Date Closed:** 2026-03-15

## Goal

Complete invite flow: create + accept invites for manager and worker users. Then fix 3 critical auth identity issues discovered during invite testing: service-role client separation, session router identity resolution, and login UI cleanup.

## Invariant

- Service-role client must be used for all internal DB writes (never tainted by user session)
- JWT `sub` claim must contain Supabase Auth UUID (not tenant_id)
- User role is server-determined from `tenant_permissions`, never client-chosen

## Design / Files

| File | Change |
|------|--------|
| `src/api/invite_router.py` | MODIFIED — Separate `supa_admin` (service_role) and `supa_login` (anon) clients |
| `src/api/auth_login_router.py` | NEW — `POST /auth/login` (email+password → Supabase Auth → tenant lookup → JWT) |
| `src/api/auth.py` | MODIFIED — Added `get_identity()` + `jwt_identity` dependency, dual JWT format support |
| `src/api/session_router.py` | MODIFIED — `/auth/login-session` renamed to `/auth/dev-login`, deprecated |
| `src/main.py` | MODIFIED — Registered `auth_login_router` |
| `ihouse-ui/lib/api.ts` | MODIFIED — Added `loginWithEmail()`, updated `LoginResponse` type |
| `ihouse-ui/app/(public)/login/page.tsx` | MODIFIED — Email + password only, removed tenant_id/secret/role fields |
| `ihouse-ui/app/(public)/dev-login/page.tsx` | NEW — Old login form preserved for dev/internal use |
| `docs/product/admin-preview-mode.md` | NEW — Product direction: read-only role preview for admins |
| `docs/product/staffing-flexibility.md` | NEW — Product direction: check-in/check-out staffing model |

## Result

Invite flow: both manager and worker users created in Supabase Auth with correct roles in tenant_permissions. Auth identity fix: runtime-verified on staging Docker:
- `admin@domaniqo.com` → role=admin ✅
- `manager@domaniqo.com` → role=manager ✅
- `worker@domaniqo.com` → role=worker ✅

All 3 logins authenticate via Supabase Auth, resolve identity from `tenant_permissions`, and return JWT with correct `sub=user_id`, `tenant_id`, and `role` claims.
