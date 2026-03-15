# Phase 796 — Staging Deploy & Smoke Test + Bootstrap Fix

**Status:** Closed
**Prerequisite:** Phase 795 (First Real Admin User)
**Date Closed:** 2026-03-15

## Goal

Full staging smoke test: verify all core API endpoints respond correctly with live data. Fix any bootstrap issues.

## Design / Files

| File | Change |
|------|--------|
| `docker-compose.yml` | USED — staging deploy |

## Result

Bootstrap: all 4 tables upsert successfully (`bootstrap_complete`). Role: admin resolves correctly. Smoke: health, summary, auth/me, bookings, tasks — all pass. Frontend: 200 OK (39KB) via compose.
