# Phase 363 — Guest Token Flow Hardening

**Status:** Closed
**Prerequisite:** Phase 362 (Webhook Retry & DLQ Dashboard Enhancement)
**Date Closed:** 2026-03-12

## Goal

Harden the guest token issuance and verification flow for production security.

## Design / Files

| File | Change |
|------|--------|
| `src/main.py` | MODIFIED — Added `IHOUSE_GUEST_TOKEN_SECRET` to startup env validation |
| `src/services/guest_token.py` | MODIFIED — Added minimum key length warning (32 bytes per RFC 7518 §3.2) |
| `src/api/guest_token_router.py` | MODIFIED — Added audit logging to verify-token: VERIFY_OK, VERIFY_FAILED, VERIFY_REVOKED |

## Security Audit Summary

| Property | Status |
|----------|--------|
| HMAC-SHA256 signing | ✅ |
| Constant-time compare | ✅ |
| Hash-only DB storage | ✅ |
| Token expiry enforcement | ✅ |
| DB revocation check | ✅ |
| Minimum key length warning | ✅ (Phase 363) |
| Startup env validation | ✅ (Phase 363) |
| Verification audit logging | ✅ (Phase 363) |

## Result

Tests: **24 passed, 4 skipped**. No regressions.
