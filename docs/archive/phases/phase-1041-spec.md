# Phase 1041 — P1: OM Hub Refinement

**Status:** CLOSED
**Prerequisite:** Phase 1040
**Date closed:** 2026-04-02
**Branch:** `checkpoint/supabase-single-write-20260305-1747`

---

## Intent

Targeted Hub quality pass. No structural rebuild. Fixes the 5 concrete gaps between the Hub as designed (Phase 1037 Part A spec) and the Hub as built.

This phase does NOT redesign the Hub layout, does NOT add new backend endpoints, and does NOT touch the Stream.

---

## Scope — 5 targeted fixes

### Fix 1 — Morning Briefing auto-loads on mount
**Problem:** `MorningBriefingWidget` renders with an empty state and a "Generate Briefing" button. The manager must click it every session. This is friction — the Hub is supposed to answer "what needs attention right now?" instantly.

**Fix:** Trigger `doFetch()` in a `useEffect` on mount. Remove the "Generate Briefing" label from the button; rename to "Refresh Briefing" when data is present. The briefing is now available immediately on Hub load.

**Kept:** language selector, Refresh button, generated-by badge, action items list, ops metric chips.

---

### Fix 2 — AlertRail rendered in Hub
**Problem:** `AlertRail` is fully implemented (Phase 1033) but not mounted in `ManagerPage`. The Hub page fetches alerts in `OpsStrip` (for the alert count chip) but silently discards the full alert list.

**Fix:** Mount `AlertRail` between OpsStrip and PriorityTaskSnapshot. Share the alert fetch — `ManagerPage` fetches once via a new `useAlerts()` hook, passes `alerts` and `loading` to both `AlertRail` and `OpsStrip`.

**Position:** follows the locked Hub layout order from Phase 1037 spec:
`Header → (Morning Briefing) → OpsStrip → Alert Rail → Priority Tasks → Today's Bookings → (Audit Lookup)`

---

### Fix 3 — Soft refresh (no full page reload)
**Problem:** Hub Refresh button calls `window.location.reload()`. This is a hard page reload, resets all component state, creates a flicker, and is inconsistent with the app's SPA behavior.

**Fix:** Use a `refreshKey` counter state in `ManagerPage`. Increment on Refresh. All data-fetching child components receive `refreshKey` as a `key` prop (or `dep` in their `useEffect`) — this forces remount + refetch without a full page reload.

**Morning Briefing:** Refresh increments `briefingKey` which remounts `MorningBriefingWidget` (triggering its mount-auto-fetch).

---

### Fix 4 — Footer phase label
**Problem:** Footer reads "Phase 1037" — stale since Hub was built across multiple phases.

**Fix:** Update to "Phase 1041".

---

### Fix 5 — Alert overflow text
**Problem:** AlertRail shows "+N more — Alerts page coming in Step 3" — internal planning note leaked into production UI.

**Fix:** Change to "+N more — view Alerts page" (or simply suppress the overflow label since Alerts already has its own nav entry).

---

## What this phase does NOT do

- Does not change backend endpoints
- Does not change Stream (`/manager/stream`)
- Does not rebuild Hub layout
- Does not implement the Booking Runway backend fix from Phase 1037 Part A (deferred)
- Does not remove `BookingAuditLookup` (already demoted to `<details>` collapse)
- Does not add new manager actions or intervention flows

---

## Files changed

| File | Change |
|------|--------|
| `ihouse-ui/app/(app)/manager/page.tsx` | Fix 1 (briefing auto-load), Fix 2 (AlertRail mount + shared fetch), Fix 3 (soft refresh), Fix 4 (footer), Fix 5 (alert overflow text) |

---

## Closure Conditions

- [x] Morning Briefing auto-loads on Hub mount — no manual click required
- [x] AlertRail renders between OpsStrip and PriorityTaskSnapshot
- [x] Alerts fetched once, shared — no double fetch
- [x] Hub Refresh does not trigger `window.location.reload()`
- [x] Footer updated to Phase 1041
- [x] Alert overflow text cleaned (no planning-note leakage)
- [x] TypeScript 0 errors
- [x] Staging deployed + verified

**Status: CLOSED.**
