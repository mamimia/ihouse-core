# Handoff to New Chat — Phase 300 (Platform Checkpoint XIV)

**Date:** 2026-03-12  
**Current Phase:** 301  
**Last Closed:** Phase 300 — Platform Checkpoint XIV

---

## What was built in this session (Phases 297–300)

### Phase 297 — Auth Session Management + Real Login Flow
- `user_sessions` table — SHA-256 JWT hash, expiry, revocation
- `src/services/session.py` — 5 pure functions
- `src/api/session_router.py` — 5 endpoints (`/auth/login-session`, `/auth/me`, `/auth/logout-session`, `/auth/sessions` GET+DELETE)
- `tests/test_session_contract.py` — 25 tests (all pass)

### Phase 298 — Guest Portal + Owner Portal Real Authentication
- `guest_tokens` + `owner_portal_access` tables
- `src/services/guest_token.py` — HMAC-SHA256 token issue/verify + owner access helpers (9 functions)
- `src/api/guest_token_router.py` — 2 endpoints (issue, verify)
- `src/api/owner_portal_router.py` — 4 endpoints (list properties, summary, grant/revoke)
- `tests/test_guest_owner_auth.py` — 35 tests (all pass)

### Phase 299 — Notification Dispatch Layer
- `notification_log` table — tracks all outbound SMS + email dispatch
- `src/services/notification_dispatcher.py` — dispatch_sms (Twilio), dispatch_email (SendGrid), dispatch_guest_token_notification, list_notification_log
- `src/api/notification_router.py` — 4 endpoints (`/notifications/send-sms`, `/notifications/send-email`, `/notifications/guest-token-send`, `/notifications/log`)
- `tests/test_notification_dispatch.py` — 20 tests (all pass)
- Dry-run mode when env vars absent. Domaniqo-branded messages.

### Phase 300 — Platform Checkpoint XIV
- Full test suite: **6,329 pass, 13 skip, 4 pre-existing env-dependent failures**
- current-snapshot.md updated (test count, new env vars for Phases 298–299)
- Forward plan documented

---

## Test Suite Status

**6,329 passing. 13 skipped.**

4 known pre-existing failures (not regressions):
- `test_health_returns_200`
- `test_health_requires_no_auth`
- `test_health_still_200_with_middleware`
- `test_g1_degraded_probe_sets_result_degraded`

These require a live Supabase connection. They have failed since Phase 64.

---

## Critical Env Vars (NEW in 297–299)

| Var | Purpose |
|-----|---------|
| `IHOUSE_GUEST_TOKEN_SECRET` | HMAC-SHA256 secret for guest tokens (required, Phase 298) |
| `IHOUSE_TWILIO_SID` | Twilio Account SID (Phase 299) |
| `IHOUSE_TWILIO_TOKEN` | Twilio Auth Token (Phase 299) |
| `IHOUSE_TWILIO_FROM` | Sending phone E.164 (Phase 299) |
| `IHOUSE_SENDGRID_KEY` | SendGrid API key (Phase 299) |
| `IHOUSE_SENDGRID_FROM` | Sending email address (Phase 299) |

---

## New DB Tables (apply migrations)

```
artifacts/supabase/migrations/phase-297-user-sessions.sql
artifacts/supabase/migrations/phase-298-guest-owner-auth.sql
artifacts/supabase/migrations/phase-299-notification-log.sql
```

---

## Forward Plan (Phase 301+)

| Phase | Description |
|-------|-------------|
| 301 | Real Booking Data Seeding for Owner Portal |
| 302 | Guest Portal Token Flow E2E Integration Test |
| 303 | Supabase Production Migration Run |
| 304 | Pre-Production Smoke Test Suite |

---

## Key Invariants (unchanged)

- `apply_envelope` is the single write authority
- `event_log` is append-only
- `tenant_id` from JWT `sub` only — never from payload
- HMAC is primary for guest tokens — DB revocation is best-effort
- Financial data in owner portal scoped to `role='owner'` only

---

**BOOT.md:** This handoff is placed in `releases/handoffs/`. ZIP in `releases/phase-zips/`.
