# Phase 1038b — Mobile Stream Responsive Hardening + Multi-Supervisor Chips

**Status:** Closed
**Prerequisite:** Phase 1038 (Supervisory Role Assignment Hardening)
**Date Closed:** 2026-04-02

## Goal

Two focused fixes: (1) Mobile portrait OM Stream Bookings tab was breaking layout — wide table columns overflowed and the tab reset to Tasks on device orientation change. (2) Property rows for supervisory roles needed to show ALL assigned supervisors for a villa, not just the current user, so the operator can understand the full supervision picture (multi-OM per villa).

## Invariant (INV-1038b-A)

- Stream active tab is persisted to `sessionStorage` and restored on mount — survives orientation change and resize.
- Mobile portrait (<640px): Bookings rows render as vertical card layout (3 rows: property+status / guest+dates / ref+hint). Desktop: unchanged table row layout.
- Supervisor chip strip: shows ALL supervisors assigned to property. First 2 as chips; 3+ shows `+N` overflow chip (hover = full list). Current user's own chip highlighted in purple. Others in amber. `No supervisor yet` only when allSupervisors.length === 0 AND user not assigned.

## Design / Files

| File | Change |
|------|--------|
| `ihouse-ui/app/(app)/manager/stream/page.tsx` | MODIFIED — `useIsMobile` hook (viewport < 640px); `activeTab` persisted to sessionStorage; `switchTab()` replaces `setActiveTab()` everywhere; `BookingRow` isMobile prop gates layout branch (mobile card vs desktop table row); urgency bar shows on mobile as `borderLeft`, on desktop as `urgencyBar` div |
| `ihouse-ui/app/(app)/admin/staff/[userId]/page.tsx` | MODIFIED — Supervisory chip strip: show ALL supervisors for property (not filtered to current user); first 2 chips + overflow `+N`; current user highlighted purple; others amber; `No supervisor yet` only when truly empty |

## Result

Mobile portrait Bookings tab: readable card layout. Orientation change: tab state preserved. Supervisory chip strip: shows complete multi-supervisor picture per villa. Build clean. Deployed commit `eae8705`.

## Open (carries into Phase 1039)

- OM inline help / product-truth explanatory text on Role & Assignment screen — not yet implemented.
- UI proof screenshot for 1035–1038b pending (requires Vercel staging session).
