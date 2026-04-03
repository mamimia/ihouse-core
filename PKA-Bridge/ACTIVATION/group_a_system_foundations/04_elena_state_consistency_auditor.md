# Activation Memo: Elena — State & Consistency Auditor

**Phase:** 971 (Group A Activation)
**Date:** 2026-04-02
**Grounded in:** Direct reading of ihouse-core repository (apply_envelope SQL, CoreExecutor, booking_checkin_router, checkout_settlement_router, task_writer, migrations)

---

## 1. What in the Current Real System Belongs to This Domain

Elena's domain is source-of-truth verification and consistency across the system's data stores. The real system has:

- **event_log** — append-only, canonical source of truth for all booking lifecycle events
- **booking_state** — derived projection, written ONLY via apply_envelope RPC (Supabase function)
- **booking_financial_facts** — separate financial projection, never in booking_state
- **cash_deposits** — deposit records written by checkin_settlement_router (Phase 964)
- **booking_settlement_records** — settlement lifecycle (draft → calculated → finalized)
- **tasks** — directly written (not event-sourced), creation triggered by booking events
- **properties.operational_status** — written by checkin/checkout endpoints
- **cleaning_task_progress** — checklist state per cleaning task
- **ocr_results** — OCR capture results with status tracking
- **apply_envelope** RPC — the sole write gate to booking_state, with row-level locking and idempotency

## 2. What Appears Built

- **apply_envelope** (Phase 50): Supabase SQL function handling BOOKING_CREATED, BOOKING_CANCELED, BOOKING_AMENDED. Row-level locking prevents races. Validates dates, checks overlaps. Appends STATE_UPSERT events to event_log. Idempotent via request_id dedup.
- **CoreExecutor commit policy**: Commits state only after apply_status == "APPLIED". Never commits in replay_mode. Clean separation.
- **Financial isolation**: booking_financial_facts is a separate table. apply_envelope never writes financial data. The invariant is architecturally enforced.
- **Settlement state machine**: booking_settlement_records use draft → calculated → finalized states. Finalized is terminal. Admin can void. State transitions are explicit.
- **OCR result lifecycle**: ocr_results track status (pending_review → confirmed/rejected/corrected/failed) with confidence scores. Clean state machine.
- **Task creation determinism**: task_id = sha256(kind:booking_id:property_id)[:16]. On-conflict upsert ensures idempotency.
- **Immutable audit trails**: acting_sessions, admin_audit_log, identity_repair_log — all append-only by design.

## 3. What Appears Partial

- **properties.operational_status**: Booking_checkin_router sets it to 'occupied' on check-in. Booking_checkin_router (checkout path) sets it to 'needs_cleaning'. But this is a direct column update — not event-sourced. If the checkout endpoint fails after updating booking_state but before updating property status, or vice versa, the two records diverge. No transactional guarantee links them.
- **Settlement-to-deposit consistency**: checkin_settlement_router writes deposits to cash_deposits. checkout_settlement_router's finalize step updates cash_deposits status. But the deposit_settlement_router (Phases 687-692) has its own deposit write/return/forfeit path. If both paths are active, cash_deposits could have records from two sources with different lifecycle assumptions.
- **Task state vs booking state**: Tasks are created by booking events but not event-sourced themselves. A booking could be CANCELED (via apply_envelope) but its tasks could remain in ACKNOWLEDGED or IN_PROGRESS if the cancellation automation fails or the task is already past PENDING state. The task system handles PENDING→CANCELED but acknowledges it cannot touch ACKNOWLEDGED+ tasks.

## 4. What Appears Missing

- **Projection drift detection**: No mechanism to compare event_log against booking_state and flag divergences. If apply_envelope fails silently or partially, the projection drifts with no alert.
- **Financial fact refresh**: booking_financial_facts is written by financial_writer_router. If the writer fails after an event is logged, the financial projection stalls. No sweep or reconciliation job catches this.
- **Settlement-to-event correlation**: Settlement records (booking_settlement_records) are written by the settlement engine but not linked to event_log entries. A settlement could exist for a booking whose checkout event was never logged.
- **Property status reconciliation**: No sweep that compares properties.operational_status against the latest booking_state for that property. Stale 'occupied' status after an unlogged checkout persists indefinitely.

## 5. What Appears Risky

- **Checkout write path**: booking_checkin_router's POST /bookings/{id}/checkout transitions booking status to 'checked_out'. The critical question is: does this transition go through apply_envelope (event-sourced) or does it write directly to booking_state? If direct, every downstream system that depends on event_log completeness (financial projections, audit trail, replay) will miss the checkout event. This is the single highest consistency risk and must be verified immediately.
- **Dual deposit write sources**: If both checkin_settlement_router and deposit_settlement_router write to cash_deposits, and a worker uses one path while an admin uses the other, deposit records could be duplicated or have conflicting states.
- **Task-booking divergence window**: Between a booking cancellation event and the task cancellation automation, there is a window where workers see active tasks for canceled bookings. For ACKNOWLEDGED+ tasks, this window is permanent — the automation cannot touch them.
- **Early checkout context**: Phase 1001 added early_checkout_at/reason/approved_by to booking_settlement_records. If checkout happens before settlement is created, these fields are never populated. The settlement and checkout flows are not guaranteed to execute in sequence.

## 6. What Appears Correct and Worth Preserving

- **apply_envelope as sole write gate**: This is architecturally sound. Row-level locking, idempotency via request_id, and STATE_UPSERT event emission make it the strongest piece of the consistency model.
- **Financial isolation invariant**: booking_state NEVER contains financial data. booking_financial_facts is completely separate. This is enforced at the schema level and the application level. Excellent.
- **Task ID determinism**: Idempotent task creation prevents duplicates. On-conflict upsert is the correct pattern.
- **Settlement state machine**: draft → calculated → finalized with explicit terminal states prevents accidental re-processing.
- **Append-only audit tables**: acting_sessions, identity_repair_log, admin_audit_log — immutable by design. Correct.

## 7. What This Role Would Prioritize Next

1. **Verify the checkout event log path**: Read booking_checkin_router's checkout handler and determine whether it calls apply_envelope or writes directly. This is the #1 consistency question.
2. **Map cash_deposits write sources**: Identify every code path that writes to the cash_deposits table. Determine whether there are truly two sources and whether they conflict.
3. **Assess projection drift risk**: Determine whether any mechanism exists to detect when booking_state diverges from event_log. If not, propose a sweep.

## 8. Dependencies on Other Roles

- **Nadia**: Elena needs Nadia to trace the checkout endpoint's actual database write path — is it apply_envelope or direct?
- **Ravi**: Elena needs Ravi to map the settlement flow sequence — does settlement always happen before checkout, after, or independently?
- **Larry**: Elena needs Larry to sequence the checkout verification — if it bypasses event_log, this affects every downstream system and must be fixed before other work proceeds
- **Victor (Group C)**: Elena's findings on financial projection consistency directly affect Victor's payment lifecycle design

## 9. What the Owner Most Urgently Needs to Understand

The event-sourced kernel is well-designed — apply_envelope is a strong write gate with locking and idempotency. Financial isolation is real and enforced. These are worth preserving.

The urgent concern is **whether checkout bypasses the event log**. If it does, then: (a) event_log is incomplete for any replayed booking, (b) financial projections triggered by checkout events may not fire, (c) the audit trail has a gap. This is not theoretical — Investigation #15 from the initial audit flagged exactly this. It needs to be verified against the current code, which has evolved since that investigation.

Secondary concern: **two deposit write paths** may create inconsistent financial records. This affects trust in the deposit lifecycle.
