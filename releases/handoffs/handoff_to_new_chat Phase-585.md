> ⚠️ FIRST: Read `docs/core/BOOT.md` before doing anything else.

# Handoff — Phase 585 → Phase 586

**Date:** 2026-03-14
**Last Closed Phase:** 585 — Booking Test Suite Repair
**Next Phase:** 586 (TBD)

## What Was Done This Session

Fixed all 143 test failures caused by the Phase 570 response envelope migration (`ok()`/`err()` wrapper). Updated 17 test files with ~170 targeted assertion changes:

- **Success data wrapping:** `resp.json()["field"]` → `resp.json()["data"]["field"]` for migrated routers (bookings, auth)
- **Error format migration:** `body["code"]` → `body["error"]["code"]`, `body["detail"]` → `body["error"]["message"]`
- **Non-migrated router reverts:** Reverted incorrect `["data"]` wrapping for invite, access_token, org, admin routers
- **Mock chain fix:** Corrected `.single()` → `.limit()` in api_error_standards test mock

## Test Suite Status

**7,380 passed, 0 failed, 22 skipped** (was: 6,884 passed, 482 failed)

## Key Decision: Migrated vs Non-Migrated Routers

Only `bookings_router` and `auth_router` use the new `ok()`/`err()` envelope. All other routers (invite, access_token, org, admin, properties, tasks, financial, etc.) still return flat JSON. The next major effort would be migrating remaining routers to the envelope format.

## Canonical Documents Updated

- `docs/core/current-snapshot.md` — Phase 585, test counts
- `docs/core/work-context.md` — Phase 585, test counts
- `docs/core/phase-timeline.md` — Phase 585 appended
- `docs/core/construction-log.md` — Phase 585 appended
- `docs/archive/phases/phase-585-spec.md` — Created
- `releases/phase-zips/iHouse-Core-Docs-Phase-585.zip` — Created

## Files Modified This Session (17 test files)

| File | Changes |
|------|---------|
| `tests/test_auth_router_contract.py` | Token/tenant_id under `data` |
| `tests/test_auth_logout_contract.py` | Message/token under `data` |
| `tests/test_session_contract.py` | Session data under `data` |
| `tests/test_jwt_role_enforcement.py` | Role info under `data` |
| `tests/test_supabase_auth.py` | User/token under `data` |
| `tests/test_supabase_auth_contract.py` | Token under `data` |
| `tests/test_booking_date_range_contract.py` | Dates + error format |
| `tests/test_booking_list_router_contract.py` | List fields under `data` |
| `tests/test_booking_flags_contract.py` | Flags under `data`, error revert |
| `tests/test_booking_amendment_history_contract.py` | Amendments under `data` |
| `tests/test_booking_search_contract.py` | Sort/filter under `data` |
| `tests/test_booking_flow_e2e.py` | All booking fields under `data` |
| `tests/test_booking_checkin_checkout.py` | Checkin/checkout under `data` |
| `tests/test_multi_tenant_e2e.py` | Booking data + org revert |
| `tests/test_api_error_standards_contract.py` | Error format + mock chain fix |
| `tests/test_invite_flow.py` | Reverted wrong wrapping |
| `tests/test_access_token_system.py` | Reverted wrong wrapping |
