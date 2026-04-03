# Group A Audit Result: Elena — State & Consistency Auditor

**Audit date:** 2026-04-04
**Auditor:** Antigravity (session 627e84a9)

---

## Verdict: PARTIALLY REAL

Two concerns are real (checkout write-gate bypass, event_log replay incompleteness). One concern is disproven (missing property readiness gate). Financial isolation is confirmed correct. The real issues are documented and planned; no new fix was triggered in this pass because the issues are already captured under Phase 1056.

---

## Evidence Basis

### Checkout bypasses apply_envelope (primary concern)

**REAL — confirmed.**

`booking_checkin_router.py` lines 549–551: Direct `db.table("booking_state").update(...)` call. This is NOT routed through `apply_envelope`.

`booking_checkin_router.py` line 580: `_write_audit_event(db, booking_id, tenant_id, "BOOKING_CHECKED_OUT", ...)` — best-effort event_log write.

**Consequence:**
- `booking_state` transitions for check-in and checkout are **direct writes**, not event-sourced.
- `event_log` contains `BOOKING_CHECKED_IN` and `BOOKING_CHECKED_OUT` entries (usually — best-effort means they can be lost silently).
- `apply_envelope` only handles `BOOKING_CREATED`, `BOOKING_CANCELED`, `BOOKING_AMENDED`. A replay through `apply_envelope` would leave every booking in `active` state — checkout and check-in transitions would be missing.
- This is NOT a newly discovered issue. It matches Investigation #15 from the original audit and is formally captured under **Phase 1056 (Write-Gate Alignment)** in the phase timeline.

**Important nuance from evidence file (Claim 1):** The evidence suggests this may be a deliberate architectural split — OTA lifecycle events go through `apply_envelope`; operational lifecycle events (check-in/checkout) go through `booking_checkin_router` with direct writes. This is not documented as an explicit design decision in BOOT.md, which is why Phase 1056 requires either a migration to Option 1 (full apply_envelope) or a formal documented exception.

### Financial isolation

**CONFIRMED CORRECT.** `booking_state` never contains financial data. `booking_financial_facts` is completely separate. Multiple routers independently declare this invariant in their docstrings (`checkout_settlement_router.py` line 59, `cleaning_task_router.py` lines 15–17).

### Property status lifecycle (readiness gate)

**DISPROVEN — the gate exists.**

`cleaning_task_router.py` lines 816–857: On cleaning task completion, the router updates `properties.operational_status` to `"ready"` or `"ready_with_issues"` (if open `problem_reports` exist). Full cycle:
```
ready → occupied (check-in) → needs_cleaning (checkout) → ready / ready_with_issues (cleaning completion)
```
The memo's claim that "no mechanism transitions property status from needs_cleaning to vacant/ready after cleaning" is **incorrect**.

Caveat: The transition is a direct column write wrapped in try/except (best-effort). Silent failure leaves the property in `needs_cleaning` indefinitely. A reconciliation sweep does not exist.

### Settlement-to-event correlation

**Confirmed gap — but deliberately designed.**

`checkout_settlement_router.py` line 59: "NEVER writes to event_log." Settlement records live in `booking_settlement_records` and audit to `admin_audit_log`. No event_log entry exists for settlement creation, calculation, or finalization. The router header explicitly states "financial integration is deferred."

This is a known, intentional design gap. It is not a bug — it is deferred scope.

### Task-booking divergence window

**REAL — confirmed.** `task_writer.py` `cancel_tasks_for_booking_canceled()` cancels PENDING tasks only. ACKNOWLEDGED and IN_PROGRESS tasks survive a booking cancellation. This is the Phase 1055 gap already documented and planned.

---

## Fix Needed

**No new fix triggered in this pass.**

---

## Why Not Fixed

- Checkout write-gate bypass: Already documented as Phase 1056 in the canonical phase timeline. The architecture decision (Option 1 full migration vs. documented exception) requires deliberate product input, not an immediate code change.
- Task-booking divergence: Already Phase 1055 in the canonical phase timeline.
- Property readiness gate: Does not exist as a problem — the gate is already implemented.
- Settlement-to-event gap: Intentional deferred scope per router docstring.
