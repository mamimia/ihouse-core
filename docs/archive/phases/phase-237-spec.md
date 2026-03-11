# Phase 237 — Staging Environment & Integration Tests

**Status:** Closed
**Prerequisite:** Phase 236 — Guest Communication History
**Date Closed:** 2026-03-11

## Goal

237 phases of development with zero integration tests against a real database. This phase adds the staging infrastructure layer: a docker-compose configuration pointing at Supabase local, and a suite of 10 smoke tests that verify the most critical data paths end-to-end.

## Invariant (Phase 237)

Integration tests under `tests/integration/` are **automatically skipped** in normal `pytest` runs. They only execute when `IHOUSE_ENV=staging` is set in the environment. This ensures the unit test suite remains fast and DB-free.

## Design / Files

| File | Change |
|------|--------|
| `docker-compose.staging.yml` | NEW — staging compose with `api` + `tests` services |
| `.env.staging.example` | NEW — documents required staging env vars |
| `tests/integration/conftest.py` | NEW — `@pytest.mark.integration` + skipif guard + DB/auth fixtures |
| `tests/integration/test_smoke_integration.py` | NEW — 10 smoke tests |
| `docs/archive/phases/phase-237-spec.md` | NEW — this file |

## Smoke Tests

| # | Tests |
|---|-------|
| 1 | `/health` → 200 |
| 2 | POST ingest → `booking_state` row created |
| 3 | Booking retrieval from `booking_state` |
| 4 | `booking_financial_facts` table accessible |
| 5 | `tasks` table accessible |
| 6 | `GET /worker/availability` → 200 |
| 7 | `POST /guest-messages/{booking_id}` → `guest_messages_log` row |
| 8 | `GET /guest-messages/{booking_id}` → timeline with message |
| 9 | `GET /conflicts` → `{conflicts, summary}` keys |
| 10 | `GET /admin/conflicts/dashboard` → `{summary, by_property, timeline, narrative}` |

## Result

**Unit suite: 5,543/5,543 pass. Exit 0.**
Integration tests: 10 smoke tests written. Execute with `IHOUSE_ENV=staging pytest tests/integration/ -v`.
