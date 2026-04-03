# Phase Closure — 1047 Series (Guest Portal Hardening)

> Closed: 2026-04-03  
> Session: 33412724-4b6d-47bf-824d-1633a177c0b0  
> Branch: `checkpoint/supabase-single-write-20260305-1747`  
> Last commit: `361371f`

---

## Phase 1047A — Guest Portal Foundation Repair

**Status: CLOSED**

Fixed 5 functional regressions in the guest portal `/guest/[token]` page.
- Cover photo SELECT gap on backend
- House info JSON unwrap (was rendering `[object Object]`)
- Status chip hardcoded to "CONFIRMED"
- Guest message POST key mismatch (`message` → `content`)
- Generate QR button disconnected from real endpoint

Commits: `940fecd` → `1ec8122`.

---

## Phase 1047A-name — Guest Portal No-Leak + Schema Alignment

**Status: EFFECTIVELY CLOSED**

Product rule locked: **no internal identifier may appear on any guest-facing surface.**

Root cause: backend was querying 6 non-existent property columns causing silent nulls,
which fell through to internal codes (`KPG-500`, etc.) as visible fallback values.

Fixes:
- `name` → `display_name`
- `check_in_time` → `checkin_time`
- `check_out_time` → `checkout_time`
- `welcome_message` → `description`
- `checkout_notes` → `extra_notes`
- `manager_*` → `owner_phone` / `owner_email`
- OTA placeholder guest names sanitized

**PROVEN:** Real property name ("Emuna Villa TEST") confirmed visible on staging.
**OPEN (not blocking):** WhatsApp contact proof; untested portal variants.

Commit: `54ef82c`.

---

## Phase 1047B — Guest Portal Host Identity Block

**Status: PROVEN (manual — full path confirmed 2026-04-03)**

### What was built

3 new `portal_host_*` columns added to `properties` table (Supabase migration applied):
- `portal_host_name TEXT`
- `portal_host_photo_url TEXT`
- `portal_host_intro TEXT`

Backend portal response extended to include these fields.

Admin "GUEST PORTAL — HOST IDENTITY" section added to Property Settings → General tab.
Framing is explicit: _guest-facing display content only — not routing truth, not system identity._

Guest portal `PortalHostBlock` component:
- Invisible when `portal_host_name` is null
- Compact layout without intro when intro is null
- Initials fallback when no photo

Placement: below hero, above Home Essentials. Confirmed correct.

### Persistence fix (critical bug resolved)

`portal_host_*` fields were missing from `_PROPERTY_DETAIL_FIELDS` whitelist in
`properties_router.py` and from `_format_property()`. Fields were accepted in PATCH but
never returned, causing the UI to always snap back to empty on reload.

**Fix:** Added all three fields to whitelist and return map.

### Invariant locked

> `portal_host_*` is guest-facing presentation data only.
> It is NOT routing truth. It is NOT owner truth. It is NOT audit truth.
> Never use `portal_host_*` to determine who receives a message or who is responsible for a property.

### Proof status

| Item | Label |
|------|-------|
| Admin section visible | PROVEN |
| `portal_host_name` set → block visible | PROVEN |
| `portal_host_name` null → block absent | PROVEN |
| Block placement (below hero, above Home Essentials) | PROVEN |
| Persistence after Save + reload | PROVEN |

Commits: `215e9f8`, `8994396`.

---

## Phase 1047C — Messaging Honesty + Schema Repair

**Status: PROVEN (manual — send confirmed working 2026-04-03)**

### What was broken

The `guest_send_message` backend handler had 3 schema mismatches against `guest_chat_messages`:

| Wrong | Correct |
|-------|---------|
| `booking_ref` column | `booking_id` |
| `content` column | `message` |
| `property_id` missing (NOT NULL) | must be included |
| `tenant_id` conditional | must always be set |

Every guest send attempt was returning 500 at the database insert level.

### What was fixed

