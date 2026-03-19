# Phase 855 — LINE Integration E2E Proof

**Status:** Closed
**Prerequisite:** Phase 854 (Route Guard Test Suite Validation)
**Date Closed:** 2026-03-20

## Goal

Prove the LINE Messaging API integration end-to-end: inbound webhook receipt with userId capture, worker routing sync via `_sync_channels()`, and real outbound message delivery to a worker's LINE client. Establish `docs/integrations/` as the durable operational readiness structure for all messaging integrations.

## Invariant (if applicable)

- `notification_channels` remains the single source of truth for worker LINE routing
- `_sync_channels()` auto-syncs `comm_preference` updates to `notification_channels` on every staff profile save
- LINE Channel Secret and Channel Access Token are stored separately with distinct purposes

## Design / Files

| File | Change |
|------|--------|
| `src/api/permissions_router.py` | MODIFIED — added `_sync_channels()` helper; integrated into POST and PATCH endpoints |
| `src/api/line_webhook_router.py` | MODIFIED — added native LINE event interception and userId logging |
| `src/channels/notification_dispatcher.py` | MODIFIED — `_default_line_adapter` fetches token from `tenant_integrations` and dispatches via LINE API |
| `tests/test_notification_dispatch_integration.py` | MODIFIED — fixed adapter fixture signatures (2-arg → 4-arg) |
| `docs/integrations/README.md` | NEW — operational readiness folder README |
| `docs/integrations/integration-status-matrix.md` | NEW — aggregate status matrix for all integrations |
| `docs/integrations/line-production-readiness.md` | NEW — LINE setup guide, proof summary, current limitations |
| `docs/integrations/telegram-production-readiness.md` | NEW — Telegram readiness tracker |
| `docs/integrations/whatsapp-production-readiness.md` | NEW — WhatsApp readiness tracker |
| `docs/integrations/local-webhook-testing.md` | NEW — guide for local webhook testing with ngrok |

## Result

**54 tests pass (permissions + notification dispatcher + dispatch integration). 0 failed.**
LINE inbound webhook proven, userId captured (`Ue6ef0a469d844632061fc0a3f04c7e2e`), worker binding proven with `notification_channels` sync, and real outbound LINE message delivered (HTTP 200, sentMessages ID `605849683361005587`).
