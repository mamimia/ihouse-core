# Evidence File: Larry — Chief Orchestrator

**Paired memo:** `01_larry_chief_orchestrator.md`
**Evidence status:** Mixed — some claims directly proven, some revised by deeper reading, some still hypotheses

---

## Claim 1: System has grown from 53+ to 134 routers

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/main.py` — all router mount calls enumerated
- Agent exploration listed all 134 router names from main.py mounts

**What was observed:** main.py registers 134 distinct router prefixes. The SYSTEM_MAP documented "53+ routers." The actual count is 134.

**Confidence:** HIGH

**Uncertainty:** None. The count is observable.

---

## Claim 2: Two deposit systems coexist as the highest cross-domain risk

**Status:** REVISED — both systems write to the SAME table, reducing the risk but not eliminating it

**Evidence basis:**
- File: `src/api/checkin_settlement_router.py`, line 331: `db.table("cash_deposits").insert(cash_deposit_row).execute()`
- File: `src/api/deposit_settlement_router.py`, line 116: `db.table("cash_deposits").insert(row).execute()`
- File: `src/api/checkout_settlement_router.py`, lines 1194-1205: `cash_deposits.update(status=...)` on finalize

**What was observed:** Both routers write to the **same table** (`cash_deposits`). This is better than two separate tables (no data split), but creates a **dual-recording risk**: if both the check-in wizard (Phase 964) and the manual deposit endpoint (Phase 687) are called for the same booking, two deposit records could exist for one booking. The checkout settlement finalize step updates cash_deposits status — it would update whichever record it finds.

**Confidence:** HIGH that they write to the same table. MEDIUM on the dual-recording risk — unclear if the frontend ever calls the Phase 687 manual endpoint during a standard workflow.

**Uncertainty:** Which frontend path calls which router? Does the check-in wizard exclusively use checkin_settlement_router, or does it sometimes fall back to deposit_settlement_router? This requires frontend code trace.

**Follow-up check:** Grep the frontend check-in wizard for the exact API endpoint it calls during the deposit step.

---

## Claim 3: Checkout event log bypass is the highest consistency risk

**Status:** REVISED — checkout DOES write to event_log, but BYPASSES apply_envelope

**Evidence basis:**
- File: `src/api/booking_checkin_router.py`, lines 549-551: Direct update to `booking_state` table via `db.table("booking_state").update(...)`
- File: `src/api/booking_checkin_router.py`, line 580: `_write_audit_event(db, booking_id, tenant_id, "BOOKING_CHECKED_OUT", event_log_payload)` — best-effort event_log write

**What was observed:** The checkout endpoint does TWO things: (1) writes directly to `booking_state` (bypassing apply_envelope), and (2) writes a `BOOKING_CHECKED_OUT` event to `event_log` (best-effort, separate call). This means the event_log IS populated, but the state change does NOT go through the apply_envelope RPC. apply_envelope handles BOOKING_CREATED, BOOKING_CANCELED, BOOKING_AMENDED — but NOT checkout. The checkout state change is a direct UPDATE to booking_state.

**Confidence:** HIGH. Code path is unambiguous.

**Uncertainty:** The event_log write is "best-effort" — if it fails, the event_log is incomplete while booking_state has changed. Also: a replay of event_log through apply_envelope would NOT produce a checkout state change, because apply_envelope doesn't handle BOOKING_CHECKED_OUT. The replay would show the booking as still `checked_in`.

**Follow-up check:** Verify whether the check-in endpoint follows the same pattern (direct booking_state write + best-effort event_log) or goes through apply_envelope.

---

## Claim 4: 134 routers with financial ordering dependencies is risky

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/main.py` — comment explicitly states financial-specific routes must register before the catch-all `/financial/{booking_id}`
- Router registration order: financial_aggregation_router, financial_dashboard_router, financial_correction_router, financial_explainer_router, financial_writer_router registered BEFORE financial_router

**What was observed:** The ordering constraint is real and documented in code. If a new financial sub-route is added after the catch-all, it would be swallowed.

**Confidence:** HIGH

**Uncertainty:** None for the current state. The risk is future — next router addition could break ordering.

---

## Claim 5: Task automation assumes upstream events

**Status:** DIRECTLY PROVEN with mitigation observed

**Evidence basis:**
- File: `src/tasks/task_writer.py`, lines 107-256: `write_tasks_for_booking_created()` is the sole task creation path for booking events
- File: `src/tasks/task_writer.py`, Phase 1027a: Future-only cutoff — skips task creation if `check_in < today`

**What was observed:** If BOOKING_CREATED doesn't fire (e.g., OTA webhook lost to DLQ), no tasks are generated. However, the DLQ monitoring system (10-minute sweep) exists to catch failed webhooks. The mitigation is real but asynchronous — a lost webhook creates a gap until DLQ replay.

**Confidence:** HIGH on the dependency. MEDIUM on the risk severity given DLQ mitigation exists.

**Uncertainty:** How long can a webhook sit in DLQ before a booking becomes operationally impacted? If a booking is created 1 day before check-in and the webhook fails, the pre-arrival scan (06:00 UTC daily) might also create CHECKIN_PREP — but only if the booking is already in booking_state. If the webhook never fires, the booking never enters booking_state, and pre-arrival scan finds nothing.

---

## Claim 6: SYSTEM_MAP is stale

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- SYSTEM_MAP documents 53+ routers; actual count is 134
- SYSTEM_MAP does not mention: self-check-in portal (Phase 1012), OCR platform (Phase 982), settlement engine (Phases 959-967), deposit suggestion flow (Phases 954-955), manager task takeover (Phase 1022), early checkout (Phase 1001), SELF_CHECKIN_FOLLOWUP task kind (Phase 1004), MANAGER_EXECUTING task state (Phase 1022)
- Check-in wizard is 7 steps in code, documented as 6 in SYSTEM_MAP

**Confidence:** HIGH

**Uncertainty:** None. Observable divergence.
