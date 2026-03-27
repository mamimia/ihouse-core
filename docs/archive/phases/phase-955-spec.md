# Phase 955 — Admin Manage Staff: Invite Button + Pending Approval Stat Box

**Status:** Closed
**Prerequisite:** Phase 954 (Intake Queue Count Fix)
**Date Closed:** 2026-03-27

## Goal

Surface the pending staff onboarding approval state as a first-class summary box on the Admin Manage Staff page, and rename the top-right "Pending Requests" button to a clearer invitation-oriented label.

## Design / Files

| File | Change |
|------|--------|
| `ihouse-ui/app/(app)/admin/staff/page.tsx` | MODIFIED — Renamed "Pending Requests" button to "Invite Staff". Added `pendingCount` state + concurrent `apiFetch('/admin/staff-onboarding')` call. Added "Waiting for Approval" StatCard to stat row with click-to-navigate to `/admin/staff/requests`. |

## Result

- "Pending Requests" button relabeled to "Invite Staff" across the admin staff page.
- New "Waiting for Approval" summary box added to the stat row, wired to the real count from the `/admin/staff-onboarding` endpoint (same data source as the requests page list).
- Clicking the box routes to `/admin/staff/requests`.
- Deployed to Vercel staging.
