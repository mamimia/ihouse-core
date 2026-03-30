# Phase 1021 — Owner Bridge Flow

**Status:** Closed
**Prerequisite:** Phase 1003 — Canonical Block Classification & Bookings UX
**Date Closed:** 2026-03-29

## Goal

Implemented a real create-or-link flow for staff users with role = Owner in the Manage Staff surface. Previously, the CTA in the "Linked Owner Profile" section navigated to the Owners page with no context. This phase replaced that with a real bridge flow: a modal that carries over the staff user's personal details and existing property assignments into the owner creation/linking experience.

## Invariant

After takeover, the Owner profile created from a staff user must carry:
- Personal details (name, email, phone) from the staff record
- All existing property assignments already on the staff side
No manual re-entry should be required for already-known fields.

## Design / Files

| File | Change |
|------|--------|
| `ihouse-ui/app/(app)/admin/staff/[id]/page.tsx` | MODIFIED — replaced simple navigation CTA with modal-launching bridge flow |
| `ihouse-ui/components/owners/LinkOwnerModal.tsx` | NEW — create/link modal with prefilled personal details + property assignments |

## Result

The Linked Owner Profile section in Manage Staff now launches a real modal. When "Create new profile" is selected, the modal pre-fills name, email, phone and pre-selects all property assignments already existing for that staff user. The Owners page navigation was retained as the fallback path. No test count change (frontend-only change).
