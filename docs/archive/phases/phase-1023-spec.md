# Phase 1023 — Staff Onboarding Error Clarity & Role Integrity

**Status:** Closed
**Prerequisite:** Phase 1022 — Operational Manager Takeover Gate
**Date Closed:** 2026-03-30

## Goal

Addressed the "UNKNOWN_ERROR" masking problem in the staff onboarding frontend. The frontend was swallowing real backend error codes/messages and replacing them with a generic string. Improved status derivation for id/work permit documents. Hardened role integrity so that the Combined (checkin+checkout) role is correctly normalized instead of being stored as a broken slash-string, and ensured the Operational Manager invite flow no longer routes through worker sub-role logic.

## Invariant

- Frontend must surface real backend error codes — no generic UNKNOWN_ERROR fallback
- Combined role = checkin + checkout in worker_roles array, never a slash-string
- Operational Manager invite flow must not be processed as a worker sub-role invite

## Design / Files

| File | Change |
|------|--------|
| `ihouse-ui/app/(app)/admin/staff/` | MODIFIED — surfaces real backend error messages instead of UNKNOWN_ERROR |
| `ihouse-ui/` (invite + onboarding paths) | MODIFIED — Combined role normalization; OM invite route separation |

## Result

Staff onboarding errors now correctly surface real backend responses. Combined role stored as array [checkin, checkout]. Operational Manager invite no longer falls through worker sub-role path.
