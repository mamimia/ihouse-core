# Activation Memo: Larry — Chief Orchestrator

**Phase:** 971 (Group A Activation)
**Date:** 2026-04-02
**Grounded in:** Direct reading of ihouse-core repository

---

## 1. What in the Current Real System Belongs to This Domain

Larry's domain is cross-domain coherence — the invariants, dependencies, and sequencing risks that span multiple architectural layers. The real system has:

- **Event kernel** with CoreExecutor → EventLogPort → apply_envelope → StateStore commit pipeline
- **134 API routers** mounted in main.py with explicit ordering rules (financial-specific before financial catch-all)
- **Middleware stack** with 7 layers (CORS → SecurityHeaders → PreviewMode → ActAsAttribution → Envelope handlers → Monitoring → Logging)
- **Task automation** that chains booking events to task creation/cancellation/rescheduling
- **Two API client modules** (api.ts / staffApi.ts) with different token isolation models
- **10 canonical roles** with route-level and API-level authorization as separate enforcement layers
- **3 deployment environments** (dev SQLite, staging Supabase+Railway+Vercel, production Docker Compose)

## 2. What Appears Built

- Event-sourced kernel with apply_envelope RPC in Supabase (Phase 50), CoreExecutor, skill registry, and state projection
- Complete task automation: BOOKING_CREATED → CHECKIN_PREP + CLEANING + CHECKOUT_VERIFY; BOOKING_CANCELED → cancel PENDING; BOOKING_AMENDED → reschedule
- Task state machine extended to include MANAGER_EXECUTING (Phase 1022) and SELF_CHECKIN_FOLLOWUP (Phase 1004)
- 7-step check-in wizard (extended from 6), 4-step checkout flow, cleaner flow with checklist + photos
- Self check-in portal with two-gate architecture (Phase 1012)
- Settlement engine with draft → calculated → finalized lifecycle (Phases 959-967)
- OCR platform for meter readings and identity documents (Phase 982)
- Deposit suggestion flow with owner-initiated suggestions and admin approve/reject (Phases 954-955)
- 134 routers covering booking lifecycle, financial model, task system, guest portal, admin surfaces, worker flows, OTA adapters, AI copilot
- Middleware: PreviewMode (Phase 866) blocks mutations for preview-as; ActAsAttribution (Phase 869) dual-attributes mutations during act-as
- Future-only task cutoff (Phase 1027a) prevents ghost tasks from historical iCal imports

## 3. What Appears Partial

- **Check-in passport capture**: DEV_PASSPORT_BYPASS still referenced; OCR platform exists (Phase 982) but production camera wiring status unclear
- **Deposit persistence at check-in**: checkin_settlement_router writes to `cash_deposits` (Phase 964 confirmed), but the older deposit_settlement_router (Phases 687-692) represents a parallel deposit path — two deposit systems may coexist
- **Owner visibility toggles**: owner_portal_v2_router defines 8 flags but filtering in query logic unconfirmed
- **Cleaning checklist connection**: cleaning_checklist_templates + cleaning_task_progress tables exist, backend router exists (Phases 626-632), frontend cleaner page exists — but the end-to-end connection between template seeding and task-specific checklist rendering needs verification

## 4. What Appears Missing

- **Readiness gate**: No function that aggregates cleaning checklist completion + photo compliance + escalation status into a pass/fail property-ready signal
- **Guest extras catalog**: Schema tables exist (extras_catalog, property_extras, extra_orders in Phase 586-605 migration) but implementation status unclear — gap analysis claimed 0%
- **Worker notification channel config UI**: Backend notification_channels table exists but no confirmed UI for workers to set their preferred channel
- **Unified deposit lifecycle**: Two deposit systems exist (deposit_settlement_router Phases 687-692 and checkin_settlement_router Phases 957-964) — the relationship and lifecycle handoff between them needs mapping

## 5. What Appears Risky

- **Two deposit systems coexisting**: checkin_settlement_router (Phase 964) writes to `cash_deposits`; deposit_settlement_router (Phases 687-692) has its own deposit collection/return/forfeit flow. If both are active, deposits could be double-recorded or inconsistently tracked. This is the single highest cross-domain risk I see.
- **Checkout event log bypass**: Investigation #15 previously identified that checkout writes directly to booking_state. The checkout flow now uses booking_checkin_router's POST /bookings/{id}/checkout — need to verify whether this goes through apply_envelope or bypasses it.
- **134 routers with ordering dependencies**: Financial routers must be registered before the catch-all. Any router addition that violates this ordering silently breaks route matching.
- **Task automation assumes upstream events**: If BOOKING_CREATED doesn't fire (e.g., iCal import edge case), no tasks are generated and the property gets no operational preparation.

## 6. What Appears Correct and Worth Preserving

- **Event kernel invariant**: apply_envelope as the sole write path to booking_state is architecturally sound and enforced in Supabase
- **Task ID determinism**: sha256(kind:booking_id:property_id)[:16] ensures idempotent task creation — excellent pattern
- **Middleware stack ordering**: Security → Preview → ActAs → Monitoring is correct; each layer has clear responsibilities
- **Two API client isolation**: api.ts (localStorage) vs staffApi.ts (sessionStorage-first) prevents Act As session contamination — this is a critical safety boundary
- **Phase locking discipline**: Phase 888 (task backfill), Phase 91 (CRITICAL SLA = 5 min) are explicitly locked and cannot change
- **Future-only task cutoff (Phase 1027a)**: Prevents ghost tasks from historical imports — a practical, defensive rule

## 7. What This Role Would Prioritize Next

1. **Resolve the dual deposit system risk**: Map the relationship between deposit_settlement_router and checkin_settlement_router. Determine if one supersedes the other or if they handle different lifecycle stages. This blocks Victor (financial lifecycle) and Ravi (service flows).
2. **Verify checkout event log path**: Confirm whether POST /bookings/{id}/checkout writes through apply_envelope or bypasses the event log. This is a state consistency risk that blocks Elena.
3. **Sequence Group B activation**: Ensure Nadia, Daniel, Elena, and Ravi complete their first-pass findings before activating operational surface roles who depend on integration truth and flow integrity.

## 8. Dependencies on Other Roles

- **Nadia**: Larry needs Nadia to verify the dual deposit system wiring — which endpoints are live, which are deprecated, which are redundant
- **Elena**: Larry needs Elena to verify whether checkout bypasses the event log and whether booking_state projections are consistent with event_log
- **Ravi**: Larry needs Ravi to map the full deposit lifecycle (collection → hold → settlement) across both deposit systems and determine the canonical flow
- **Daniel**: Larry needs Daniel to validate that the 134 routers have consistent role guards (especially the financial and settlement endpoints)

## 9. What the Owner Most Urgently Needs to Understand

The system has grown significantly since the initial audit. It now has 134 routers (up from "53+" in SYSTEM_MAP), a self-check-in portal (Phase 1012), an OCR platform (Phase 982), a settlement engine (Phases 959-967), and a deposit suggestion flow (Phases 954-955). The SYSTEM_MAP is now stale relative to the real codebase.

The most urgent risk is the **dual deposit system**: two independent router sets handle deposit operations, and it is not clear whether they are complementary lifecycle stages or redundant parallel paths. If both are active, money tracking becomes unreliable. This must be resolved before any financial lifecycle or settlement work proceeds.
