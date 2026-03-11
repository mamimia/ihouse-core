# Phase 276 — Real JWT Authentication Flow

**Status:** Closed
**Prerequisite:** Phase 275 (Deployment Readiness Audit)
**Date Closed:** 2026-03-11

## Goal

Integrate Supabase Auth JWT support into the authentication layer, replacing the implicit dev bypass (secret absent = bypass) with an explicit `IHOUSE_DEV_MODE=true` flag. Both Supabase-issued and internally-issued JWTs are now accepted.

## Changes

### `src/api/auth.py` — Rewrote

| Change | Detail |
|--------|--------|
| **Supabase JWT support** | Tokens with `aud="authenticated"` or `role="authenticated"` are now accepted alongside internal self-issued tokens. Both validated with the same `IHOUSE_JWT_SECRET` |
| **Dev bypass hardened** | Old: implicit when `IHOUSE_JWT_SECRET` absent. New: requires `IHOUSE_DEV_MODE=true` explicitly. Missing secret without dev mode → HTTP 503 |
| **`decode_jwt_claims(token, secret)`** | New helper for JWT introspection (used by `/auth/supabase-verify`) |
| **`_ENV_VAR` alias** | Backward-compat alias for existing tests that imported the old constant |

### `src/api/auth_router.py` — Added

`POST /auth/supabase-verify` — accepts a JWT (Supabase-issued or internal), validates it, returns decoded claims:
```json
{
  "valid": true,
  "sub": "user-uuid",
  "aud": "authenticated",
  "role": "authenticated",
  "email": "user@example.com",
  "exp": 1234567890,
  "token_type": "supabase"
}
```

### `tests/test_supabase_auth_contract.py` — NEW (25 tests)

- Group A (4): `IHOUSE_DEV_MODE=true` bypass
- Group B (3): No secret + not dev mode → 503
- Group C (5): Supabase Auth token accepted (aud=authenticated)
- Group D (3): Internal tokens still accepted (backward compat)
- Group E (7): `/auth/supabase-verify` endpoint
- Group F (3): `decode_jwt_claims` helper

### `tests/test_auth.py` — Updated (3 tests)

- test_6 (`test_dev_mode_returns_dev_tenant`): now sets `IHOUSE_DEV_MODE=true`
- tests 1, 2: now explicitly clear `IHOUSE_DEV_MODE` to avoid env pollution

## Test Results

```
33 auth tests passed (8 existing + 25 new)
Full suite: exit 0
```

## Supabase Production Use

To use Supabase Auth JWTs in production:
1. Set `IHOUSE_JWT_SECRET` = Supabase project JWT secret (Settings → API → JWT Secret)
2. Do NOT set `IHOUSE_DEV_MODE`
3. Clients authenticate via Supabase Auth JS client, then pass the session JWT in `Authorization: Bearer`
4. `sub` claim = Supabase user UUID (used as `tenant_id` throughout the system)
