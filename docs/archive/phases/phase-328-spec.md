# Phase 328 — Guest Messaging Copilot Integration Tests

**Status:** Closed
**Prerequisite:** Phase 327 (Availability Broadcaster Integration Tests)
**Date Closed:** 2026-03-12

## Goal

First-ever integration tests for `api/guest_messaging_copilot.py` — the Phase 227 guest messaging draft engine.

## Files Changed

| File | Change |
|------|--------|
| `tests/test_guest_messaging_copilot_integration.py` | NEW — 18 tests |

## Test Coverage

| Group | Tests | What |
|-------|-------|------|
| A — Draft Content | 6 | All 6 intents verified for key content |
| B — Language + Salutation | 4 | en, th, ja, unknown→en fallback |
| C — Tone Variations | 2 | `friendly` vs `professional`, `brief` closing |
| D — Subject Generation | 3 | Distinct subjects, property embedded, pre-arrival date |
| E — Nights Calculation | 3 | 5 nights, 1 night (no plural), missing dates fallback |

## Result

**18 tests. 18 passed. 0 failed. 0.42s. Exit 0.**
