# Phase 1024 — Identity Mismatch & Auth-Email Repair Path

**Status:** Closed
**Prerequisite:** Phase 1023 — Staff Onboarding Error Clarity & Role Integrity
**Date Closed:** 2026-03-30

## Goal

Addressed a real-world case where a worker submitted onboarding with a wrong email. The admin corrected the email in the staff card but the auth identity remained tied to the old email, causing an Identity Mismatch / Access Link Blocked state. Analyzed the repair path and improved the auth-email repair flow by replacing a fragile route with a hardened alternative.

## Invariant

- Auth identity and staff card email must remain synchronized
- Email correction in admin staff card must trigger or surface a repair path for the auth identity
- Admin must be clearly informed when an identity mismatch exists

## Design / Files

| File | Change |
|------|--------|
| `src/api/` (auth-email repair route) | MODIFIED — replaced fragile identity repair route with hardened path |
| `ihouse-ui/app/(app)/admin/staff/[id]/` | MODIFIED — surfaces identity mismatch state to admin |

## Result

Identity mismatch scenarios surface to admin. Auth-email repair path improved. Area remains sensitive — full proof requires real login-path verification when mismatch case is active.
