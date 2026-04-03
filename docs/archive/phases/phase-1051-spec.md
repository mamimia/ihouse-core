# Phase 1051 — Operational Guest Inbox UI

**Status:** SURFACED (manually confirmed on live staging)
**Prerequisite:** Phase 1048 (Inbox backend)
**Date Closed:** 2026-04-03
**Branch:** `checkpoint/supabase-single-write-20260305-1747`
**Commits:** `ed2bee1` (inbox page), `f17ddd2` (nav fix)

## Goal

Surface a real, accessible Operational Manager inbox inside the manager shell. The OM must be able to:
- See which guests have sent messages
- See which property and stay the thread belongs to
- See the latest message preview and unread state
- Click a thread to open a drawer showing the full history
- Reach the inbox easily from the existing manager navigation

## Design / Files

| File | Change |
|------|--------|
| `ihouse-ui/app/(app)/manager/inbox/page.tsx` | NEW — Full inbox page: thread list + `ThreadDrawer` component with full message history. Fetches `GET /manager/guest-inbox`. |
| `ihouse-ui/app/(app)/manager/page.tsx` (OMSidebar) | MODIFIED — Added `💬 Inbox` link to primary sidebar navigation |
| `ihouse-ui/app/(app)/manager/page.tsx` (OMBottomNav) | MODIFIED — Added `💬 Inbox` to mobile bottom nav |

## Result

**SURFACED — manually confirmed:**
- `/manager/inbox` accessible via `💬 Inbox` in sidebar and mobile bottom nav
- Live thread list shows guest conversation from KPG-500
- Threading drawer opens on row click, shows full message history
- Route is a first-class operational tool, not a hidden developer URL

**Not yet at this phase:** reply sending (Phase 1052).
