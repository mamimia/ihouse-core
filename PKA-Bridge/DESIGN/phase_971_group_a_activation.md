# Phase 971: Group A Activation — System Foundations

## Purpose

First controlled activation of the PKA-Bridge team. Group A (5 roles) reads the real ihouse-core repository and produces first-pass domain memos grounded in actual code, not summaries or prior documentation.

## Status: COMPLETE

**Date:** 2026-04-02

## Activated Roles

| # | Name | Title | Memo |
|---|------|-------|------|
| 1 | Larry | Chief Orchestrator | `ACTIVATION/group_a_system_foundations/01_larry_chief_orchestrator.md` |
| 2 | Nadia | Chief Product Integrator | `ACTIVATION/group_a_system_foundations/02_nadia_chief_product_integrator.md` |
| 3 | Daniel | Role & Permission Architect | `ACTIVATION/group_a_system_foundations/03_daniel_role_permission_architect.md` |
| 4 | Elena | State & Consistency Auditor | `ACTIVATION/group_a_system_foundations/04_elena_state_consistency_auditor.md` |
| 5 | Ravi | Service Flow Architect | `ACTIVATION/group_a_system_foundations/05_ravi_service_flow_architect.md` |

## Key Findings

### System has grown significantly since SYSTEM_MAP
- SYSTEM_MAP documented 53+ routers; real system now has **134 routers**
- New systems not in SYSTEM_MAP: self-check-in portal (Phase 1012), OCR platform (Phase 982), settlement engine (Phases 959-967), deposit suggestion flow (Phases 954-955), manager task takeover (Phase 1022), early checkout support (Phase 1001)
- Check-in wizard is now 7 steps (was documented as 6)
- Task system extended: SELF_CHECKIN_FOLLOWUP kind (Phase 1004), MANAGER_EXECUTING state (Phase 1022)

### Cross-Role Convergence: Three urgent questions

**1. Dual deposit system (flagged by Larry, Nadia, Elena, Ravi)**
Two deposit-related router sets exist: checkin_settlement_router (Phase 964, writes to cash_deposits) and deposit_settlement_router (Phases 687-692, separate deposit collection/return/forfeit). All 4 roles independently flagged this as the highest-priority integration risk.

**2. Checkout event log path (flagged by Larry, Elena, Ravi)**
Whether POST /bookings/{id}/checkout writes through apply_envelope or bypasses the event log. This affects event_log completeness, financial projection triggers, audit trail, and replay reliability.

**3. Missing property readiness gate (flagged by Ravi)**
No mechanism transitions property status from 'needs_cleaning' to 'vacant/ready' after cleaning task completion. This means the system cannot reliably answer "is this property ready for the next guest?"

### Additional findings by role

- **Daniel**: 134 routers lack systematic role guard audit. Settlement/financial endpoints may accept any authenticated user. Manager capability enforcement pattern is unverified.
- **Elena**: properties.operational_status is not event-sourced — direct column updates with no transactional guarantee linking them to booking_state changes.
- **Nadia**: staffApi.ts has fewer typed wrapper methods than api.ts, creating contract risk for worker surfaces. No integration test layer visible.

## Recommended Pre-Group-B Actions

1. **Resolve the dual deposit question** — trace the exact table and column path from check-in collection to checkout settlement
2. **Verify the checkout event log path** — read booking_checkin_router's checkout handler to confirm whether it calls apply_envelope
3. **Update SYSTEM_MAP** — the current map is stale (53 → 134 routers, missing major features)

## Group B Activation Readiness

Group B (Sonia, Talia, Marco, Hana, Claudia) depends on Group A's integration truth and flow integrity findings. The deposit question and checkout event log question should be answered before Group B activation, because:
- Marco needs to know whether the check-in deposit step actually persists
- Claudia needs the property readiness gate to exist (or be defined) to build turnover standards
- Talia needs to know which flows have partial state to design recovery interactions
- Hana needs to know whether task assignment chains work end-to-end
