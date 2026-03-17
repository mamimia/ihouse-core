# Phase 831 — Cleaner Role + Auth Hardening

**Status:** Closed
**Prerequisite:** Phase 830 (System Re-Baseline + Data Seed + Zero-State Reset)
**Date Closed:** 2026-03-17

## Goal

Add `cleaner` as a first-class role across the auth and routing stack. Remove the hardcoded `tenant_e2e_amended` fallback in the login flow — if no `tenant_permissions` row exists, the user must be re-invited.

## Invariant

- No hardcoded tenant fallback in auth login. Missing `tenant_permissions` → 403 `NO_TENANT_BINDING`.
- `role_authority.py` prefers `requested_role` when no DB record exists, instead of silently defaulting.

## Design / Files

| File | Change |
|------|--------|
| `src/api/auth_login_router.py` | MODIFIED — added `cleaner` to `_VALID_ROLES`, removed hardcoded `tenant_e2e_amended` fallback |
| `src/api/session_router.py` | MODIFIED — added `cleaner` to `_VALID_ROLES` |
| `src/services/role_authority.py` | MODIFIED — prefer `requested_role` when no DB record, fall back to default |
| `ihouse-ui/middleware.ts` | MODIFIED — added `/dev-login` as public prefix, added `cleaner` role access rules |
| `ihouse-ui/lib/roleRoute.ts` | MODIFIED — cleaner → `/ops/cleaner` landing |

## Result

Cleaner role recognized across backend + frontend. Auth login no longer falls back to hardcoded tenant.
