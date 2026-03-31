# Phase 1028 — Primary/Backup Model Decision & Baton-Transfer Architecture

**Status:** Closed
**Prerequisite:** Phase 1027 — Stale Task & Past-Task Hygiene
**Date Closed:** 2026-03-30

## Goal

Decided on and locked the Primary/Backup worker assignment model for property-lane assignments. Replaced the previous "first DB row wins" non-deterministic behavior with an explicit priority-ranked model. Designed the full baton-transfer architecture including lane-awareness, PENDING task movement rules, ACKNOWLEDGED task protection, and admin confirmation modal requirement.

## Invariant

- **INV-1010:** Primary/Backup is per property + work lane (Cleaning, Check-in & Check-out combined, Maintenance)
- Priority 1 = Primary. Priority 2 = Backup 1. Priority N = Backup N-1.
- Check-in and Check-out remain combined in one lane — not two independent lanes
- Baton-transfer: PENDING tasks may move to new Primary. ACKNOWLEDGED and IN_PROGRESS tasks must NOT move
- Assignment must not be silent — admin must see confirmation modal on baton-transfer

## Design / Files

| File | Change |
|------|--------|
| DB migration | NEW — `priority` INTEGER column on `staff_property_assignments` |
| `src/api/permissions_router.py` | MODIFIED — baton-transfer logic with lane-aware backup candidate filtering |
| `ihouse-ui/app/(app)/admin/staff/` | MODIFIED — Primary/Backup UI labels; assignment UI shows lane role |

## Result

Primary/Backup model locked. `priority` column added to DB and populated for existing staging workers. Lane-aware logic in baton-transfer code path. Admin UI shows Primary/Backup labels per assignment.
