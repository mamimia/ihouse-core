# Phase 287 — Frontend Foundation

**Date:** 2026-03-12
**Category:** 🎨 Frontend

## Objective

Audit and complete the Domaniqo/iHouse Next.js frontend shell. The frontend was already substantially built in Phases 153–257. This phase identifies and closes remaining gaps.

## Audit Finding

`ihouse-ui/` was already at an advanced state:
- **18 pages** built: login, dashboard, bookings, financial, tasks, worker, admin, guests, calendar, manager, owner, statements, DLQ
- **Protected route middleware** (`middleware.ts`) — cookie/localStorage token gate
- **API client** (`lib/api.ts`) — typed fetch wrapper with auto-logout on 401/403
- **Domaniqo branding** — Midnight Graphite palette, Manrope/Inter fonts, token CSS
- **Language switcher** — bilingual support (Phase 193)
- **Auth flow** — login page fully connected to backend `/auth/login`

## Gaps Found and Closed

### 1. `ihouse-ui/app/page.tsx` — MODIFIED

Root path was showing the default Next.js boilerplate ("To get started, edit the page.tsx file."). Replaced with a proper server-side redirect to `/dashboard`. Middleware sends unauthenticated users to `/login`.

**Before:** Default Next.js template
**After:** `redirect('/dashboard')` — clean entry point

### 2. `ihouse-ui/.env.local.example` — NEW

Frontend environment variable reference was not documented. Added:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## File Summary

| File | Action |
|------|--------|
| `ihouse-ui/app/page.tsx` | MODIFIED — root redirect to /dashboard |
| `ihouse-ui/.env.local.example` | NEW — env var reference for developers |
| `docs/archive/phases/phase-287-spec.md` | NEW |

## Test Results

Full Python test suite: **6,216 passed · 0 failed · exit 0**
TypeScript: `tsc --noEmit` passes (no type errors)
