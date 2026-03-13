# Phase 585 — Booking Test Suite Repair

**Status:** Closed
**Prerequisite:** Phase 584 (Platform Checkpoint XXVII)
**Date Closed:** 2026-03-14

## Goal

Fix all 143 test failures caused by the Phase 570 response envelope migration (`ok()`/`err()` wrapper on `bookings_router` and `auth_router`). Tests expected old flat JSON responses but the routers now return `{ok: true, data: {...}}` / `{ok: false, error: {code, message}}`. Also revert incorrect `["data"]` wrapping previously applied to non-migrated routers (invite, access_token, org, admin).

## Invariant (if applicable)

No new invariants. Existing envelope contract enforced:
- Migrated routers (`bookings_router`, `auth_router`) return `{ok, data}` / `{ok, error}`.
- Non-migrated routers continue returning flat JSON.

## Design / Files

| File | Change |
|------|--------|
| `tests/test_auth_router_contract.py` | MODIFIED — token/tenant_id under `data` |
| `tests/test_auth_logout_contract.py` | MODIFIED — message/token under `data` |
| `tests/test_session_contract.py` | MODIFIED — session data under `data` |
| `tests/test_jwt_role_enforcement.py` | MODIFIED — role info under `data` |
| `tests/test_supabase_auth.py` | MODIFIED — user/token under `data` |
| `tests/test_supabase_auth_contract.py` | MODIFIED — token under `data` |
| `tests/test_booking_date_range_contract.py` | MODIFIED — dates + error format |
| `tests/test_booking_list_router_contract.py` | MODIFIED — list fields under `data` |
| `tests/test_booking_flags_contract.py` | MODIFIED — flags under `data`, error revert |
| `tests/test_booking_amendment_history_contract.py` | MODIFIED — amendments under `data` |
| `tests/test_booking_search_contract.py` | MODIFIED — sort/filter under `data` |
| `tests/test_booking_flow_e2e.py` | MODIFIED — all booking fields under `data` |
| `tests/test_booking_checkin_checkout.py` | MODIFIED — checkin/checkout under `data` |
| `tests/test_multi_tenant_e2e.py` | MODIFIED — booking `data` + org revert |
| `tests/test_api_error_standards_contract.py` | MODIFIED — error format + mock chain fix |
| `tests/test_invite_flow.py` | MODIFIED — reverted wrong wrapping |
| `tests/test_access_token_system.py` | MODIFIED — reverted wrong wrapping |

## Result

**7,380 tests pass, 0 failed, 22 skipped.**
143 assertion failures fixed across 17 test files. ~170 targeted assertion changes. Zero regression — all previously passing tests continue to pass.
