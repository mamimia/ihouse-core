# Phase 1052 — Host Reply Path

**Status:** PROVEN (manually confirmed on live staging — 2026-04-03)
**Prerequisite:** Phase 1051 (Inbox UI surfaced)
**Date Closed:** 2026-04-03
**Branch:** `checkpoint/supabase-single-write-20260305-1747`
**Commits:** `65c45ea` (initial reply endpoint), `e24bfe2` (scope guard bug fix)

## Goal

Enable a staff/OM user to send a real text reply to a guest from inside the inbox drawer.
The reply must be persisted in `guest_chat_messages` with the correct identity attributes.

## Invariant (LOCKED)

**`sender_id = caller's user_id` — NEVER `tenant_id`.**

`tenant_id` is shared across all staff for a property group. It is not a personal identity.
`sender_id` must always be the specific staff member's `user_id` (from the verified JWT).
This rule applies to all host-side writes to `guest_chat_messages`.

## Design / Files

| File | Change |
|------|--------|
| `src/api/guest_inbox_router.py` | NEW endpoint `POST /manager/guest-messages/{booking_id}/reply` — identity rule enforced: `sender_id = caller user_id`, `sender_type = 'host'` |
| `src/api/guest_inbox_router.py` | BUG FIX (`e24bfe2`): scope guard was using `.limit(1)` without ordering, fetching pre-1048 rows with `assigned_om_id=null`, returning 403 NOT_ASSIGNED. Fixed: fetch all rows, check ANY row for ownership. |
| `ihouse-ui/app/(app)/manager/inbox/page.tsx` | MODIFIED — `ThreadDrawer`: real reply textarea + send button. Optimistic UI, Cmd+Enter submit, inbox row sync on reply. |

## Bug Root Cause (Fixed)

The `.limit(1)` query on the reply endpoint fetched a random row — often a pre-Phase-1048 message with `assigned_om_id = null`. This caused the ownership check to fail (null ≠ caller user_id), returning 403 for all legitimate replies. DB evidence: 3 of 5 rows in the test thread had `assigned_om_id = null`.

## Result

**PROVEN — manually confirmed 2026-04-03:**
- Reply sends successfully from `/manager/inbox`
- New row in `guest_chat_messages` with:
  - `sender_type = 'host'`
  - `sender_id = 10de26bb-0746-412a-8c62-cecb5c405b4f` (Nana G's user_id — NOT tenant_id)
  - correct `booking_id = ICAL-36ff7d9905e0`
  - correct `property_id = KPG-500`
- Reply appears immediately in inbox drawer
- Same reply appears in Guest Dossier Chat tab for that stay
