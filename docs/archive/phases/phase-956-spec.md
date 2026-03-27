# Phase 956 — Admin Manage Staff Stat Box Visual Alignment

**Status:** Closed
**Prerequisite:** Phase 955 (Invite Button + Pending Approval Stat Box)
**Date Closed:** 2026-03-27

## Goal

Fix visual rhythm breakage in the Manage Staff stat row caused by long label text wrapping inconsistently. Ensure all number values sit on the same visual baseline regardless of label length.

## Design / Files

| File | Change |
|------|--------|
| `ihouse-ui/app/(app)/admin/staff/page.tsx` | MODIFIED — Renamed label from "Waiting for Approval" to "Pending Approval". Refactored shared `cardStyle` to use flexbox column layout with `justifyContent: 'space-between'` and `minHeight: '94px'`. Removed fixed `marginTop` from all number values. |

## Result

- Label shortened to "Pending Approval" to prevent wrapping.
- Stat box system rebuilt at `cardStyle` level — all boxes (Total, Admin, Manager, Staff Member, Owner, Pending Approval, Legacy) share the same flex structure.
- Number values are anchored to the bottom of each card via flexbox, ensuring visual baseline alignment regardless of label length.
- Deployed to Vercel staging.
