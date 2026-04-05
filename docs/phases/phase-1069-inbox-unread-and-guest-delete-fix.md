# Phase 1069 — Inbox Unread Correction + Guest Message Delete UI

**Status:** Deployed  
**Date:** 2026-04-05  
**Depends on:** Phase 1068 (unread badge infrastructure, backend soft-delete endpoint)

---

## Problem Statement

Phase 1068 shipped the backend infrastructure for both features but two product gaps
remained after manual staging verification:

1. **OM unread state not clearing correctly** — badge and thread-level indicators
   remained after OM opened and read a thread.

2. **Guest message delete not visible in the portal** — the backend `DELETE /guest/{token}/messages/{id}`
   endpoint existed but there was no affordance in the guest portal UI.

---

## Fix 1 — OM Unread/Read Model

### Canonical rule (now implemented and enforced)

| Concept | Rule |
|---|---|
| Where unread is stored | Per **message** — `guest_chat_messages.read_at IS NULL` |
| What "unread count" means | Aggregated per **thread** in the inbox list API response |
| What event marks messages read | Opening the thread drawer → fires `PATCH /manager/guest-messages/{booking_id}/read` |
| Which messages get marked | All `sender_type IN ('guest','system')` messages with `read_at IS NULL` for that booking |
| When the badge clears | Immediately (optimistic local patch) + 1.5s deferred reload from DB |

### Root cause of the bug

The old code in `ThreadDrawer` had:

```typescript
if (conversation.unread_count > 0) {
    apiFetch(...PATCH /read...);
}
```

`conversation.unread_count` is **stale inbox-list data** — it's whatever value was in
the last poll result. In two failure scenarios:

- The 15s auto-poll had just run and locally optimistically set `unread_count = 0`
  (from a previous `handleMarkedRead` call) but the DB still had unread messages →
  the guard blocked the PATCH → messages stayed unread in DB → next poll re-inflated badge.
- The inbox was freshly loaded with the real count, but immediately opening the thread
  caused the guard condition to flip correctly — until the next reload overwrote it.

### Fix

1. **Remove the guard entirely** — `PATCH /read` is now called unconditionally on
   every thread open. It is idempotent: if nothing is unread it writes 0 rows cheaply.

2. **Immediate local `read_at` stamp** — after PATCH /read succeeds, local message
   state is updated to set `read_at = now` on all previously-unread messages, so the
   ✓ Read / ○ Unread per-message indicators flip without waiting for a re-fetch.

3. **Dual-strategy `handleMarkedRead`** — parent now does:
   - Optimistic local `unread_count = 0` → instant badge clear
   - `refreshBadge()` → immediate nav badge sync
   - `setTimeout(() => { load(); refreshBadge(); }, 1500)` → DB-truth sync after
     backend write settles, prevents the 15s auto-poll from clobbering local state

---

## Fix 2 — Guest Message Delete UI

### Canonical behavior (now implemented)

| Aspect | Behavior |
|---|---|
| Delete window | **30 seconds** from `created_at` |
| Delete affordance | `🗑 Xs` countdown button appears below each guest-sent message while window is open |
| Countdown style | Normal (grey border) for 30–11s remaining; urgent (red) for ≤10s remaining |
| On click | Immediately fires `DELETE /guest/{token}/messages/{id}` |
| On success | Optimistic: message bubble replaced with italic "Message deleted" tombstone |
| On window expiry | Button vanishes automatically (no manual poll needed — pure client-side timer) |
| On backend `WINDOW_EXPIRED` | Shows "Too late — window expired." inline next to button |
| Guest sees after delete | Italic tombstone: *"Message deleted"* |
| OM/Admin sees after delete | Italic dashed tombstone: *"🗑 Message deleted by guest"* |
| Audit trail | Row remains in DB with `is_deleted=true`, `deleted_at` — never hard-deleted |

### Implementation

New component `DeleteCountdown` in `guest/[token]/page.tsx`:
- Uses `useEffect` with `setInterval(1s)` to tick down `secondsLeft`
- Calls `DELETE /guest/{token}/messages/{id}` directly (no auth token needed — portal is token-authenticated)
- `onDeleted(id)` callback triggers optimistic local state update in parent `ConversationThread`
- Component unmounts / returns null when `secondsLeft <= 0`

---

## Files Changed

| File | Change |
|---|---|
| `ihouse-ui/app/(app)/manager/inbox/page.tsx` | Removed unread_count guard; added local read_at stamp; dual-strategy handleMarkedRead |
| `ihouse-ui/app/(public)/guest/[token]/page.tsx` | Added `DeleteCountdown` component; updated `ConversationThread` with delete + tombstone |

### Backend — no changes required

Both backend endpoints were already correct from Phase 1068:
- `PATCH /manager/guest-messages/{booking_id}/read` — idempotent, marks all unread rows
- `DELETE /guest/{token}/messages/{message_id}` — enforces 30s WINDOW_SECONDS, returns `WINDOW_EXPIRED`

---

## Staging Verification Steps

### Fix 1 — Unread clearing

1. Log in as Operational Manager (Nano G) on staging
2. Confirm the nav badge shows unread count (e.g. `3`)
3. Click Inbox → see threads with left-border highlight and unread dot
4. Click one unread thread to open the drawer
5. **Expected within ~2 seconds:**
   - Per-message ✓ Read indicators appear on guest messages
   - Thread row loses unread dot and left-border highlight immediately
   - Nav badge count decrements immediately
6. Close drawer — badge should still reflect the updated count
7. Wait for the 15s auto-poll to re-fetch — badge should remain correct (not re-inflate)

### Fix 2 — Guest delete

1. Open any real guest portal link (e.g. Amuna Villa)
2. Scroll to "Need Help?" section, type a message, send
3. Message appears in thread immediately
4. **Expected:** `🗑 30s` button appears below the bubble, counting down
5. At ≤10s: button border turns red, text turns red
6. At 0s: button vanishes completely
7. **Test delete:** within 30s, click the `🗑 Xs` button
8. **Expected:** bubble replaced with italic *"Message deleted"*
9. In OM Inbox, open that guest's thread → bubble shows *"🗑 Message deleted by guest"*

---

## Invariants

- Unread is tracked **per message** in DB (`read_at`)
- Shown **per thread** as an aggregate count in inbox list
- Delete window is **strictly 30 seconds** — enforced both in frontend timer (no button after 30s) and backend check (WINDOW_EXPIRED)
- Soft-delete only: `is_deleted=true` + `deleted_at` — DB row never removed
- OM always sees tombstone for deleted messages — never sees a blank gap
