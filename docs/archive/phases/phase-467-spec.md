# Phase 467 — Supabase Auth First Real User

**Status:** Closed
**Prerequisite:** Phase 466 (Environment Configuration Audit)
**Date Closed:** 2026-03-13

## Goal

Add real Supabase Auth signup/signin endpoints so the system can create and authenticate real users rather than relying solely on dev JWT tokens.

## Design / Files

| File | Change |
|------|--------|
| `src/api/auth_router.py` | MODIFIED — Added POST /auth/signup (admin.create_user + sign_in) and POST /auth/signin (sign_in_with_password). Uses service_role key for admin operations, auto-confirms email. Added `Depends` and `jwt_auth` imports. |
| `tests/test_supabase_auth.py` | NEW — 6 tests: signup success/503, signin success/503/401, /auth/me dev mode. All mock Supabase client. |

## Result

**POST /auth/signup creates a real Supabase Auth user with email confirmation auto-enabled. POST /auth/signin returns Supabase-issued JWT directly usable with all iHouse API endpoints. Existing /auth/me in session_router.py confirmed working — no duplication. 6/6 new tests pass.**
