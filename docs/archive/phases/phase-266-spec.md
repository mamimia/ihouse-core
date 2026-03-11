# Phase 266 — HTTP-level E2E Booking Flow Integration Test

**Status:** Closed
**Prerequisite:** Phase 265 (Test Suite Repair + Documentation Integrity Sync)
**Date Closed:** 2026-03-11

## Goal

Add an HTTP-level end-to-end test suite for the booking API surface using
FastAPI `TestClient` and mocked Supabase. CI-safe — no live DB, no staging
environment required.

Fills the gap between:
- Existing in-process pipeline harness (no HTTP, no DB)
- Existing staging smoke tests (live Supabase, `IHOUSE_ENV=staging` required)

## Invariant

All previous booking router invariants hold:
- Endpoints are read-only for GET routes (never write to booking_state or event_log)
- Tenant isolation enforced in all mocked Supabase queries
- PATCH /flags is the only write endpoint; uses upsert on (booking_id, tenant_id)

## Design / Files

| File | Change |
|------|--------|
| `tests/test_booking_flow_e2e.py` | NEW — 26 tests, 4 groups (A-D) |

**Test groups:**
- **Group A** (6 tests): `GET /bookings/{id}` — 200 shape, required keys, flags=None, 404, status values
- **Group B** (10 tests): `GET /bookings` — count/limit defaults, filter validation (status/sort/date), sort meta in response, empty list
- **Group C** (4 tests): `GET /bookings/{id}/amendments` — shape, empty list, 404
- **Group D** (6 tests): `PATCH /bookings/{id}/flags` — 200 upsert, flags key in response, 400 empty body, 400 unknown keys, 400 non-bool, 404

## Result

**6,050 tests pass, 13 skipped, 0 failures.**
26 new CI-safe HTTP-level E2E tests covering the booking query surface.
