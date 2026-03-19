# Phase 845 — Worker App UI Overhaul & Brand Alignment

**Status:** Closed
**Prerequisite:** Phase 844
**Date Closed:** 2026-03-19

## Goal

Apply the Domaniqo Brand (Midnight Graphite, Deep Moss, Cloud White, etc.) to the worker application. Create a dedicated mobile-first desktop shell for the worker app to emulate a mobile interface while on desktop browsers. Reorganized bottom tabs into Home, Tasks, Done, and Profile.

## Invariant (if applicable)

The worker interface (`/worker` and `/ops/*`) must always use a consistent `max-width: 480px` constraint (mobile enclosure) even on desktop to normalize the field-worker experience. Typography must follow Manrope for headers, Inter for standard text.

## Design / Files

| File | Change |
|------|--------|
| `ihouse-ui/app/(app)/worker/page.tsx` | MODIFIED — refactored components into Dashboard, Task List, DetailSheet, BottomNav. Replaced Tailwind CSS with CSS custom properties representing the brand |
| `ihouse-ui/components/AdaptiveShell.tsx` | MODIFIED — added logic to extract worker paths (`/worker`, `/ops/`) into the mobile envelope |

## Result

**N tests pass, M skipped.**
UI successfully reflects the specified premium Domaniqo aesthetics.
