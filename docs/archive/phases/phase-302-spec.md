# Phase 302 — Guest Portal Token Flow E2E Integration Test

**Status:** Closed  
**Prerequisite:** Phase 298 (Guest Token Service), Phase 299 (Notification Dispatch), Phase 301 (Owner Portal Data)  
**Date Closed:** 2026-03-12

## Goal

Write comprehensive E2E contract tests that exercise the full guest token lifecycle — from issuance through notification dispatch through verification — using real HMAC cryptography against mocked Supabase. Also include a live Supabase integration suite gated behind `IHOUSE_ENV=staging`.

## Files Added

| File | Description |
|------|-------------|
| `tests/test_guest_token_e2e.py` | **NEW** — 7 test suites, 24 in-process tests + 4 live integration |

## Test Suites (24 in-process, 4 staged)

| Suite | Tests | What is covered |
|-------|-------|-----------------|
| A. TestIssueGuestToken | 5 | Token format, expiry, per-ref uniqueness, email embedding, 7d default TTL |
| B. TestVerifyGuestToken | 5 | Valid claims, wrong ref, tampered sig, malformed, expired |
| C. TestRecordGuestToken | 3 | Hash stored (not raw token), row returned without token_hash, DB error → `{}` |
| D. TestGuestTokenFullServiceFlow | 4 | issue→record→verify chain, SMS dispatch, both channels, no-recipient error |
| E. TestVerifyTokenEndpointE2E | 4 | POST /guest/verify-token: valid 200, wrong ref 401, tampered 401, missing body 422 |
| F. TestGuestTokenSendRouterE2E | 3 | POST /notifications/guest-token-send: SMS 201, email 201, no-recipient 422 |
| G. TestGuestTokenLiveIntegration | 4 | Live Supabase: table accessibility + full issue→verify against real DB (staging only) |

## Key Design Notes

- All in-process tests use real HMAC via `issue_guest_token()` — no mocked crypto
- `_log_notification` patched to return `{"notification_id": ..., "status": "pending"}` (correct dict type)
- Live integration suite uses `@pytest.mark.integration` + autouse skip unless `IHOUSE_ENV=staging`
- The `notifications` key in the router response is a list (matches `dispatch_guest_token_notification` which returns `list[dict]`)

## Result

**24 passed, 4 skipped (live integration suite), 0 failed**
