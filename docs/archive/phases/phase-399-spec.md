# Phase 399 — Access Token System Foundation

**Status:** Closed
**Prerequisite:** Phase 398 (Checkin + Checkout Backend)
**Date Closed:** 2026-03-13

## Goal

Build a universal access token system for invite, onboard, and guest portal flows. HMAC-SHA256 signing, Supabase persistence, full lifecycle management (issue/verify/consume/revoke).

## Invariant

All token operations use HMAC-SHA256. Tokens are hashed before storage. Used/revoked tokens are rejected.

## Design / Files

| File | Change |
|------|--------|
| `src/services/access_token_service.py` | NEW — issue/verify/consume/revoke HMAC tokens |
| `src/api/access_token_router.py` | NEW — admin + public endpoints |
| `supabase/migrations/20260313190000_phase399_access_tokens.sql` | NEW — access_tokens table + RLS |
| `tests/test_access_token_system.py` | NEW — 12 contract tests |
| `src/main.py` | MODIFIED — router registration |

## Result

**12 tests pass, 0 skipped.**
