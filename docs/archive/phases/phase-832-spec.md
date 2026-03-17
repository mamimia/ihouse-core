# Phase 832 — Worker Task Start + Guest Name Enrichment

**Status:** Closed
**Prerequisite:** Phase 831 (Cleaner Role + Auth Hardening)
**Date Closed:** 2026-03-17

## Goal

Add the missing `PATCH /worker/tasks/{id}/start` endpoint for the ACKNOWLEDGED → IN_PROGRESS transition, and enrich booking list/detail responses with `guest_name`.

## Invariant

- Task lifecycle: PENDING → ACKNOWLEDGED → IN_PROGRESS → COMPLETED. The `start` endpoint fills the missing IN_PROGRESS transition.
- `guest_name` is exposed in booking responses but remains optional (nullable).

## Design / Files

| File | Change |
|------|--------|
| `src/api/worker_router.py` | MODIFIED — added `PATCH /worker/tasks/{task_id}/start` (ACKNOWLEDGED → IN_PROGRESS) |
| `src/api/bookings_router.py` | MODIFIED — added `guest_name` to booking list + detail responses |
| `ihouse-ui/app/(public)/dev-login/page.tsx` | MODIFIED — minor dev-login page update |

## Result

Full task lifecycle transition support (PENDING → ACK → IN_PROGRESS → COMPLETED). Guest names visible in booking API responses.
