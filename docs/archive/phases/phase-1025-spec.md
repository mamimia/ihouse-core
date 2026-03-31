# Phase 1025 — Public Property Submission Flow Hardening

**Status:** Closed
**Prerequisite:** Phase 1024 — Identity Mismatch & Auth-Email Repair Path
**Date Closed:** 2026-03-30

## Goal

Fixed stale-state blocking in the public property submission flow. A previously submitted listing in a stale non-active state (draft/rejected/archived) could block a new submission. Added visible and safe My Properties delete affordance with confirmation dialog. Improved submitter journey so it does not dead-end in a list. Improved intake queue to show submitter phone in addition to email.

## Invariant

- Stale draft/rejected/archived listings must not block new submission for the same submitter
- Delete of a submitted property must require explicit confirmation
- Intake queue must show submitter phone, not only email

## Design / Files

| File | Change |
|------|--------|
| `src/api/` (public submission route) | MODIFIED — stale blocking state cleared before new submission allowed |
| `ihouse-ui/app/(public)/` (My Properties) | MODIFIED — delete affordance + confirmation dialog |
| `ihouse-ui/app/(app)/admin/` (intake queue) | MODIFIED — submitter phone column added |

## Result

Stale-state submission blocking fixed. Delete flow hardened with confirmation. Intake queue shows phone. Screenshot proof was partial — treat as built, not fully staging-proven.
