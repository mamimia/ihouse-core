# Phase 59 — FastAPI App Entrypoint

**Status:** Closed  
**Date:** 2026-03-08  
**Tests:** 292 passed, 2 skipped  

## Objective

Create `src/main.py` — the unified production entrypoint that assembles the FastAPI app and mounts the webhooks router.

## Files Created

| File | Role |
|------|------|
| `src/main.py` | FastAPI app — `/health` + `POST /webhooks/{provider}` |
| `tests/test_main_app.py` | 6 contract tests (TestClient, CI-safe) |

## Key Decisions

- `lifespan` context manager used (not deprecated `@app.on_event`)
- `app/main.py` left unchanged — still serves `/events` legacy path
- No middleware yet: Phase 60 (logging), Phase 61 (JWT), Phase 62 (rate limit)
- `IHOUSE_ENV` env var controls environment label in health response

## Test Coverage

| # | Scenario |
|---|----------|
| 1 | GET /health → 200, body has status/version/env |
| 2 | POST /webhooks/bookingcom routed through assembled app |
| 3 | Unknown route → 404 not 500 |
| 4 | /health requires no auth |
| 5 | app.title == "iHouse Core" |
| 6 | app.version == "0.1.0" |
