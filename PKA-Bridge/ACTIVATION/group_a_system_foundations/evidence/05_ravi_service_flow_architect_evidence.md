# Evidence File: Ravi — Service Flow Architect

**Paired memo:** `05_ravi_service_flow_architect.md`
**Evidence status:** Major revision on property readiness gate; deposit lifecycle partially resolved; task deduplication pattern confirmed

---

## Claim 1: No property readiness gate exists after cleaning

**Status:** DISPROVEN — readiness gate EXISTS in cleaning_task_router.py

**Evidence basis:**
- File: `src/api/cleaning_task_router.py`, lines 816-857: On cleaning completion, transitions property `operational_status` to `"ready"` or `"ready_with_issues"` (if open problem reports exist)
- File: `src/api/booking_checkin_router.py`, lines 402-410: Check-in sets `operational_status = "occupied"`
- File: `src/api/booking_checkin_router.py`, lines 595-603: Checkout sets `operational_status = "needs_cleaning"`

**What was observed:** The full property status lifecycle is:
```
ready → occupied (check-in) → needs_cleaning (checkout) → ready / ready_with_issues (cleaning completion)
```

The memo stated: "No function that transitions property from 'needs_cleaning' to 'vacant/ready' after cleaning task completion." This is WRONG. `cleaning_task_router.py` lines 816-857 explicitly perform this transition. The router even checks for open problem_reports and differentiates between `"ready"` and `"ready_with_issues"`.

**Confidence:** HIGH. Code path is unambiguous.

**Uncertainty:** The transition is a direct column write (not event-sourced), wrapped in a try/except. If the write fails, the property remains `needs_cleaning` with no reconciliation sweep. The cleaning task itself would still be marked COMPLETED. This is a silent-failure risk, not a missing-feature risk.

---

## Claim 2: Checkout creates a CLEANING task, potentially duplicating BOOKING_CREATED automation

**Status:** CONFIRMED — dual creation exists, but deduplication mechanism is present

**Evidence basis:**
- File: `src/api/booking_checkin_router.py`, lines 557-564: Checkout handler calls task creation for CLEANING task
- File: `src/tasks/task_writer.py`: `write_tasks_for_booking_created()` also creates CLEANING task on BOOKING_CREATED event
- File: `src/tasks/task_writer.py`: Task ID is deterministic: `sha256(kind:booking_id:property_id)[:16]` with on-conflict upsert

**What was observed:** Two code paths can create a CLEANING task for the same booking:
1. `task_automator` on BOOKING_CREATED → calls `write_tasks_for_booking_created()` → creates CLEANING task
2. `booking_checkin_router` on checkout → creates CLEANING task directly

The deterministic task_id (`sha256(CLEANING:booking_id:property_id)[:16]`) means that if both paths use the same booking_id and property_id, the on-conflict upsert prevents duplication. The second write updates the existing row rather than inserting a duplicate.

**Confidence:** HIGH on the deduplication mechanism. MEDIUM on whether both paths always produce identical inputs (booking_id and property_id).

**Uncertainty:** If the booking was amended between creation and checkout (property changed), the BOOKING_CREATED CLEANING task has the old property_id and the checkout CLEANING task has the new property_id. These would produce different task_ids, creating two CLEANING tasks — one for the old property (orphaned) and one for the new property (correct). The AMENDED handler reschedules PENDING tasks, which should handle this. But if the original task was already ACKNOWLEDGED or IN_PROGRESS, it would not be rescheduled, leaving the orphan.

---

## Claim 3: Settlement assumes deposit exists

**Status:** PARTIALLY VERIFIED — settlement reads deposits but skip logic needs confirmation

**Evidence basis:**
- File: `src/api/checkout_settlement_router.py`, lines 1194-1205: Finalize step updates `cash_deposits` status
- File: `src/api/checkout_settlement_router.py`, lines 52-61: Explicit invariant: "NEVER writes to event_log, booking_financial_facts, or booking_state"

**What was observed:** The settlement finalize step attempts to update cash_deposits. If no deposit record exists for the booking, the UPDATE would affect zero rows. Whether the code handles this gracefully (skip) or raises an error depends on the Supabase client behavior for zero-row updates.

**Confidence:** MEDIUM. The finalize code path exists, but the zero-deposit edge case handling was not fully traced.

**Uncertainty:** Does the frontend prevent reaching settlement finalize if no deposit was collected? Or does the backend handle the absence gracefully? This is a frontend-backend coordination question.

---

## Claim 4: Deposit lifecycle crosses 3 routers with unclear handoff

**Status:** REVISED — the handoff is clearer than the memo suggested, but still crosses router boundaries

**Evidence basis:**
- File: `src/api/checkin_settlement_router.py`, line 331: INSERT to `cash_deposits` (collection at check-in, Phase 964)
- File: `src/api/deposit_settlement_router.py`, line 116: INSERT to `cash_deposits` (manual deposit, Phase 687)
- File: `src/api/checkout_settlement_router.py`, lines 1194-1205: UPDATE `cash_deposits` status on finalize
- File: `src/api/deposit_settlement_router.py`, lines 17-33: Phase 690 checkout endpoint REMOVED — "wrote to wrong table, bypassed event_log, lacked role guard"

**What was observed:** All three routers operate on the SAME `cash_deposits` table. The join key is booking_id + tenant_id. The lifecycle is:
```
INSERT (check-in or manual) → [hold period] → UPDATE status (checkout finalize)
```

The memo framed this as "unclear handoff." In reality, the handoff is structurally simple — same table, same key. The risk is not data disconnection but dual-recording: both checkin_settlement_router and deposit_settlement_router can INSERT for the same booking.

The removal of Phase 690's checkout endpoint (which "wrote to wrong table") shows the team is actively aware of cross-router integrity and has corrected at least one violation.

