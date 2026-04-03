# Phase 972 — Group B Activation: Operational Product Surfaces

**Date:** 2026-04-03
**Depends on:** Phase 971 (Group A Activation)
**Status:** Complete

---

## Objective

Activate Group B (5 roles) to read the real operational product surfaces in ihouse-core and produce first-pass domain memos with paired evidence files. Group B covers the product-facing layer: role surfaces, interaction patterns, mobile worker experiences, staff lifecycle, and property readiness standards.

## Group B Roster

| # | Name | Title | Domain |
|---|------|-------|--------|
| 6 | Sonia | Operational UX Architect | Role surface differentiation, shell architecture, navigation |
| 7 | Talia | Product Interaction Designer | Interaction patterns, error handling, wizards, state-to-UI mapping |
| 8 | Marco | Mobile Systems Designer | Worker mobile surfaces, staffApi, camera, OCR, dark theme |
| 9 | Hana | Staff Operations Designer | Intake, onboarding, assignment, backfill, performance, deactivation |
| 10 | Claudia | Property Readiness Standards Architect | Templates, checklists, readiness gate, property status, escalation |

## Artifacts Produced

### Memos (PKA-Bridge/ACTIVATION/group_b_operational_product_surfaces/)
- `06_sonia_operational_ux_architect.md`
- `07_talia_product_interaction_designer.md`
- `08_marco_mobile_systems_designer.md`
- `09_hana_staff_operations_designer.md`
- `10_claudia_property_readiness_standards_architect.md`

### Evidence (PKA-Bridge/ACTIVATION/group_b_operational_product_surfaces/evidence/)
- `06_sonia_operational_ux_architect_evidence.md` — 7 claims
- `07_talia_product_interaction_designer_evidence.md` — 9 claims
- `08_marco_mobile_systems_designer_evidence.md` — 9 claims
- `09_hana_staff_operations_designer_evidence.md` — 9 claims
- `10_claudia_property_readiness_standards_architect_evidence.md` — 9 claims

## Key Findings

### Cross-Role Convergence Pattern: The System Is More Complete Than Expected

All 5 Group B roles independently discovered that their domain is substantially more built than the original SYSTEM_MAP suggested. Specific examples:

1. **Three-shell architecture** (Sonia): Not a single app with role-filtered menus — three genuinely distinct experiences (standard Sidebar, OMSidebar, MobileStaffShell).
2. **Structured error handling** (Talia): Clean 401/403 separation with CAPABILITY_DENIED inline handling. Not typical for early-stage SaaS.
3. **Full mobile stack** (Marco): Forced dark theme, safe area handling, OCR capture with confidence scoring, session isolation, role-specific bottom nav.
4. **Complete staff lifecycle** (Hana): Two onboarding paths, Primary/Backup priority, automatic task backfill, performance metrics, capability-gated management.
5. **Working readiness gate** (Claudia): 3-flag completion gate, problem report → maintenance auto-escalation, property status lifecycle.

### Cross-Role Gap Pattern: Deactivation and Recovery

Multiple roles converged on gaps related to what happens when things go wrong:

1. **Worker deactivation doesn't handle tasks** (Hana): Tasks remain assigned to deactivated workers. No warning, no auto-reassignment. #1 staff operations risk.
2. **No wizard recovery path** (Talia/Marco): Multi-step flows write independently with no saga pattern. Failure mid-flow requires manual retry.
3. **No offline resilience** (Marco): Workers with weak connectivity lose photo evidence. No persistent upload queue.
4. **No post-completion readiness update** (Claudia): Property status is set once at cleaning completion. Later issues don't downgrade status.

### Open Group A Questions — Group B Impact Assessment

1. **Deposit duplication guard**: Claudia noted that duplicate CLEANING tasks (if both BOOKING_CREATED and checkout create tasks with different IDs after amendment) could trigger the readiness gate twice. Low probability but theoretically possible.
2. **Settlement endpoint authorization**: Talia noted that if settlement endpoints lack capability guards, the checkout wizard's deposit step may expose settlement actions inappropriately.
3. **Checkout canonicality**: Claudia noted that all operational_status writes (check-in, checkout, cleaning) are direct writes, not event-sourced. If checkout canonicality is questioned, the same question applies to the entire operational_status lifecycle.

## Recommended Pre-Group-C Actions

1. **Verify deactivation task handling**: Determine if deactivation should auto-remove assignments (triggering task clearing) or at minimum warn admin.
2. **Verify owner visibility flag enforcement at query level**: Trace whether the summary endpoint filters data via SQL or relies on frontend rendering.
3. **Clarify manager FULL_ACCESS**: Determine if managers should have middleware-level restriction to `/manager/*` prefixes.
4. **Verify worker_roles population via invite path**: Confirm that the basic invite flow (not self-onboarding) correctly sets worker_roles array.
