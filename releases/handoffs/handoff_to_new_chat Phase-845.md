> ⚠️ FIRST: Read `docs/core/BOOT.md` before doing anything else.

# Handoff to New Chat — Phase 846 Initialization

**Current Phase:** Phase 846 — Admin Preview As Context Scaffolding
**Last Closed Phase:** Phase 845 — Worker App Functionality Polish & Date Formatting
**Status:** Worker surface localized, visually consistent, dynamically populated for real workflows array (`worker_roles`).

## Next Objective

The next major feature to implement is the **"Preview As"** capability for Admins inside the Admin Interface `/admin/`. Admins should have a dropdown that allows them to securely mock and render the `ihouse-ui` interfaces exactly as specific Field Workers or Guests would see it, enabling seamless QA and operational verification. 

## The Next 10 Phases Sequence 
(Consult `docs/core/work-context.md` for extended details)

- Phase 846: Admin Preview As Context Scaffolding
- Phase 847: Admin Preview As Role & Org JWT Simulation
- Phase 848: Admin Dashboard Flight Cards (Ops Awareness)
- Phase 849: Staff Management Profiles & Avatar Upload
- Phase 850: Mobile Check-in Flow (Deposit, Auth)
- Phase 851: Mobile Checkout Flow (Inspection, Issues)
- Phase 852: Guest Portal Mobile Form Polish
- Phase 853: Owner Statement PDF Pipeline Localization
- Phase 854: Route Guard Test Suite Validation
- Phase 855: End-To-End Operations Day Simulation

## Key In-Progress State

- The worker interface (`/worker`) was effectively unified under Mobile First strict layout wrapping (`AdaptiveShell`). Everything should render to look precisely like a phone app inside the desktop, with `max-width: 480px`.
- Role verification backend `/tasks/worker` now safely extracts data correctly for Field Workers who assume a series of roles (array `worker_roles`). Zero roles return zero elements without an `HTTP 500`.
- Domaniqo brand (`Midnight Graphite`, `Deep Moss`) custom css colors override generic Tailwind definitions. Keep all design implementations compliant.

Please start by confirming Phase 846 initialization and state your operational plan for the Preview As Context Scaffolding.
