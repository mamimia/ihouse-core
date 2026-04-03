# Evidence File: Elena — State & Consistency Auditor

**Paired memo:** `04_elena_state_consistency_auditor.md`
**Evidence status:** Critical claims revised by deep code reading; the checkout path finding is significantly more nuanced than the memo suggested

---

## Claim 1: apply_envelope is the sole write gate to booking_state

**Status:** REVISED — apply_envelope is the write gate for CREATED/CANCELED/AMENDED, but NOT for check-in or checkout

**Evidence basis:**
- File: `supabase/migrations/20260308210000_phase50_step2_apply_envelope_amended.sql` — handles BOOKING_CREATED, BOOKING_CANCELED, BOOKING_AMENDED only
- File: `src/api/booking_checkin_router.py`, lines 549-551: checkout writes directly to booking_state via `db.table("booking_state").update(...)`
- File: `src/api/booking_checkin_router.py`, lines 393-410: check-in also writes directly to booking_state (status="checked_in", checked_in_at, property operational_status)

**What was observed:** apply_envelope handles the OTA-lifecycle events (created, canceled, amended). But the operational-lifecycle events (check-in, checkout) bypass apply_envelope and write directly to booking_state. Both check-in and checkout then write a separate audit event to event_log (best-effort).

**This means:**
- A replay of event_log through apply_envelope would reconstruct bookings up to `active` status but would NOT show check-in or checkout transitions
- The event_log contains BOOKING_CHECKED_IN and BOOKING_CHECKED_OUT events (best-effort writes), but apply_envelope cannot process them
- booking_state and event_log are NOT fully consistent — booking_state has operational transitions that are only partially represented in event_log

**Confidence:** HIGH. Multiple code paths confirm this pattern.

**Uncertainty:** Is this by design? The checkout_settlement_router header explicitly states "NEVER writes to event_log, booking_financial_facts, or booking_state" and "Booking status transitions are owned exclusively by booking_checkin_router." This suggests a deliberate architectural choice: OTA events go through apply_envelope, operational events go through booking_checkin_router with direct writes.

---

## Claim 2: Financial isolation is architecturally enforced

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `supabase/migrations/20260308210000_phase50_step2_apply_envelope_amended.sql` — apply_envelope never writes to booking_financial_facts
- File: `src/api/financial_router.py` — reads from booking_financial_facts ONLY
- File: `src/api/checkout_settlement_router.py`, lines 52-61: explicit invariant comment: "NEVER writes to event_log, booking_financial_facts, or booking_state"
- File: `src/api/cleaning_task_router.py`, lines 15-17: "This router NEVER writes to booking_state, event_log, or booking_financial_facts"

**What was observed:** Multiple routers have explicit comments declaring they never cross the financial isolation boundary. The financial router reads only from booking_financial_facts. apply_envelope writes only to booking_state. The invariant is enforced by convention AND by code separation.

**Confidence:** HIGH

**Uncertainty:** None observed. Multiple independent routers independently declare the same invariant.

---

## Claim 3: properties.operational_status is not event-sourced and has no reconciliation

**Status:** REVISED — the status lifecycle is MORE complete than the memo claimed

**Evidence basis:**
- File: `src/api/booking_checkin_router.py`, lines 402-410: check-in → `operational_status = "occupied"`
- File: `src/api/booking_checkin_router.py`, lines 595-603: checkout → `operational_status = "needs_cleaning"`
- File: `src/api/cleaning_task_router.py`, lines 816-857: cleaning completion → `operational_status = "ready"` or `"ready_with_issues"` (if open problem reports exist)

**What was observed:** The property status lifecycle is:
```
occupied → needs_cleaning → ready (or ready_with_issues)
```

This is MORE complete than the memo claimed. The memo stated "No mechanism transitions property status from 'needs_cleaning' to 'vacant/ready' after cleaning." This is WRONG — `cleaning_task_router.py` lines 816-857 DO transition the property to "ready" on cleaning completion. It even checks for open problem reports and sets "ready_with_issues" if any exist.

However, the status updates are still direct column writes (not event-sourced). Each write is best-effort with try/except that logs warnings but doesn't block the parent operation. If any write fails silently, the property status is stale with no reconciliation sweep.

