# Phase 321 — Owner + Guest Portal Production Polish

**Status:** Closed
**Prerequisite:** Phase 320 (Notification Dispatch Integration)
**Date Closed:** 2026-03-12

## Goal

Integration tests for both portal authentication flows and data paths.

## Files Changed

| File | Change |
|------|--------|
| `tests/test_portal_integration.py` | NEW — 20 tests |

## Test Coverage

| Group | Tests | What |
|-------|-------|------|
| A — Guest Token Service | 7 | issue, verify, expired, wrong ref, hash, malformed, uniqueness |
| B — Guest Portal HTTP | 4 | booking overview, wifi, rules → 200; missing token → 422 |
| C — Owner Access Service | 5 | grant, invalid role, has_access true/false, get_properties |
| D — Owner Portal HTTP | 4 | list properties, grant → 201, revoke → 200, revoke missing → 404 |

## Result

**20 tests. 20 passed. 0 failed. 1.15s. Exit 0.**
