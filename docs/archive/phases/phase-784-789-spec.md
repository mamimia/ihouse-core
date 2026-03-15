# Phases 784–789 — Staging Activation: Runtime Fixes

**Status:** Closed
**Prerequisite:** Phase 775 (Deployment & Staging Activation complete)
**Date Closed:** 2026-03-15

## Goal

Fix all runtime issues blocking the 5 core frontend user flows (Dashboard, Bookings, Tasks, Financial, Admin Properties) against the live staging backend. Ensure the system runs end-to-end with real data.

## Invariant

- `apply_envelope` remains the only write gate — unchanged.
- External channels remain escalation-only — unchanged.
- All existing invariants preserved.

## Design / Files

| File | Change |
|------|--------|
| `src/tasks/task_router.py` | MODIFIED — case-insensitive status/kind normalization (`.upper()` before validation) |
| `src/api/worker_router.py` | MODIFIED — case-insensitive status/worker_role normalization |
| `src/api/admin_router.py` | MODIFIED — fixed `updated_at_ms` → `updated_at` column drift |
| `src/main.py` | MODIFIED — reordered financial sub-routers before catch-all `/{booking_id}` |
| `ihouse-ui/lib/api.ts` | MODIFIED — auto-unwrap `{ok, data}` envelope in `apiFetch` |
| `ihouse-ui/app/(app)/dashboard/page.tsx` | MODIFIED — null-safe optional chaining for all API results |
| `ihouse-ui/app/(app)/admin/properties/page.tsx` | MODIFIED — added JWT auth token + envelope unwrap to local fetchAPI |

## Result

**278 test items collected, 20 pre-existing E2E/integration failures (unchanged from prior state). Frontend: 54 pages compile. All 5 core flows verified working in browser.**

### Phase Breakdown

| Phase | Title | Outcome |
|-------|-------|---------|
| 784 | Webhook Write-Path Fix | 3 bugs fixed — RLS, column names, query structure |
| 785 | admin_audit_log Table | Created missing table in live DB |
| 786 | Column Drift | 6 columns added to match code expectations |
| 787 | Status/Column Case Mismatch | 5 files fixed — status values now case-insensitive |
| 788 | Frontend Runtime Flow Audit | 5 flows tested — identified 4 critical issues |
| 789 | Frontend Fixes | 7 code fixes across 7 files — all 5 flows working |
