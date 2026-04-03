# Phase 1053 — Guest Portal Thread View

**Status:** BUILT + SURFACED (deployed to Vercel — 2026-04-03; manual proof pending)
**Prerequisite:** Phase 1052 (Host Reply Path proven)
**Date Closed:** 2026-04-03
**Branch:** `checkpoint/supabase-single-write-20260305-1747`
**Commits:** `c2d2f55`

## Goal

Surface the full conversation thread (both guest messages and host replies) inside the guest portal,
above the existing note form. Guest must be able to read the history of their own messages
and host replies for the current stay. No cross-stay leakage. No AI responses. No typing indicators.
Host replies shown verbatim, labeled with `portal_host_name` or "Your Host" — never internal identity.

## Invariant

- **Thread is scoped strictly to the portal token's `booking_id`** — one stay, no previous-stay leakage.
- **`portal_host_name` is display-only** — not routing truth, not audit truth, not sender identity.
- **`sender_id` is never returned to the guest** — internal staff identity stays backend-only.
- **30-second poll** — sufficient for this phase. No WebSocket overbuild.

## Design / Files

| File | Change |
|------|--------|
| `src/api/guest_portal_router.py` | MODIFIED — `GET /{token}/messages`: fixed root bug (`.eq("booking_ref")` → `.eq("booking_id")`), returns only safe fields, resolves `portal_host_name` from `properties` for labeling |
| `ihouse-ui/app/(public)/guest/[token]/page.tsx` | MODIFIED — New `ConversationThread` component: polls 30s, renders guest/host bubbles; guest=right+blue, host=left+subtle. Mounted inside `NeedHelp` card above note form. `useCallback` import added. |

## Bug Fixed

`GET /{token}/messages` had used `.eq("booking_ref", ...)` since Phase 670. `booking_ref` is not a column in `guest_chat_messages` — the correct column is `booking_id`. This caused 0 rows returned on every call since the endpoint's creation. Fixed in this phase.

## Phase 1052 Identity Rule — Docstring Captured

The `GET /{token}/messages` docstring now explicitly documents:
> `sender_id = user_id (NOT tenant_id). This field is not returned to guest; it is internal routing truth only.`

This replaces any previous doc language that may have implied `sender_id = tenant_id`.

## Result

**BUILT + DEPLOYED — 2026-04-03. Manual proof pending.**
- Vercel deployed at commit `c2d2f55`
- Railway backend auto-deploying
- Expected: guest messages + host reply visible in portal "Need Help?" section
- Thread renders null cleanly when no messages exist
- Note form remains open and usable below thread at all times
