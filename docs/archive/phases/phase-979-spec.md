# Phase 979 — Guest Dossier & Worker Check-in Hardening

**Status:** Closed
**Prerequisite:** Phase 958 (Worker Check-in Audit & Root-Cause Isolation)
**Date Closed:** 2026-03-28

## Goal

Complete the full Guest Dossier system (detail page with tabbed stay/activity/contact data, status badges, compact metadata, QR/portal actions), fix critical worker check-in task lifecycle bugs (orphaned tasks stuck as ACKNOWLEDGED after booking is checked_in), harden mobile worker navigation (breadcrumb leak suppression), improve mobile layout (horizontal gutter), implement human-readable countdown formatting, and fix the worker Home 'Next Up' broken modal / i18n token leak.

## Invariant

- Guest Dossier endpoint `/guests/{guest_id}` returns full denormalized guest record with stays, check-in records, and portal data.
- Self-healing mechanism in check-in wizard auto-completes orphaned ACKNOWLEDGED tasks when booking is already `checked_in`.
- Breadcrumbs suppressed on all mobile staff routes (`/worker`, `/ops/checkin`, `/ops/cleaner`, `/ops/checkout`, `/ops/maintenance`).
- MobileStaffShell provides consistent horizontal gutter (`paddingInline: var(--space-4)`) on all worker surfaces.
- LiveCountdown uses tiered human-readable format: `>48h → "13d"`, `24-48h → "1d 6h"`, `<24h → "18h 20m"`, `<1h → "42m 08s"`.
- Worker Home Next Up cards navigate directly to role-specific task flows — no generic modal.

## Design / Files

| File | Change |
|------|--------|
| `ihouse-ui/app/(app)/guests/[id]/page.tsx` | NEW — Full Guest Dossier page with tabbed UI (Current Stay, Activity, Contact) |
| `ihouse-ui/app/(app)/guests/page.tsx` | MODIFIED — Full-row clickability, navigation to dossier |
| `src/api/guest_router.py` | MODIFIED — `/guests/{guest_id}` endpoint with full denormalized response |
| `ihouse-ui/app/(app)/ops/checkin/page.tsx` | MODIFIED — Self-healing orphaned task logic, forceCompleteTask helper |
| `ihouse-ui/components/Breadcrumbs.tsx` | MODIFIED — Suppress on MOBILE_STAFF_PREFIXES |
| `ihouse-ui/components/MobileStaffShell.tsx` | MODIFIED — `paddingInline: var(--space-4)` on content area |
| `ihouse-ui/components/WorkerTaskCard.tsx` | MODIFIED — New `fmtDuration()` tiered format, adaptive tick rate, `LiveCountdown` exported |
| `ihouse-ui/app/(app)/worker/page.tsx` | MODIFIED — DetailSheet removed, Next Up onTap navigates to real flow, LiveCountdown in TaskCard |
| `ihouse-ui/components/CopyBtn.tsx` | MODIFIED — Borderless inline utility |
| `20260328_guest_dossier_schema.sql` | NEW — Migration for guest dossier fields |

## Result

**7,888 tests pass, 95 failed, 22 skipped.** (8,005 collected across 294 active test files)

95 failures are pre-existing across: `test_wave6_checkout_deposit_contract`, `test_wave7_manual_booking_takeover`, `test_whatsapp_escalation_contract`, `test_worker_router_contract`, `test_integration_management`, `test_notification_dispatcher_contract`. These are not regressions from Phase 979 — they existed before this phase.
