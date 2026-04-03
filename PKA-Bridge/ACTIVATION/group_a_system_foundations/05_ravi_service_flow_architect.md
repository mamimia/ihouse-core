# Activation Memo: Ravi — Service Flow Architect

**Phase:** 971 (Group A Activation)
**Date:** 2026-04-02
**Grounded in:** Direct reading of ihouse-core repository (task_automator, task_writer, booking_checkin_router, checkin_settlement_router, checkout_settlement_router, self_checkin_portal_router, cleaning_task_router, pre_arrival_tasks, sla_engine)

---

## 1. What in the Current Real System Belongs to This Domain

Ravi's domain is end-to-end service flow integrity — the complete chains that span multiple services and actors. The real system has these operational flows:

- **Booking intake flow**: OTA webhook → adapter → pipeline → CoreExecutor → apply_envelope → task automation
- **Pre-arrival flow**: Daily 06:00 UTC scan → CHECKIN_PREP + GUEST_WELCOME + SELF_CHECKIN_FOLLOWUP task generation for bookings 1-3 days out
- **Staffed check-in flow**: 7-step wizard (arrival confirmation → walkthrough photos → electricity meter → guest contact → deposit → passport/ID → complete + QR)
- **Self check-in flow**: Two-gate architecture (Gate 1: ID + agreement + deposit ack → access code release; Gate 2: meter + photos, non-blocking)
- **Checkout flow**: 4-step wizard (inspection → closing meter → issue flagging → deposit settlement)
- **Cleaning flow**: Template retrieval → task start → checklist execution → photos → supplies → issue reporting → complete
- **Maintenance flow**: Problem report → auto MAINTENANCE task → priority-to-SLA mapping → worker assignment → resolution
- **Settlement flow**: Draft → calculate (auto electricity deduction from meter delta) → add deductions → finalize (terminal)
- **Deposit lifecycle**: Collection at check-in → hold → settlement/return/forfeit at checkout
- **Task automation chain**: BOOKING_CREATED → 3 tasks; BOOKING_CANCELED → cancel PENDING; BOOKING_AMENDED → reschedule
- **SLA escalation chain**: SLA sweep (every 120s) → ACK_SLA_BREACH or COMPLETION_SLA_BREACH → notify_ops or notify_admin

## 2. What Appears Built

- **Task automation is complete and robust**: task_automator handles CREATED/CANCELED/AMENDED. task_writer creates deterministic tasks with idempotent upsert, auto-assigns via staff_property_assignments, and uses Phase 1030 primary worker selection by priority ASC. Phase 1027a prevents ghost tasks from historical imports. Phase 1033 writes canonical due_times.
- **7-step check-in flow**: Each step has a dedicated backend router. Sequence: guest_checkin_form (form+guests) → checkin_photos (walkthrough) → checkin_settlement (meter+deposit) → checkin_identity (passport/OCR) → booking_checkin (status transition + guest token). OCR linkage (Phase 988) connects captures to structured results.
- **Self check-in flow (Phase 1012)**: Complete two-gate architecture. Gate 1 is blocking (ID, agreement, deposit acknowledgement). Gate 2 is non-blocking (meter, arrival photos). Access code released only after Gate 1 + time gate. Admin can override mode (default, late_only, disabled).
- **4-step checkout flow**: inspection → closing meter → issue flagging → deposit settlement. checkout_settlement_router handles closing meter capture, settlement draft/calculate/finalize. booking_checkin_router handles status transition (checked_in → checked_out) + property status update + CLEANING task creation.
- **Settlement engine**: Draft → calculated → finalized. Auto-creates electricity deduction from (closing_reading - opening_reading) × rate_kwh. Damage and miscellaneous deductions added manually. Finalize locks settlement and updates cash_deposits status. Early checkout context captured (Phase 1001).
- **SLA escalation**: sla_engine evaluates ACK and COMPLETION breaches. Terminal states (Completed, Cancelled) emit audit only. Escalation targets: ops and admin.
- **Cleaning flow**: cleaning_task_router provides template retrieval (property-specific → tenant global → default fallback), progress tracking, photo uploads. Frontend cleaner page has checklist + photos + supplies + inline issue reporting.
- **Manager task takeover (Phase 1022)**: MANAGER_EXECUTING state allows manager to take over stuck tasks. Can reassign back to PENDING.

## 3. What Appears Partial

