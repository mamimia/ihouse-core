# iHouse Core — System Audit & Hardening Pass
## Phases 1054–1057

**Date:** 2026-04-03  
**Status:** AUDIT COMPLETE — Fix phases defined (1055–1057 pending execution)  
**Auditor:** Antigravity (session 627e84a9)

---

## Scope

Six suspected issues raised by product/audit review. Each item was audited against the live codebase before any fixes were proposed. Verdicts are evidence-backed.

---

## Audit Verdicts

### Issue 1 — Check-in/Check-out Write-Gate Bypass

**Claimed:** The check-in and check-out path writes directly to `booking_state` and `event_log` without going through `apply_envelope`.

**Verdict: REAL ISSUE**

**Evidence (`src/api/booking_checkin_router.py`):**

The router writes to `booking_state` and appends to `event_log` independently. It does **not** call `apply_envelope`, does not go through `CoreExecutor`, and bypasses the RPC validation layer entirely. This means check-in/check-out events:
- Are never validated by the canonical envelope schema
- Cannot be deterministically replayed from the ledger
- Break the system's single-write-gate invariant

**Auth note:** The router does correctly enforce role guards (`_WRITE_ROLES`, `_CHECKIN_ROLES`). The issue is write-path architecture, not access control.

**Risk:** High — architectural consistency. Not a data loss risk today, but prevents deterministic rebuild and undermines the core audit invariant.

**Fix phase:** 1056

---

### Issue 2 — Deposit Lifecycle Dual-Recording Risk

**Claimed:** Deposits may be recorded in two places, creating a dual-recording or reconciliation risk.

**Verdict: NOT REAL**

**Evidence:**
- `checkin_settlement_router.py`: writes deposits exclusively to `cash_deposits` table. Confirmed `require_capability("financial")` guard enforced.
- `deposit_settlement_router.py`: manages the deposit lifecycle (collected → partially_returned → fully_returned) **solely** within `cash_deposits`. No cross-writes to `booking_state` financial fields or `booking_financial_facts`.
- `checkout_settlement_router.py` (line 58–61, docstring invariant): **"NEVER writes to event_log, booking_state, or booking_financial_facts."** The only cross-table side-effect is the `cash_deposits` status update at `finalize`.

`cash_deposits` is the canonical, single source of truth for deposit state. There is no dual-recording path.

**Risk:** None.

---

### Issue 3 — Settlement Auth Coverage

**Claimed:** Settlement endpoints may lack adequate authorization, allowing unauthorized role access to financial operations.

**Verdict: NOT REAL**

**Evidence (`checkout_settlement_router.py`):**

```
_WRITE_ROLES    = frozenset({"admin", "ops", "worker", "checkin", "checkout"})
_DEDUCT_ROLES   = frozenset({"admin", "ops", "checkout"})
_FINALIZE_ROLES = frozenset({"admin", "ops", "worker", "checkout"})
_VOID_ROLES     = frozenset({"admin"})
```

Role guards are applied at every mutation endpoint. Additionally, `capability_guard.py` implements a full delegated-capability model for manager-role access (`require_capability("financial")`), with Phase 1023 fixing a known `is_active` nullable-boolean bug that previously caused silent 403s.

The settlement auth model is layered:
1. Role guard (frozenset check on JWT role)
2. Capability delegation check (DB-backed, manager-only)
3. Checkout-date eligibility gate (`_assert_checkout_eligibility`)

No coverage gaps found.

**Risk:** None.

---

### Issue 4 — Wizard Partial-State Risk (No Saga/Compensation)

**Claimed:** Multi-step wizards (check-in settlement, check-out settlement) write to the DB incrementally with no rollback or compensation mechanism for partial failures.

**Verdict: REAL ISSUE (nuanced)**

**Evidence:**

The checkout settlement wizard is: `start → calculate → deductions → finalize`. Each step is a separate HTTP call writing independently. There is **no saga coordinator, no distributed transaction, no compensation path, and no rollback endpoint**. A grep across `src/api/` confirms zero uses of `rollback`, `compensat`, `saga`, or `transaction`.

**Mitigating factors that reduce actual blast radius:**
- `finalize` is terminal and protected by status guards
- The `void` endpoint exists for admin to undo non-finalized settlements
- `calculate` is idempotent — it upserts the electricity deduction row

**Critical tail case:** If `finalize` writes to `booking_settlement_records` successfully but the `cash_deposits` status update fails, the settlement record says `finalized` while the deposit record says `collected`. This cross-table partial failure has **no automatic detection or recovery path**.

**Risk:** Medium — operational integrity risk in the finalize→deposit cross-table tail scenario.

**Fix phase:** 1057

---

### Issue 5 — Cancellation Scope Gap (Active Tasks Not Canceled)

**Claimed:** Booking cancellation only cancels `PENDING` tasks, leaving `ACKNOWLEDGED` and `IN_PROGRESS` tasks orphaned.

**Verdict: REAL ISSUE**

**Evidence (`src/tasks/task_writer.py`, `cancel_tasks_for_booking_canceled`, line 296):**

```python
.eq("status", TaskStatus.PENDING.value)  # PENDING only
```

The docstring explicitly states this is intentional. The audit question is whether this intent holds up operationally.

**Problem:** When a booking is canceled — especially via OTA webhook (e.g., Booking.com cancels 2 days before check-in) — any task a worker has already `ACKNOWLEDGED` or started (`IN_PROGRESS`) will **not** be automatically canceled. The worker sees an active task for a canceled booking with no system-driven signal to stop.

