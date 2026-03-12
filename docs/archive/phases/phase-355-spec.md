# Phase 355 — Cancel/Amend Adapter Test Repair (Closed) — 2026-03-12

## Category
🔧 Test Isolation / Environment Repair

## Problem
30 pre-existing test failures in `test_sync_cancel_contract.py` (10) and `test_sync_amend_contract.py` (20).
All failing tests returned `dry_run` instead of expected `ok`/`failed` — adapter never reached HTTP path.

## Root Cause
`test_outbound_sync_fullchain_integration.py` line 24: `os.environ.setdefault("IHOUSE_DRY_RUN", "true")`
This module-level statement executes during pytest collection (before the conftest session fixture captures its snapshot).
Result: `IHOUSE_DRY_RUN=true` leaks to every subsequent test in the session, causing all outbound adapter
HTTP-path tests to take the dry-run early-return branch.

`conftest.py` did not include `IHOUSE_DRY_RUN` or adapter API key env vars in its cleanup list.

## Fix
1. **Removed** module-level `os.environ.setdefault("IHOUSE_DRY_RUN", "true")` from `test_outbound_sync_fullchain_integration.py`
2. **Added** `IHOUSE_DRY_RUN`, `AIRBNB_API_KEY`, `BOOKINGCOM_API_KEY`, `EXPEDIA_API_KEY`, `VRBO_API_KEY` to `_SENSITIVE_VARS` in `conftest.py`
3. **Added** `os.environ["IHOUSE_DRY_RUN"] = "false"` as explicit session default in `conftest.py`

## Files Changed
- `tests/conftest.py` — expanded `_SENSITIVE_VARS` list + explicit DRY_RUN=false default
- `tests/test_outbound_sync_fullchain_integration.py` — removed module-level IHOUSE_DRY_RUN

## Test Results
- Before: 7,069 collected, 7,022 passed, 30 failed, 17 skipped
- After:  7,069 collected, 7,043 passed, 9 failed, 17 skipped
- Net: +21 passed (30 cancel/amend fixed, 9 remaining are infrastructure/Supabase tests)

## Remaining 9 Failures (NOT from this phase)
- 5 × test_booking_amended_e2e (require live Supabase)
- 2 × test_main_app health endpoint (Supabase connectivity → 503)
- 1 × test_logging_middleware health (same 503)
- 1 × test_health_enriched_contract degraded probe