**Confidence:** HIGH that the data connects. MEDIUM on whether deduplication prevents two deposit records for the same booking.

**Uncertainty:** Does `cash_deposits` have a UNIQUE constraint on `(booking_id, tenant_id)` or similar that prevents duplicate inserts? If not, the only guard is frontend behavior (not calling both endpoints for the same booking).

---

## Claim 5: Multi-step check-in wizard has no saga pattern

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/guest_checkin_form_router.py` — Step 1: writes guest form data independently
- File: `src/api/checkin_photos_router.py` — Step 2: writes walkthrough photos independently
- File: `src/api/checkin_settlement_router.py` — Step 3: writes meter reading + deposit independently
- File: `src/api/checkin_identity_router.py` — Step 4: writes passport/ID capture independently
- File: `src/api/booking_checkin_router.py` — Final step: transitions booking status to checked_in

**What was observed:** Each step writes to its own table/endpoint independently. No transaction coordinator wraps the multi-step sequence. No compensation mechanism rolls back previous steps if a later step fails.

If step 5 (deposit) fails after steps 1-4 succeeded:
- Guest form data exists (step 1) ✓
- Walkthrough photos exist (step 2) ✓
- No deposit record (step 5) ✗
- Booking status remains `active` (final step never reached) ✗
- The worker must retry step 5 or escalate manually

**Confidence:** HIGH. No saga or compensation pattern exists.

**Uncertainty:** Whether the frontend wizard allows retry of individual steps (resumability) or requires restart. If steps are resumable, the practical impact is low — the worker retries the failed step. If restart is required, steps 1-4 data becomes orphaned (though the on-conflict upsert pattern may handle re-creation cleanly).

---

## Claim 6: Task automation chain is complete and robust

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/tasks/task_automator.py`: BOOKING_CREATED → 3 tasks (CHECKIN_PREP, CLEANING, CHECKOUT_VERIFY); BOOKING_CANCELED → cancel PENDING tasks; BOOKING_AMENDED → reschedule
- File: `src/tasks/task_writer.py`: Deterministic task_id = `sha256(kind:booking_id:property_id)[:16]`, on-conflict upsert, Phase 1027a future-only cutoff, Phase 1030 primary worker selection by priority ASC, Phase 1033 canonical due_times
- File: `src/tasks/task_model.py`: 7 TaskKinds including SELF_CHECKIN_FOLLOWUP (Phase 1004), state machine including MANAGER_EXECUTING (Phase 1022)

**What was observed:** The automation chain handles the standard lifecycle correctly:
- Creation is idempotent (deterministic IDs + upsert)
- Cancellation only touches PENDING tasks (correct — ACKNOWLEDGED+ tasks need manual intervention)
- Amendment reschedules PENDING tasks
- Future-only cutoff prevents ghost tasks from iCal imports
- Primary worker selection uses staff_property_assignments with priority ordering

**Confidence:** HIGH

**Uncertainty:** The ACKNOWLEDGED+ cancellation gap (Claim 7 in Elena's evidence) means canceled bookings can leave workers preparing for a nonexistent guest. This is a known gap, not a bug — but it has no automated notification.

---

## Claim 7: Self check-in → staffed check-in handoff

**Status:** PARTIALLY VERIFIED

**Evidence basis:**
- File: `src/tasks/task_model.py`: SELF_CHECKIN_FOLLOWUP task kind (Phase 1004) exists
- File: `src/api/self_checkin_portal_router.py`: Two-gate architecture confirmed (Gate 1 blocking, Gate 2 non-blocking)

**What was observed:** Phase 1004 adds a SELF_CHECKIN_FOLLOWUP task kind, which suggests the system creates a follow-up task when self check-in is incomplete. The handoff trigger (when exactly this task is created — timeout? admin action? automatic after gate failure?) was not fully traced in the code reading.

**Confidence:** MEDIUM. The mechanism exists (task kind defined), but the triggering logic was not fully mapped.

**Uncertainty:** When and how SELF_CHECKIN_FOLLOWUP tasks are created. Is it a scheduled sweep, a webhook, or a manual admin trigger? This requires reading the pre_arrival_tasks module more deeply.

---

## Claim 8: SLA escalation chain is well-structured

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/tasks/sla_engine.py`: Evaluates ACK_SLA_BREACH and COMPLETION_SLA_BREACH. Terminal states (Completed, Cancelled) emit audit only, never escalate. Escalation targets: ops then admin.

**What was observed:** The SLA engine correctly differentiates between active tasks (escalatable) and terminal tasks (audit-only). The two breach types (acknowledgement and completion) cover the most important operational SLAs. The sweep runs every 120 seconds.

**Confidence:** HIGH

**Uncertainty:** None for the mechanism. Whether the SLA thresholds are correctly calibrated for real operations is an operational question, not a code question.

---

## Summary of Revisions

| Memo Claim | Evidence Status | Impact |
|---|---|---|
| No property readiness gate | **DISPROVEN** — gate exists in cleaning_task_router.py | Major positive revision — system is more complete than Ravi assessed |
| Deposit lifecycle unclear handoff | **REVISED** — same table, clear join key | Reduces risk severity from "unclear" to "dual-recording concern" |
| Dual CLEANING task risk | **CONFIRMED** with deduplication | Dedup mechanism exists; edge case on amended bookings |
| No saga pattern in wizard | **PROVEN** | Confirmed as stated |
| Task automation robust | **PROVEN** | Confirmed as stated |
| Settlement assumes deposit | **PARTIALLY VERIFIED** | Zero-deposit edge case not fully traced |
| Self check-in handoff | **PARTIALLY VERIFIED** | Task kind exists, trigger logic not mapped |
| SLA chain well-structured | **PROVEN** | Confirmed as stated |
