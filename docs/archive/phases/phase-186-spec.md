# Phase 186 — Auth & Logout Flow

**Status:** Closed
**Prerequisite:** Phase 185 (Outbound Sync Trigger Consolidation)
**Date Closed:** 2026-03-10

## Goal

Add a complete, secure logout capability to iHouse Core — both server-side cookie invalidation and client-side session clearing. The backend POST /auth/logout endpoint is intentionally unprotected so that users with expired or invalid tokens can still log out cleanly. The frontend auto-logout on 401/403 prevents stale sessions from causing silent data failures.

## Design / Files

| File | Change |
|------|--------|
| `src/api/auth_router.py` | MODIFIED — POST /auth/logout: unprotected, 200 + Set-Cookie Max-Age=0 |
| `ihouse-ui/lib/api.ts` | MODIFIED — performClientLogout(), api.logout(), apiFetch() auto-logout on 401/403 |
| `ihouse-ui/components/LogoutButton.tsx` | NEW — Client Component, sidebar button |
| `ihouse-ui/app/layout.tsx` | MODIFIED — LogoutButton added + flex spacer |
| `tests/test_auth_logout_contract.py` | NEW — 16 contract tests (Groups A-D) |

## Result

**4,386 tests pass. 0 regressions.**
LogoutButton visible in sidebar. POST /auth/logout works with expired token. apiFetch auto-clears on 401/403.
