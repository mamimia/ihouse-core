# Phase 299 — Notification Dispatch Layer

**Status:** Closed  
**Prerequisite:** Phase 298 (Guest Portal + Owner Portal Auth)  
**Date Closed:** 2026-03-12

## Goal

Add a real outbound notification layer — SMS via Twilio and Email via SendGrid. Introduce a `notification_log` table to track all dispatch activity. Add a one-step `guest-token-send` endpoint that issues a Phase 298 guest token AND delivers the portal link to the guest in a single API call.

## Design Decisions

- **Dry-run mode** when env vars absent — always logs status, never raises, returns `status='dry_run'`
- **Notification log** is the single source of truth — every dispatch creates a row regardless of outcome
- **Body preview (200 chars max)** stored in DB — PII-minimal 
- Raw token is never returned in `guest-token-send` response — issued internally and sent directly
- Provider packages (twilio, sendgrid) imported at module level with `try/except` — optional deps, no crash if not installed
- Domaniqo branding in all guest messages ("— Domaniqo")

## Files Changed

| File | Change |
|------|--------|
| `artifacts/supabase/migrations/phase-299-notification-log.sql` | NEW — notification_log table |
| `src/services/notification_dispatcher.py` | NEW — 5 functions (dispatch_sms, dispatch_email, dispatch_guest_token_notification, list_notification_log, helpers) |
| `src/api/notification_router.py` | NEW — 4 endpoints |
| `tests/test_notification_dispatch.py` | NEW — 20 tests (all pass) |
| `src/main.py` | MODIFIED — notification_router registered |

## API Surface

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /notifications/send-sms | JWT | Send SMS via Twilio |
| POST | /notifications/send-email | JWT | Send Email via SendGrid |
| POST | /notifications/guest-token-send | JWT | Issue guest token + send link to guest (1-step) |
| GET | /notifications/log | JWT | List notification dispatch history |

## Env Vars Required

| Var | Purpose |
|-----|---------|
| `IHOUSE_TWILIO_SID` | Twilio Account SID |
| `IHOUSE_TWILIO_TOKEN` | Twilio Auth Token |
| `IHOUSE_TWILIO_FROM` | Sending phone number (E.164) |
| `IHOUSE_SENDGRID_KEY` | SendGrid API key |
| `IHOUSE_SENDGRID_FROM` | Sending email address |

## Result

**20 new tests pass (20/20). All existing tests unaffected. Exit 0.**
