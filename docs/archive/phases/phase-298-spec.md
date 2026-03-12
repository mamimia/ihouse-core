# Phase 298 — Guest Portal + Owner Portal Real Authentication

**Status:** Closed  
**Prerequisite:** Phase 297 (Auth Session Management)  
**Date Closed:** 2026-03-12

## Goal

Replace the Phase 262 stub guest token validation with real cryptographic (HMAC-SHA256) tokens. Add a DB-backed owner portal with property-level access grants.

## Design Decisions

- **HMAC-SHA256** signed guest tokens — `IHOUSE_GUEST_TOKEN_SECRET` (separate from JWT secret)
- Token format: `base64url(booking_ref:email:exp).HMAC-sig` — opaque to guest
- **Raw token returned exactly once** — only SHA-256 hash stored in DB
- **HMAC is primary trust** — DB check (revocation) is best-effort
- Owner portal access is **property-scoped** — owner can only see granted properties
- Financial data shown only for `role = 'owner'` (not `'viewer'`)

## Files Changed

| File | Change |
|------|--------|
| `artifacts/supabase/migrations/phase-298-guest-owner-auth.sql` | NEW — guest_tokens + owner_portal_access |
| `src/services/guest_token.py` | NEW — 9 functions |
| `src/api/guest_token_router.py` | NEW — 2 endpoints |
| `src/api/owner_portal_router.py` | NEW — 4 endpoints |
| `tests/test_guest_owner_auth.py` | NEW — 35 tests (all pass) |
| `src/main.py` | MODIFIED — guest_token_router + owner_portal_router registered |

## API Surface

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /admin/guest-token/{booking_ref} | JWT | Issue signed guest token |
| POST | /guest/verify-token | None | Guest verifies their token |
| GET | /owner/portal | JWT | List owner's properties |
| GET | /owner/portal/{property_id}/summary | JWT + access | Property summary |
| POST | /admin/owner-access | JWT | Grant owner property access |
| DELETE | /admin/owner-access/{oid}/{pid} | JWT | Revoke owner access |

## Result

**35 new tests pass (35/35). All existing tests unaffected. Exit 0.**
