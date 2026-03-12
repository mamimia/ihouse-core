# Phase 297 — Auth Session Management + Real Login Flow

**Status:** Closed
**Prerequisite:** Phase 296 (Multi-Tenant Organization Foundation)
**Date Closed:** 2026-03-12

## Goal

Add server-side session management on top of JWT-based auth. Sessions are created at login and revoked at logout, enabling "sign out everywhere" and audit trails without replacing the existing JWT architecture.

## Design Decisions

- **JWT remains the transport** — no existing endpoint changed. `api.auth.verify_jwt()` still validates JWT signature.
- **Session layer is additive** — `/auth/login-session` is the new preferred login path; `/auth/token` (Phase 179) still works for dev compat.
- **Token stored as SHA-256 hash only** — never stored in plaintext in the DB.
- **Best-effort session creation** — if the DB insert fails, the JWT is still returned. Login never errors out due to session failure.
- **`/auth/me` works for all token types** — Supabase Auth tokens, `/auth/token` dev tokens, and `/auth/login-session` tokens all work; `has_session` indicates whether the token is tracked.

## Files Changed

| File | Change |
|------|--------|
| `artifacts/supabase/migrations/phase-297-user-sessions.sql` | NEW — user_sessions + active_sessions view |
| `src/services/session.py` | NEW — 5 service functions |
| `src/api/session_router.py` | NEW — 5 endpoints |
| `tests/test_session_contract.py` | NEW — 25 contract tests (all pass) |
| `src/main.py` | MODIFIED — session_router registered (Phase 297) |

## API Surface

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /auth/login-session | None | Login: JWT + session record |
| GET | /auth/me | JWT | Identity + session info |
| POST | /auth/logout-session | JWT | Revoke current session |
| GET | /auth/sessions | JWT | List active sessions |
| DELETE | /auth/sessions | JWT | Revoke all sessions |

## Result

**25 new tests pass (25/25). All existing tests unaffected. Exit 0.**