- **Checkout → CLEANING task creation**: booking_checkin_router's checkout handler creates a CLEANING task. But whether this task receives the correct property assignment and due_date (relative to next booking check-in, not checkout time) needs verification. The task_writer's BOOKING_CREATED automation already creates a CLEANING task — does the checkout handler create a duplicate, or does the deterministic task_id prevent it?
- **Settlement → deposit consistency**: Checkout settlement finalize updates cash_deposits status. But deposits were collected via checkin_settlement_router to cash_deposits (Phase 964). The checkout path reads from cash_deposits via a different router. The join key (booking_id + tenant_id) should connect them, but this assumption needs end-to-end trace.
- **Self check-in → staffed check-in handoff**: If self check-in fails mid-gate (e.g., guest can't complete ID verification), the system should fall back to staffed check-in. Phase 1004 adds SELF_CHECKIN_FOLLOWUP task kind for incomplete late self check-ins. But the handoff trigger and worker notification are not fully mapped.
- **Post-checkout property lifecycle**: After checkout, property status goes to 'needs_cleaning'. After cleaning completion, property should transition to 'vacant' (ready). This transition is not visible in the code I've read — there may be no readiness gate that flips property status after cleaning.

## 4. What Appears Missing

- **Property readiness gate**: No function that transitions property from 'needs_cleaning' to 'vacant/ready' after cleaning task completion. Cleaning task can be COMPLETED but property status may remain 'needs_cleaning' indefinitely. This is the gap Claudia's role was created to address.
- **Deposit lifecycle handoff documentation**: The path from deposit collection (check-in) through deposit hold (stay) to deposit settlement (checkout) crosses 3 routers. No single flow document maps this chain.
- **Booking amendment impact on active flows**: If a booking is amended after check-in has started (guest already arrived, form partially filled), what happens? task_automator reschedules PENDING tasks but cannot touch ACKNOWLEDGED+. The check-in wizard may be mid-flow with stale booking data.
- **Failure recovery in multi-step flows**: If the check-in wizard fails at step 5 (deposit) but steps 1-4 succeeded, what state is the check-in in? Each step appears to write independently — there is no transaction that rolls back steps 1-4 if step 5 fails. The partial state may leave an incomplete check-in with no clear recovery path.

## 5. What Appears Risky

- **Dual CLEANING task creation**: BOOKING_CREATED automation creates a CLEANING task. Checkout handler also creates a CLEANING task. Both use deterministic task_id based on kind:booking_id:property_id. If the parameters are identical, on-conflict upsert deduplicates correctly. But if the checkout handler uses a different property_id format or the booking was amended, a duplicate could be created.
- **No readiness gate after cleaning**: A property can be 'needs_cleaning' forever if the cleaning task is completed but no code transitions the property status. Next check-in could proceed on a property that the system still considers 'needs_cleaning'.
- **Multi-step wizard failure mid-flow**: The 7-step check-in wizard writes each step to a separate backend endpoint. No saga pattern or compensation mechanism exists. Partial completion creates orphaned data (e.g., deposit collected but check-in not completed — the guest portal token is never issued).
- **Settlement assumes deposit exists**: Checkout settlement finalize tries to update cash_deposits status. If no deposit was collected at check-in (property doesn't require it), the settlement flow should skip this. Whether the skip logic exists needs verification.

## 6. What Appears Correct and Worth Preserving

- **Task automation chain**: BOOKING_CREATED → 3 tasks, CANCELED → cancel PENDING, AMENDED → reschedule. This is well-designed, idempotent, and handles the common cases correctly.
- **Deterministic task IDs**: sha256 prevents duplicates. On-conflict upsert is the correct pattern.
- **Self check-in two-gate architecture**: Separating blocking prerequisites (Gate 1) from non-blocking nice-to-haves (Gate 2) is smart. Access code release only after Gate 1 completion + time gate is operationally sound.
- **Settlement state machine**: draft → calculated → finalized with auto electricity deduction is well-structured. Terminal state prevents re-processing.
- **SLA engine**: Clean evaluation with terminal-state awareness (completed/cancelled tasks never escalate). Correct separation of audit events from escalation actions.
- **Future-only task cutoff (Phase 1027a)**: Prevents ghost tasks from historical iCal imports. A practical, defensive rule.
- **Phase 1022 manager takeover**: Allows managers to unstick tasks without canceling them. Clean state transition model.

## 7. What This Role Would Prioritize Next

1. **Map the deposit lifecycle end-to-end**: Trace from check-in collection (which table, which columns) through checkout settlement (which table it reads, how finalize updates status). Identify whether the two deposit-related routers (checkin_settlement, deposit_settlement) both write to cash_deposits or to different tables.
2. **Verify the checkout → CLEANING task deduplication**: Confirm that the checkout handler and the BOOKING_CREATED automation produce the same task_id for the CLEANING task. If not, duplicates are created.
3. **Map the property status lifecycle**: Check-in sets 'occupied'. Checkout sets 'needs_cleaning'. What sets 'vacant/ready'? If nothing does, this is a flow gap.
4. **Document the check-in failure modes**: What partial states are possible if the wizard fails at each step? What is the recovery path for each?

## 8. Dependencies on Other Roles

- **Nadia**: Ravi needs Nadia to trace the deposit table write path — which endpoints write to which tables, and whether the checkout flow reads from the same table the check-in flow writes to
- **Elena**: Ravi needs Elena to verify whether checkout goes through apply_envelope — if not, the entire checkout flow's state transitions are outside the event log
- **Larry**: Ravi needs Larry to sequence the deposit lifecycle mapping — this blocks Victor (Group C) and affects Miriam's owner experience
- **Claudia (Group B)**: Ravi's finding about the missing readiness gate directly feeds Claudia's work on property turnover standards

## 9. What the Owner Most Urgently Needs to Understand

The service flows are substantially more complete than the original SYSTEM_MAP captured. The 7-step check-in, 4-step checkout, settlement engine, self-check-in portal, and manager task takeover are all built and appear well-structured.

Three flow gaps need attention:

1. **No property readiness gate**: After cleaning, nothing transitions the property back to 'ready'. This means the system cannot reliably answer "is this property ready for the next guest?"

2. **Deposit lifecycle crosses multiple routers with unclear handoff**: Money collected at check-in and settled at checkout may flow through different code paths. Until this is traced, deposit accounting is unverified.

3. **Multi-step wizard failure recovery**: The check-in and checkout wizards have no saga pattern. A failure mid-flow creates partial state with no defined recovery path. This is manageable for now (workers can retry or escalate), but will become a reliability concern at scale.
