# Group A Audit Result: Ravi — Service Flow Architect

**Audit date:** 2026-04-04
**Auditor:** Antigravity (session 627e84a9)

---

## Verdict: PARTIALLY REAL

Three of Ravi's concerns are real (no saga pattern, deposit dual-recording possible, CLEANING task amended-booking edge case). One major claim is disproven (property readiness gate). No new canonical fixes were triggered — the confirmed real issues are already captured in Phase 1055 and 1057 planning.

---

## Evidence Basis

### Property readiness gate (biggest claimed gap)

**DISPROVEN — the gate exists.**

`cleaning_task_router.py` lines 816–857 explicitly transition `properties.operational_status` on cleaning completion:
- No open problem reports → `"ready"`
- Open problem reports exist → `"ready_with_issues"`

Full lifecycle confirmed:
```
ready → occupied (check-in) → needs_cleaning (checkout) → ready / ready_with_issues (cleaning completion)
```

The memo stated: "No function transitions property from needs_cleaning to vacant/ready after cleaning task completion." This is **incorrect**. The function exists and is operational.

Caveat: The transition uses a direct column write inside a try/except (best-effort). Silent failure would leave the property in `needs_cleaning` with no recovery sweep. But this is a failure-mode concern, not a missing-feature concern.

### CLEANING task deduplication

**CONFIRMED SAFE in normal case.** Two code paths can create a CLEANING task for the same booking:
1. `task_automator.py` on BOOKING_CREATED
2. `booking_checkin_router.py` on checkout

Both use `sha256("CLEANING:{booking_id}:{property_id}")[:16]` as the task ID. Identical inputs → identical ID → on-conflict upsert deduplicates. No duplicate in the normal case.

**Known edge case:** If a booking is amended and the property changes, the original CLEANING task (old property_id) and the checkout CLEANING task (new property_id) produce different task IDs → two CLEANING tasks. The AMENDED handler reschedules PENDING tasks, which should handle the old task. If the task was already ACKNOWLEDGED or IN_PROGRESS, the orphan persists. Low-probability edge case, not a current active bug.

### Deposit lifecycle handoff

**CONFIRMED CONNECTED.** All three routers (`checkin_settlement_router`, `deposit_settlement_router`, `checkout_settlement_router`) use `cash_deposits` with `booking_id + tenant_id` as the join key. The lifecycle is:
```
INSERT (check-in wizard) → [hold period] → UPDATE status (checkout finalize)
```
Data connects. No disconnect between check-in write path and checkout read path.

**Residual dual-recording concern:** Deposit IDs in both router INSERT paths are timestamp-seeded (not booking-deterministic). No `UNIQUE(booking_id, tenant_id)` constraint on `cash_deposits`. If both the check-in wizard (worker) and the manual deposit endpoint (admin/financial capability) were called for the same booking, two rows could exist. In practice this is capability-gated and unlikely, but not technically prevented at the DB level.

### Multi-step wizard — no saga pattern

**CONFIRMED.** Each of the 7 check-in wizard steps writes to its own endpoint independently with no transaction coordinator or compensation mechanism. This is the Phase 1057 planned item (Settlement Finalize Atomicity).

The practical impact is: if step 5 (deposit) fails after steps 1–4 succeed, the booking remains in `active` status, no guest portal token is issued, and the worker must retry manually.

**Mitigation not confirmed:** Whether the frontend wizard supports individual step retry (resuming at step 5) or requires full restart from step 1 was not traced. If step retry works, practical impact is low.

### Self check-in → staffed check-in handoff

**PARTIALLY VERIFIED.** `SELF_CHECKIN_FOLLOWUP` task kind exists in `task_model.py` (Phase 1004). The two-gate architecture is confirmed in `self_checkin_portal_router.py`. The exact trigger logic for creating a SELF_CHECKIN_FOLLOWUP task (timeout? admin action? automatic after gate failure?) was not fully traced. Not confirmed as a gap — mechanism exists, trigger timing unclear.

### Task automation chain

**CONFIRMED ROBUST.** BOOKING_CREATED → 3 tasks (CHECKIN_PREP, CLEANING, CHECKOUT_VERIFY), CANCELED → cancel PENDING, AMENDED → reschedule. Deterministic IDs, on-conflict upsert, Phase 1027a future-only cutoff, Phase 1033 due_times. All confirmed correct.

### SLA escalation chain

**CONFIRMED WELL-STRUCTURED.** `sla_engine.py` evaluates ACK_SLA_BREACH and COMPLETION_SLA_BREACH. Terminal states emit audit-only. CRITICAL_ACK_SLA_MINUTES = 5 (locked Phase 91). Sweep runs every 120 seconds.

---

## Fix Needed

**No new canonical fix triggered in this pass.**

---

## Why Not Fixed

- Property readiness gate: Does not have a gap — gate is implemented.
- Saga pattern gap: Already Phase 1057 in canonical phase timeline.
- Task cancellation scope (ACKNOWLEDGED+): Already Phase 1055.
- Deposit dual-recording: Not an active failure; requires deliberate constraint migration (Phase 1058+ candidate).
- CLEANING task amended edge case: Low-probability, existing dedup mechanism handles the normal case.
