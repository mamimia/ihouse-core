# Phase 1039 — OM Role & Assignment Inline Help

**Status:** CLOSED
**Prerequisite:** Phase 1038b (Mobile Stream Responsive Hardening + Multi-Supervisor Chips)
**Date closed:** 2026-04-02
**Commit:** `cb51bf8` (UI code) · `cab19ea` (spec doc)
**Branch:** `checkpoint/supabase-single-write-20260305-1747`

## Goal

Surface the Operational Manager product model directly in the UI so an operator can understand the OM supervisory scope model without reading internal docs, investigations, or phase specs.

The operator must be able to answer the following questions from the UI alone:
- What does Operational Manager actually mean? (supervisory scope, not worker lane)
- Can one OM manage multiple villas? (yes)
- Can multiple OMs be assigned to the same villa? (yes)
- Does Primary / Backup apply to OM? (no)
- What are the name chips on each property row showing? (existing supervisors for that villa)
- What does checking the box next to a villa do? (grants managerial scope, not task ownership)

## Scope

UI only. No backend changes. No new endpoints. No schema changes.

## Design / Files

| File | Change |
|------|--------|
| `ihouse-ui/app/(app)/admin/staff/[userId]/page.tsx` | NEW: OM info block — renders when `role === 'manager'` on Role & Assignment tab. Contains 5 bullet explanations of the supervisory model. Positioned after role collapsed/edit selector, before Linked Owner Profile section. |
| `ihouse-ui/app/(app)/admin/staff/[userId]/page.tsx` | NEW: Supervisory context note — renders when `role === 'manager'` or `role === 'admin'`, placed between Assigned Properties section header and the Primary/Backup help button. One sentence explaining supervisory assignment semantics. |

## What it does NOT do

- Does not change the worker row Primary/Backup model.
- Does not add any new endpoint or API call.
- Does not change property assignment save logic.
- Does not add a modal, drawer, or overlay — inline text and styled block only.

## Closure Conditions

- [x] UI screenshot: OM info block visible on Role & Assignment tab for a manager user — ✅ proven on staging (Nana G, Operational Manager)
- [x] UI screenshot: Supervisory context note visible above Assigned Properties list — ✅ proven on staging (desktop view)
- [x] Both visible on desktop — ✅ desktop screenshot captured
- [x] Mobile view: OM info block visible and readable — ✅ mobile screenshot captured (single-column, no overflow)
- [x] TypeScript: 0 errors — ✅ verified before deploy
- [x] Deployed to staging: ✅ `https://domaniqo-staging.vercel.app`

## Staging Proof

Captured 2026-04-02. Staff member: Nana G (role: Operational Manager).

**Desktop:** OM info block lower bullets ("🚫 Primary / Backup does not apply to OM", "👤 The name chips on each villa row...") + supervisory context note ("Supervisory assignment: Checking a villa grants...") + property rows with `👤 Nana G` and `👤 03304` chips on assigned villas; `No supervisor yet` on unassigned.

**Mobile:** Role summary card shows "Operational Manager" + Edit. OM info block header "🏢 Operational Manager — Supervisory Scope Role" + first three bullets fully readable in single-column layout.

## Status

**CLOSED.** Built, deployed, staging proof captured (desktop + mobile).

