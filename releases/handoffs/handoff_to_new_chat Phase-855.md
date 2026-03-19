> ⚠️ FIRST: Read `docs/core/BOOT.md` before doing anything else.

# Handoff — Phase 855 → Phase 856

## Current Phase
Phase 856 — Next Phase (unassigned)

## Last Closed Phase
Phase 855 — LINE Integration E2E Proof (2026-03-20)

## What Phase 855 Accomplished
1. **LINE inbound webhook proven** — real LINE message → `POST /line/webhook` → HTTP 200, `source.userId` captured (`Ue6ef0a469d844632061fc0a3f04c7e2e`)
2. **Worker binding proven** — userId bound to worker เเพรวา ตาลพันธ์ via `PATCH /permissions/{user_id}`, `_sync_channels()` auto-created `notification_channels` row
3. **Outbound LINE message proven** — real push message delivered via LINE Messaging API, HTTP 200, sentMessages ID confirmed
4. **Integration docs created** — `docs/integrations/` folder with 6 files: README, status matrix, LINE/Telegram/WhatsApp readiness, local webhook testing guide
5. **Test fix** — notification dispatch integration test adapter signatures fixed (2-arg → 4-arg), 54 tests passing

## Key Files Changed
| File | Change |
|------|--------|
| `src/api/permissions_router.py` | `_sync_channels()` helper added |
| `src/api/line_webhook_router.py` | Native LINE event userId logging |
| `src/channels/notification_dispatcher.py` | `_default_line_adapter` with tenant_integrations token lookup |
| `tests/test_notification_dispatch_integration.py` | Adapter fixture signature fix |
| `docs/integrations/*` | NEW — 6 operational readiness docs |

## Current LINE Integration Status
- Inbound webhook: **action-proven**
- Worker binding + notification_channels sync: **action-proven**
- Outbound send: **action-proven**
- Production ready: **partial** — needs permanent domain, secret rotation, auto-pairing flow

## Remaining LINE Limitations
- Worker LINE userId binding is manual (captured from logs → entered in staff profile)
- Webhook tested via ngrok dev tunnel, not final production domain
- Channel Secret should be rotated (was exposed during initial setup)
- Token stored in `tenant_integrations.credentials` JSONB, not application-encrypted

## Suggested Next Objectives
- Continue operational surface work (admin preview, dashboard flight cards, staff management)
- LINE auto-pairing flow for worker onboarding
- Permanent production webhook domain setup
- Channel Secret rotation

## Environment Notes
- Backend: Python/FastAPI on port 8000
- Frontend: Next.js (ihouse-ui) on port 3000
- Supabase: `reykggmlcehswrxjviup`
- LINE Channel ID: 2009545412
- Ngrok domain: `subdeducible-leonia-explicative.ngrok-free.dev` (dev only)
