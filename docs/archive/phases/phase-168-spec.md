# Phase 168 — Push Notification Foundation

**Date closed:** 2026-03-10  
**Status:** ✅ Closed  
**Tests added:** 27 contract tests  
**Total after phase:** 4405 passing

## Goal

Create the multi-channel notification infrastructure: a `notification_channels` table to store per-user channel registrations and a `dispatch_notification()` function that routes to channels in priority order (LINE > FCM > email), fail-isolated per channel.

## Deliverables

### New Files
- `migrations/phase_168_notification_channels.sql` — `notification_channels` table: id UUID PK, tenant_id, user_id, channel_type CHECK('line'|'fcm'|'email'), channel_config JSONB, active BOOLEAN, created_at, updated_at. UNIQUE(tenant_id, user_id, channel_type). RLS. 2 indexes.
- `src/channels/notification_dispatcher.py` — `NotificationMessage`, `ChannelAttempt`, `DispatchResult` dataclasses. `dispatch_notification(message, *, channels, adapters)` — routes to channel adapters in LINE > FCM > email priority order, fail-isolated per channel, never raises. `register_channel()` + `deregister_channel()` upsert helpers. `_lookup_channels()` best-effort DB query. Injectable adapters for testing.
- `tests/test_notification_dispatcher_contract.py` — 27 contract tests

## Key Design Decisions
- Priority order: LINE (fastest ACK) > FCM (mobile push) > email (fallback). Stops at first success.
- Fail-isolated: if LINE fails, always tries FCM then email — never raises, always returns DispatchResult
- FCM adapter is a stub (no real Firebase integration yet)
- Email adapter is a stub (no real SMTP/SES integration yet)
- Injectable adapters pattern allows full contract testing without real channel credentials
- channel_config JSONB stores channel-specific data (LINE user_id, FCM token, email address)

## Architecture Invariants Preserved
- `apply_envelope` is the only write authority to `booking_state` ✅
- Notification dispatch is best-effort — failures never block canonical pipeline ✅
