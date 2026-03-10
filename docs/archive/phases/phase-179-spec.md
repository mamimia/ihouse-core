# Phase 179 — UI Auth Flow

**Status:** Closed  
**Prerequisite:** Phase 178 (Worker Mobile UI)  
**Date Closed:** 2026-03-10

## Goal

Wire end-to-end authentication in the UI. Workers, managers, and admins must log in before accessing any protected route. Token stored in `localStorage`, sent as `Authorization: Bearer` on every API call. Unauthorised routes redirect to `/login`.

## Design / Files

| File | Change |
|------|--------|
| `src/api/auth_router.py` | NEW — `POST /auth/token` (dev token issuer, HS256) |
| `src/main.py` | MODIFIED — register auth_router |
| `ihouse-ui/app/login/page.tsx` | NEW — login form (tenant_id + secret) |
| `ihouse-ui/middleware.ts` | NEW — Next.js middleware route guard |
| `ihouse-ui/lib/api.ts` | MODIFIED — add `login()` call |

## Auth flow

```
User → /login → POST /auth/token {tenant_id, secret}
             ← {token: "eyJ..."}
             → localStorage.setItem('ihouse_token', token)
             → redirect /dashboard

All pages → middleware.ts checks localStorage token
         → if missing → redirect /login
```

## Result

**TBD.**
