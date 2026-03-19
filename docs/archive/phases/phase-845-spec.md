# Phase 847 — Worker App Functionality Polish 

**Status:** Closed
**Prerequisite:** Phase 846
**Date Closed:** 2026-03-19

## Goal

Provide highly functional, actionable task cards. This includes adding a direct Waze Navigation button bound to the property address string, fixing translation lookup keys for lowercasing the task status (e.g. `PENDING` -> `pending`), and localizing dates with standard language format codes dynamically matching the user's `LanguageContext`.

## Invariant (if applicable)

Locale selection defines how dates (`fmtDate`) and times (`fmtTime`) are read by the worker, independently of the server language.

## Design / Files

| File | Change |
|------|--------|
| `ihouse-ui/app/(app)/worker/page.tsx` | MODIFIED — added `getLocale`, case-insensitive status handling, and a Waze window opening button. |

## Result

**N tests pass, M skipped.** Mobile layout reads flawlessly. Navigation is completely integrated.
