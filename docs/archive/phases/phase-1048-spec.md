# Phase 1048 — Guest Chat Model: OM Routing + Dossier Thread + Inbox Backend

**Status:** SURFACED (backend proven in DB; Dossier Chat tab surfaced; Inbox backend built)
**Prerequisite:** Phase 1047-polish
**Date Opened:** 2026-04-03
**Branch:** `checkpoint/supabase-single-write-20260305-1747`

## Goal

Establish the canonical guest-to-host messaging model end-to-end:
- Guest message is routed to the correct Operational Manager on insert
- Staff inbox has a real backend to query
- Guest Dossier surfaces a dedicated Chat tab showing per-stay thread history
- Routing ownership is stamped at insert time via `assigned_om_id`

## Invariant

- **Conversation is per stay (booking_id), not guest-lifetime.**  
  One thread per `booking_id`. No cross-stay message leakage.
- **`assigned_om_id` is routing scaffold** — stamps the OM on message insert via `resolve_conversation_owner()`.  
  This is not a final long-term ownership model. It will be extended in later phases.
- **`tenant_id` is never the personal sender identity.** All host replies use `sender_id = caller's user_id`.
- **Guest Dossier Chat tab is the canonical per-stay history surface** for staff.

## Design / Files

| File | Change |
|------|--------|
| `src/services/guest_messaging.py` | NEW — `resolve_conversation_owner()`: resolves OM from `staff_property_assignments` ordered by priority, falls back to admin |
| `src/api/guest_portal_router.py` | MODIFIED — `guest_send_message()`: now stamps `assigned_om_id` from resolver on every guest insert |
| `src/api/guest_inbox_router.py` | NEW — `GET /manager/guest-inbox`: returns all threads scoped to caller's assigned properties |
| `ihouse-ui/app/(app)/guests/[id]/page.tsx` | MODIFIED — Added Chat tab; fetches per-stay messages from `guest_chat_messages`, renders as thread per stay |

## Result

**Backend — PROVEN in DB:** `assigned_om_id = 10de26bb-...` (Nana G's user_id) correctly stamped on guest messages for KPG-500. Resolver runs successfully on message insert.

**Dossier Chat tab — SURFACED:** Chat tab visible in Guest Dossier. Messages render per stay, most-recent stay first.

**Inbox backend — BUILT:** `GET /manager/guest-inbox` returns threads. Used as data source for Phase 1051.

**ProveTest 1048 — DB confirmed:** Message `"PROVE TEST 1048"` written with correct `assigned_om_id`. Commit: `65c45ea`.
