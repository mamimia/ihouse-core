# Phase 373 — Deploy Checklist Automation

**Status:** Closed  
**Date Closed:** 2026-03-12

## Goal

Enhance deploy checklist with guest token validation and secret length checks.

## Files Modified

| File | Change |
|------|--------|
| `scripts/deploy_checklist.sh` | MODIFIED — Added IHOUSE_GUEST_TOKEN_SECRET to required vars; added HMAC key minimum length validation (32 chars per RFC 7518 §3.2) |

## Result

Script enhanced with 2 new checks. No regressions.