- All 4 column names corrected in the insert row
- Early-exit guard added: if token context returns empty `booking_ref` or `property_id`,
  returns `500 CONTEXT_ERROR` with a clean log rather than a cryptic DB violation
- `created_at` removed (DB default handles it)

### Copy change (Phase 1047C product honesty)

Guest-facing messaging copy updated per the "no false promise" rule:
- No language that implies a live human will respond
- "Leave us a note" framing (not "chat", "message", "live support")

### Proof status

| Item | Label |
|------|-------|
| Guest send → success banner | PROVEN |
| Row written to `guest_chat_messages` (sender_type='guest') | PROVEN (DB confirmed 3 rows) |
| No false response promise in guest copy | PROVEN |

Commits: `88e5fd9`.

---

## Phase 1047E — Host Photo Upload

**Status: BUILT + SURFACED (manual proof confirmed flow works, no DB verification of specific uploads)**

### What was built

Admin Host Identity section now has a real file upload flow:

**Empty state:** dashed-ring placeholder (👤), "📷 Upload Photo" button, file type hint.

**Selected state:** "asset card" — 72px round avatar preview, "PHOTO SET" purple badge,
truncated URL, "↺ Change" and "Remove" controls.

**URL fallback:** collapsed under a `<details>` disclosure for advanced use. Not in primary flow.

### Implementation

Reuses existing `uploadPropertyPhoto()` utility (`ihouse-ui/lib/uploadPhoto.ts`) and
existing `POST /properties/{id}/upload-photo` backend proxy. No new backend required.
Uploaded CDN URL is stored in `editPortalHostPhotoUrl` state and written to DB via
`portal_host_photo_url` on Save.

Photo is rendered in the guest portal host block when present (real photo > initials).

### Proof status

| Item | Label |
|------|-------|
| Upload button visible in empty state | PROVEN |
| Upload → preview renders in admin | PROVEN |
| "↺ Change" and "Remove" controls work | SURFACED (visual confirmed, end-to-end not deep-verified) |
| Uploaded photo renders in guest portal | OPEN — requires a test with a valid guest portal URL after save |

Commits: `88e5fd9`, `361371f`.

---

## Phase 1047-polish — Note Area Persistence + Photo Asset Card

**Status: BUILT + SURFACED (manual proof accepted)**

### Fix 1 — Host Photo Asset Card UI

Before: preview was a small 56px circle buried next to a visible URL input field.
After: two distinct states:
- Empty → dashed-ring CTA, single "📷 Upload Photo" button
- Set → prominent card (72px avatar + badge + Change/Remove)
URL input hidden under disclosure, not in primary visual path.

### Fix 2 — Guest Note Area Persistent

Before: after sending, the entire note area was replaced by the success message.
Guest could not send a second note without reloading.

After:
- Success banner ("✅ We got your note — thank you.") appears above the textarea
- Banner auto-clears after 4 seconds
- Textarea clears on success but remains visible and active
- Guest can send multiple notes in the same session

No changes to backend. Frontend-only.

### Proof status

| Item | Label |
|------|-------|
| Note area stays open after send | PROVEN |
| Success banner visible then auto-clears | SURFACED (manual accepted) |
| Guest can send second note | SURFACED (manual accepted) |
| Photo empty → filled states look correct | PROVEN |

Commits: `361371f`.

---

## Open Items Carried Forward

| Item | Label | Notes |
|------|-------|-------|
| Uploaded host photo renders in guest portal (end-to-end) | OPEN | Needs: save photo → visit that property's guest portal URL |
| WhatsApp contact proof (pre-fill functional) | OPEN | Not blocking |
| Guest portal untested variants (multiple properties) | OPEN | Not blocking |

---

## What This Session Closed

All guest-facing content in the portal is now:
1. Using real property data (no internal code leakage)
2. Showing real host identity when set (presentation only)
3. Accepting and storing guest notes correctly in the DB
4. Open to multiple messages per session (not a one-shot form)
5. Supporting real photo uploads for host avatar

Next workstream: Guest Chat Model (Phases 1048–1055+).
