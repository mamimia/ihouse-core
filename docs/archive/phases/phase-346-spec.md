# Phase 346 — Guest Portal + Owner Portal E2E Tests

**Closed:** 2026-03-12
**Category:** 🌐 Portal / Testing / E2E
**Test file:** `tests/test_portal_e2e.py`

## Summary

End-to-end tests for guest-facing and owner-facing portal endpoints. Covers guest
booking view (WiFi, house rules, access code), guest auth guards (token validation),
owner property listing, rich property summary with financial visibility controls,
and admin grant/revoke access flows.

## Tests Added: 28

### Group A — Guest Booking Overview (4 tests)
- Valid token returns booking, all required fields, nights calculation, house rules list

### Group B — Guest Sub-Endpoints (4 tests)
- WiFi credentials, house rules, 404 for unknown booking

### Group C — Guest Auth Guards (4 tests)
- INVALID token → 401, missing header → 422, empty token → 401, unknown booking → 404

### Group D — Owner List Properties (3 tests)
- List with/without properties, role field verification

### Group E — Owner Property Summary (5 tests)
- Owner sees financials, viewer does not, no access → 403, booking counts + occupancy

### Group F — Admin Grant/Revoke (5 tests)
- Grant → 201, invalid role → 422, duplicate → 422, revoke → 200, nonexistent → 404

### Group G — Access Guards (3 tests)
- Unauthenticated fails, missing fields → 422, path-params-only delete

## System Numbers

| Metric | Before | After |
|--------|--------|-------|
| Tests collected | 6,813 | 6,841 |
| Test files | 229 | 230 |
| New tests | — | 28 |
