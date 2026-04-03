# Phases 968–970: PKA-Bridge Team Build

## Purpose

Build the PKA-Bridge analytical team — a cohort of specialized role profiles designed to support the investigation, auditing, design, and coordination work needed to bring Domaniqo / iHouse Core from its current proven-but-partial state toward full production readiness.

These are not product implementation phases. They are PKA-Bridge workspace phases that establish the team structure for all subsequent analytical and coordination work.

## Phase 968: Wave 1 — Founding Cohort (4 roles)

**Status:** COMPLETE
**Date:** 2026-04-02

Core coordination, integration truth, mobile field surfaces, and interaction architecture.

| File | Name | Title |
|------|------|-------|
| `larry_chief_orchestrator.md` | Larry | Chief Orchestrator |
| `nadia_chief_product_integrator.md` | Nadia | Chief Product Integrator |
| `marco_mobile_systems_designer.md` | Marco | Mobile Systems Designer |
| `talia_product_interaction_designer.md` | Talia | Product Interaction Designer |

**Wave 1 covers:** cross-domain coordination and sequencing, API contract and integration verification, worker/ops mobile surface design, interaction architecture for built surfaces.

**Wave 1 refined:** narrowed after initial creation to prevent scope creep. Each role bounded to its specific domain; premature coverage of guest portal, AI copilot, notification infrastructure, and OTA domain ownership explicitly deferred.

## Phase 969: Wave 2 — System Architecture Cohort (4 roles)

**Status:** COMPLETE
**Date:** 2026-04-02

Role model clarity, operational surface differentiation, end-to-end flow architecture, and state consistency auditing.

| File | Name | Title |
|------|------|-------|
| `daniel_role_permission_architect.md` | Daniel | Role & Permission Architect |
| `sonia_operational_ux_architect.md` | Sonia | Operational UX Architect |
| `ravi_service_flow_architect.md` | Ravi | Service Flow Architect |
| `elena_state_consistency_auditor.md` | Elena | State & Consistency Auditor |

**Wave 2 covers:** permission model and access control logic, structural differentiation between role surfaces, end-to-end service flow mapping and handoff integrity, source-of-truth verification and projection drift detection.

**Boundary between Wave 1 and Wave 2:** Wave 1 asks "what exists and how does it work?" Wave 2 asks "why is it built this way, and what breaks if the rules are wrong?"

## Phase 970: Wave 3 — Domain Specialist Cohort (5 roles)

**Status:** COMPLETE
**Date:** 2026-04-02

Owner experience strategy, financial lifecycle logic, trust and privacy review, staff operations lifecycle, and guest-facing experience architecture.

| File | Name | Title |
|------|------|-------|
| `miriam_owner_experience_strategist.md` | Miriam | Owner Experience Strategist |
| `victor_financial_lifecycle_designer.md` | Victor | Financial Lifecycle Designer |
| `oren_trust_privacy_reviewer.md` | Oren | Trust & Privacy Reviewer |
| `hana_staff_operations_designer.md` | Hana | Staff Operations Designer |
| `yael_guest_experience_architect.md` | Yael | Guest Experience Architect |

**Wave 3 covers:** owner visibility strategy and trust lifecycle, payment/deposit/payout lifecycle logic, sensitive data exposure and trust boundary review, staff intake/onboarding/assignment/performance/offboarding lifecycle, guest portal experience and guest-side check-in/messaging/token lifecycle.

**Boundary between Wave 2 and Wave 3:** Wave 2 defines the structural rules (permissions, surface boundaries, flow architecture, state truth). Wave 3 applies domain-specific expertise to the stakeholders and lifecycles those rules serve (owners, finances, privacy, staff operations, guests).

## Pre-Activation Addition

**Date:** 2026-04-02

One additional role added before team activation to fill a critical operational gap: the system has cleaning checklists (`cleaning_task_progress`, `cleaning_photos`) and a cleaner surface (`/ops/cleaner`), but no authoritative definition of what "property ready" actually means — no room-by-room standards, no par levels, no issue classification logic, no readiness gate. This role provides the operational knowledge layer that the cleaning system needs to enforce.

| File | Name | Title |
|------|------|-------|
| `claudia_property_readiness_standards_architect.md` | Claudia | Property Readiness Standards Architect |

## Full Team Roster (14 roles)

| # | Name | Title | Wave | Domain |
|---|------|-------|------|--------|
| 1 | Larry | Chief Orchestrator | 1 | Cross-domain coordination |
| 2 | Nadia | Chief Product Integrator | 1 | Integration truth |
| 3 | Marco | Mobile Systems Designer | 1 | Worker/ops mobile surfaces |
| 4 | Talia | Product Interaction Designer | 1 | Interaction architecture |
| 5 | Daniel | Role & Permission Architect | 2 | Authorization model |
| 6 | Sonia | Operational UX Architect | 2 | Role surface differentiation |
| 7 | Ravi | Service Flow Architect | 2 | End-to-end flow integrity |
| 8 | Elena | State & Consistency Auditor | 2 | Data truth and consistency |
| 9 | Miriam | Owner Experience Strategist | 3 | Owner trust and visibility |
| 10 | Victor | Financial Lifecycle Designer | 3 | Payment/deposit/payout lifecycle |
| 11 | Oren | Trust & Privacy Reviewer | 3 | Sensitive data and trust boundaries |
| 12 | Hana | Staff Operations Designer | 3 | Staff lifecycle management |
| 13 | Yael | Guest Experience Architect | 3 | Guest-facing experience |
| 14 | Claudia | Property Readiness Standards Architect | 3+ | Turnover readiness and property standards |