**Confidence:** HIGH that the lifecycle exists. HIGH that it is not event-sourced. MEDIUM on the silent-failure risk.

**Uncertainty:** The audit trail for property status changes exists only in cleaning_task_router (writes audit event via `write_audit_event()`). Check-in and checkout status changes do NOT write audit events for the property status change specifically — they write audit events for the booking status change.

---

## Claim 4: Checkout event log bypass

**Status:** REVISED — checkout writes to event_log (best-effort) but bypasses apply_envelope

**Evidence basis:**
- File: `src/api/booking_checkin_router.py`, line 580: `_write_audit_event(db, booking_id, tenant_id, "BOOKING_CHECKED_OUT", event_log_payload)`
- File: `src/api/booking_checkin_router.py`, lines 549-551: `db.table("booking_state").update(booking_state_update)` — direct write

**What was observed:** Checkout does TWO writes:
1. Direct UPDATE to booking_state (bypasses apply_envelope)
2. Best-effort INSERT to event_log with type "BOOKING_CHECKED_OUT"

The event_log write exists but: (a) it is best-effort (failure is swallowed), (b) apply_envelope cannot process BOOKING_CHECKED_OUT events, (c) a replay would not reconstruct the checkout.

**This is a WEAKER bypass than Investigation #15 implied:** the event_log IS populated (usually), but the state change is not event-sourced.

**Confidence:** HIGH

**Uncertainty:** Whether the best-effort event_log write has ever failed in practice (no monitoring observed).

---

## Claim 5: Settlement-to-event correlation is missing

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/checkout_settlement_router.py`, lines 52-61: "NEVER writes to event_log"
- Settlement records live in `booking_settlement_records`; event_log has no settlement events
- Settlement audit goes to `admin_audit_log`, not event_log

**What was observed:** Settlement operations are intentionally outside the event-sourced domain. They write to their own tables (booking_settlement_records, deposit_deductions, electricity_meter_readings) and audit to admin_audit_log. There is NO event_log entry for settlement creation, calculation, or finalization.

**Confidence:** HIGH

**Uncertainty:** Is this a gap or a deliberate design choice? The router header suggests deliberate: "financial integration is deferred." This means settlement-to-financial-projection linkage does not exist yet — settlements are operationally tracked but not reflected in booking_financial_facts.

---

## Claim 6: Dual deposit write sources

**Status:** CONFIRMED — but same table, reduced risk

**Evidence basis:**
- File: `src/api/checkin_settlement_router.py`, line 331: INSERT to cash_deposits (Phase 964)
- File: `src/api/deposit_settlement_router.py`, line 116: INSERT to cash_deposits (Phase 687)
- File: `src/api/checkout_settlement_router.py`, lines 1194-1205: UPDATE cash_deposits on finalize
- File: `src/api/deposit_settlement_router.py`, lines 17-33: Comment states "Phase 690 checkout endpoint REMOVED — wrote to wrong table, bypassed event_log, lacked role guard"

**What was observed:** Both routers write to the same cash_deposits table. A historical Phase 690 checkout endpoint was explicitly REMOVED because it was incorrect. This suggests the team is aware of the dual-path risk and has already corrected one instance. The remaining dual-write risk is: both check-in wizard and manual deposit endpoint can INSERT to cash_deposits for the same booking.

**Confidence:** HIGH

**Uncertainty:** Whether any deduplication guard prevents two deposit records for the same booking_id.

**Follow-up check:** Check if cash_deposits has a UNIQUE constraint on (booking_id, tenant_id) that would prevent duplicates.

---

## Claim 7: Task-booking divergence window

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/tasks/task_writer.py` — `cancel_tasks_for_booking_canceled()` only cancels PENDING tasks
- Phase 888 (locked): task backfill never touches ACKNOWLEDGED+ tasks
- Task state machine: ACKNOWLEDGED and IN_PROGRESS cannot be automatically moved to CANCELED by the automator

**What was observed:** If a booking is canceled after a worker has acknowledged a task, that task remains in ACKNOWLEDGED or IN_PROGRESS. The worker continues preparing for a canceled booking until they manually notice or are notified.

**Confidence:** HIGH

**Uncertainty:** Whether the worker receives a notification about the booking cancellation. No notification-on-cancel logic was observed in the code paths read.
