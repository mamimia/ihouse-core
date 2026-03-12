# Phase 318 — Frontend E2E Smoke Tests

**Status:** Closed
**Prerequisite:** Phase 317 (Supabase RLS Audit II)
**Date Closed:** 2026-03-12

## Goal

Add Playwright-based E2E smoke tests for the frontend. Verify that all critical pages render without errors.

## Files Changed

| File | Change |
|------|--------|
| `ihouse-ui/package.json` | MODIFIED — added `@playwright/test` dev dep, `test:e2e` script |
| `ihouse-ui/playwright.config.ts` | NEW — Chromium, auto dev server, CI support |
| `ihouse-ui/e2e/smoke.spec.ts` | NEW — 17 tests (14 page loads, 2 login UI, 1 sidebar nav) |

## Test Coverage

| Group | Count | What |
|-------|-------|------|
| Navigation Smoke | 14 | All pages: /, login, dashboard, bookings, tasks, financial, worker, owner, guests, calendar, manager, admin, admin/notifications, admin/dlq |
| Login Page UI | 2 | Form inputs present, submit button present |
| Sidebar Nav | 1 | Desktop viewport nav content |

## Result

**17 tests. 17 passed. 0 failed. 7.3s. Exit 0.**
