# Phase 402 — Onboard Token Flow

**Status:** Closed
**Prerequisite:** Phase 399 (Access Token System)
**Date Closed:** 2026-03-13

## Goal

Build property onboarding via access tokens. Validate token, submit property details → creates property in `pending_review` status. Token consumed on submit.

## Design / Files

| File | Change |
|------|--------|
| `src/api/onboard_token_router.py` | NEW — GET /onboard/validate/{token}, POST /onboard/submit |
| `tests/test_onboard_token_flow.py` | NEW — 6 contract tests |
| `src/main.py` | MODIFIED — router registration |

## Result

**6 tests pass, 0 skipped.**
