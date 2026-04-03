> ⚠️ FIRST: Read `docs/core/BOOT.md` before doing anything else.

# Handoff — Phase 1053 Closure
**Date:** 2026-04-03  
**Branch:** `checkpoint/supabase-single-write-20260305-1747`  
**Frontend:** `https://domaniqo-staging.vercel.app`  
**Backend:** `https://ihouse-core-production.up.railway.app`

---

## What Was Completed in This Chat

### Phase 1048 — Guest Chat Model (SURFACED)
- `resolve_conversation_owner()` in `src/services/guest_messaging.py` — stamps `assigned_om_id` at message insert
- Guest Dossier Chat tab surfaced — per-stay thread history in `ihouse-ui/app/(app)/guests/[id]/page.tsx`
- Inbox backend `GET /manager/guest-inbox` built in `src/api/guest_inbox_router.py`
- ProveTest 1048 DB-confirmed: `assigned_om_id = 10de26bb-...` (Nana G's user_id)

### Phase 1049B — Guests List In-Stay Indicator (SURFACED)
- In-stay guests sorted to top of Guests list
- Soft-pulse green secondary line "In Stay — [Property Name]" under guest name (~2s fade cycle)
- No badge/chip; only the secondary text line pulses

### Phase 1050 — Guest Dossier Chat Tab (SURFACED)
- Dedicated Chat tab inside Guest Dossier
- Per-stay message threads, chronological order, most-recent stay first

### Phase 1051 — Operational Guest Inbox UI (SURFACED)
- `/manager/inbox` route
- `💬 Inbox` added to OMSidebar (desktop) and OMBottomNav (mobile)
- Thread list + `ThreadDrawer` (full message history on click)
- Confirmed reachable from live manager surface

### Phase 1052 — Host Reply Path (PROVEN ✅)
- `POST /manager/guest-messages/{booking_id}/reply` endpoint in `src/api/guest_inbox_router.py`
- Reply textarea + send button in `ThreadDrawer`
- **Root bug found and fixed:** scope guard was using `.limit(1)` without ordering, hitting pre-1048 rows with `assigned_om_id=null` → returning 403 NOT_ASSIGNED
- Fix: fetch all rows ordered newest-first, check ANY row for ownership, resolve context from most recent non-null row
- DB proof: `sender_type='host'`, `sender_id = 10de26bb-0746-412a-8c62-cecb5c405b4f` (Nana G's user_id)
- Reply visible in inbox drawer + Guest Dossier Chat tab

### Phase 1053 — Guest Portal Thread View (BUILT + SURFACED — proof pending)
- `ConversationThread` component in guest portal "Need Help?" section, above note form
- **Root bug fixed:** `GET /{token}/messages` was using `.eq("booking_ref")` since Phase 670 — wrong column. Always returned 0 rows. Fixed to `.eq("booking_id")`.
- Host messages labeled `portal_host_name` or "Your Host" — never internal identity
- 30s poll + immediate re-fetch after guest sends a note
- Null path: renders nothing cleanly when no messages yet
- Note form remains open below thread at all times
- **Manual proof pending** — deployed to Vercel + Railway

---

## Proven vs Only Built — Honest Labels

| Phase | Label | Basis |
|-------|-------|-------|
| 1048 | SURFACED | DB row confirmed; UI visible on staging |
| 1049B | SURFACED | Manually seen in live Guests list |
| 1050 | SURFACED | Chat tab visible in Guest Dossier |
| 1051 | SURFACED | Inbox visible in manager shell |
| 1052 | **PROVEN** | DB row confirmed (sender_type, sender_id). Reply visible in drawer + Dossier |
| 1053 | BUILT + SURFACED | Deployed. Manual portal proof **not yet performed in this chat** |

---

## What Remains Open

1. **Phase 1053 manual proof** — visit the guest portal link, check "Need Help?" section, confirm thread visible with all messages + host reply labeled "Your Host" or portal_host_name.
2. **`assigned_om_id` long-term ownership model** — current scaffold (based on `staff_property_assignments` priority order) is not the final design. The broader ownership model is deferred; the current scaffold is sufficient for single-property operation.
3. **Uploaded host photo renders in guest portal** — `portal_host_photo_url` admin upload tested; portal render not end-to-end proven.
4. **WhatsApp contact proof** — not blocking.
5. **Portal multi-property variant testing** — not blocking.

---

## Next Recommended Phase

> **1054 — Guest Messaging Stream Hardening**

Options for what this could include (for the next chat to decide with user):
- **Unread badge** on inbox nav icon (count of threads with unread messages)
- **Mark-as-read** on thread open (PATCH endpoint + UI)
- **Real-time / SSE** upgrade for inbox instead of manual polling (if the OM needs live updates)
- **Reassignment** — allow OM to reassign a thread to another staff member (changes `assigned_om_id`)
- **Guest typing state / UI polish** — out of scope until above are done

The single clearest next build is **unread count / mark-as-read** — it makes the inbox operationally complete for day-to-day use.

---

## Architectural Guardrails — Must Preserve

### Identity (LOCKED — DO NOT CHANGE)
- `sender_id = caller's user_id` — ALWAYS. Never `tenant_id`.
- `sender_type = 'host'` for all staff replies.
- `tenant_id` is isolation scope only — never sender identity.

### Conversation Scope (LOCKED)
- One thread per `booking_id` (per stay).
- No guest-lifetime threading across stays.
- Portal token is scoped to one `booking_id` — server enforces this on all endpoints.

### Display Layer (LOCKED)
- `portal_host_name`, `portal_host_photo_url`, `portal_host_intro` are **presentation only**.
- They are NOT routing truth, owner truth, or audit truth.
- The guest portal must NEVER expose `sender_id`, `assigned_om_id`, `tenant_id` to guests.

### Routing Scaffold (NOT YET FINAL)
- `assigned_om_id` is the current routing stamp — it identifies which OM "owns" a thread.
- This is not the final long-term ownership model. The model will be extended (multi-OM coverage, escalation, etc.).
- Do not treat `assigned_om_id` as permanent or rename it; do not build ownership-critical features on it alone.

### Guest Dossier Chat (CANONICAL)
- The Guest Dossier Chat tab is the canonical per-stay history surface for staff.
- The Inbox is the operational surface for active/unread threads.
- These are two views of the same data (`guest_chat_messages`), not separate systems.

---

## Key Files

| File | Role |
|------|------|
| `src/api/guest_inbox_router.py` | Inbox query + reply endpoint |
| `src/api/guest_portal_router.py` | Guest-facing GET/POST messages (token-authenticated) |
| `src/services/guest_messaging.py` | `resolve_conversation_owner()` |
| `ihouse-ui/app/(app)/manager/inbox/page.tsx` | Inbox UI + ThreadDrawer + reply input |
| `ihouse-ui/app/(app)/guests/[id]/page.tsx` | Guest Dossier with Chat tab |
| `ihouse-ui/app/(public)/guest/[token]/page.tsx` | Guest portal with ConversationThread |
| `ihouse-ui/app/(app)/guests/page.tsx` | Guests list with in-stay indicator |

---

## Deployment State at Handoff

| Surface | Last Deployed Commit | Status |
|---------|---------------------|--------|
| GitHub | `c2d2f55` | ✅ Pushed |
| Railway (backend) | `c2d2f55` | Auto-deploying (allow ~90s) |
| Vercel (frontend) | `c2d2f55` | ✅ Deployed manually |

---

## Test / Validation Status

pytest is not installed in the current local environment (commented out in requirements.txt). The following staging-native validation was performed:

| Check | Method | Result |
|-------|--------|--------|
| 1048 routing: `assigned_om_id` correct | Supabase SQL — `SELECT assigned_om_id FROM guest_chat_messages WHERE booking_id = 'ICAL-36ff7d9905e0'` | ✅ PASS |
| 1052 reply: DB row with correct sender_type + sender_id | Supabase SQL | ✅ PASS |
| 1052 scope guard: 403 on pre-1048 rows | Code review + DB evidence (3 null rows confirmed) | ✅ BUG FOUND + FIXED |
| 1053 portal thread bug: zero rows from GET /messages | Code review — `.eq("booking_ref")` → `.eq("booking_id")` | ✅ BUG FOUND + FIXED |
| Frontend TypeScript compile | `npm run build` in `ihouse-ui/` | ✅ 0 errors, clean exit |
| 1053 portal thread render | Manual guest portal visit | ⬛ PENDING |

**Pre-existing test failures (not introduced in this chat):**
The system at Phase 1040 documented 18 pre-existing test failures in `test_wave7_manual_booking_takeover.py`, `test_guest_owner_auth.py`, `test_task_system_e2e.py`, `test_task_writer_contract.py`. These are mock/stub mismatches, not regressions from this chat's work.

No unit tests exist for `guest_inbox_router.py` or `guest_portal_router.py` GET messages — this is a test gap (pre-existing) that should be addressed in a future hardening phase.