The system has no mechanism to:
- Notify the worker that their active task's booking was canceled
- Mark ACKNOWLEDGED tasks CANCELED with reason
- Alert an ops manager that cleanup is needed

**Risk:** Medium — operational visibility risk.

**Fix phase:** 1055

---

### Issue 6 — Documentation Drift

**Claimed:** System documentation (system map, API surface list, architecture docs) is materially behind the current codebase.

**Verdict: REAL ISSUE**

**Evidence:**

`live-system.md` states at the top: **"Last updated: Phase 1033"**. The current phase is 1053 — **20 phases of drift**.

Missing systems in `live-system.md` (confirmed present in codebase):
- Check-in Settlement (`checkin_settlement_router.py`) — Phases 955–957
- Checkout Settlement (`checkout_settlement_router.py`) — Phases 959–967, 993, 998, 1001
- Deposit Settlement (`deposit_settlement_router.py`)
- Self Check-in Admin Router (`self_checkin_router.py`) — Phase 1012
- Guest Messaging system — Phases 1048–1053
- Host Identity Block — Phase 1047B
- DB tables absent: `electricity_meter_readings`, `property_charge_rules`, `cash_deposits`, `deposit_deductions`, `booking_settlement_records`

The endpoint table **does** list `POST /bookings/{id}/checkin` and `/checkout` under Phase 398, but the settlement engine (the operational heart of check-in/out) is completely absent.

**Risk:** Medium — onboarding risk, future audit risk, planning accuracy risk. Does not affect runtime behavior.

**Fix phase:** 1054

---

## Summary Table

| # | Issue | Verdict | Risk | Fix Phase |
|---|-------|---------|------|-----------|
| 1 | Check-in/out write-gate bypass | **Real** | High | 1056 |
| 2 | Deposit dual-recording risk | **Not Real** | None | — |
| 3 | Settlement auth gaps | **Not Real** | None | — |
| 4 | Wizard partial-state (no saga) | **Real** (nuanced) | Medium | 1057 |
| 5 | Cancellation scope gap | **Real** | Medium | 1055 |
| 6 | Documentation drift | **Real** | Medium | 1054 |

---

## Fix Phase Definitions

### Phase 1054 — Documentation Reconciliation Pass
**Status:** PLANNED  
**Scope:** Update `live-system.md` to reflect all routers, tables, and subsystems added in Phases 1034–1053.
- Add Settlement Engine section (checkin-settlement, checkout-settlement, deposit-settlement)
- Add Self Check-in system section
- Add Guest Messaging section
- Add Host Identity section
- Add new DB tables to architecture overview
- Update "Last updated" timestamp

No code changes. Docs only.

---

### Phase 1055 — Task Cancellation Scope Hardening
**Status:** PLANNED  
**Scope:** Update `cancel_tasks_for_booking_canceled` in `task_writer.py` to also cancel `ACKNOWLEDGED` tasks.

Proposed behavior:
- `PENDING` → CANCELED (existing, unchanged)
- `ACKNOWLEDGED` → CANCELED with reason `"Booking canceled (acknowledged task)"` (new)
- `IN_PROGRESS` → emit `BOOKING_CANCELED_TASK_ACTIVE` warning log; do NOT auto-cancel; notify ops channel

Rationale for IN_PROGRESS exclusion: auto-canceling a task a worker is physically executing creates an operational hazard. Log + alert is the correct model.

---

### Phase 1056 — Write-Gate Alignment (Check-in/Check-out)
**Status:** PLANNED  
**Scope:** Migrate `booking_checkin_router.py` to route state transitions through `apply_envelope`.

Two options:
1. **Full migration** — wrap as canonical `BOOKING_CHECKED_IN` / `BOOKING_CHECKED_OUT` envelopes, route through `CoreExecutor`. Architecturally correct, highest effort.
2. **Intermediate gate** — add idempotency key + structured event record before the direct write. Lower effort, partial auditability.

Decision: Option 1 is the canonical correct path per the architecture invariant. Phase 1056 should execute Option 1, or formally defer and document the exception in BOOT.md.

---

### Phase 1057 — Settlement Finalize Atomicity Hardening
**Status:** PLANNED  
**Scope:** Harden the `finalize` endpoint cross-table write in `checkout_settlement_router.py`.

Proposed mechanism:
1. Write optimistically to `booking_settlement_records` (finalized)
2. If `cash_deposits` update fails, **revert settlement to `calculated`** with error flag
3. Surface `SETTLEMENT_FINALIZE_PARTIAL` error code to caller
4. Add recovery endpoint: `POST /admin/bookings/{id}/settlement/repair-deposit-status`

This is a targeted compensation for the specific cross-table write, not a full saga pattern.

---

## Audit Invariants Confirmed Correct

| Invariant | Confirmed |
|-----------|-----------|
| `cash_deposits` is the single source of truth for deposit state | Yes |
| Settlement routers never write to `booking_financial_facts` | Yes |
| `checkout_settlement_router.py` never writes to `event_log` or `booking_state` | Yes |
| Role guards present on all settlement mutation endpoints | Yes |
| `capability_guard.py` Phase 1023 fix (nullable is_active) applied | Yes |
| `task_writer.py` never writes to `booking_state` or `event_log` | Yes |

---

*End of audit document. Clean and recoverable. No system state changed during this audit pass.*
