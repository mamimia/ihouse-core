# Group A Audit Result: Larry — Chief Orchestrator

**Audit date:** 2026-04-04
**Auditor:** Antigravity (session 627e84a9)

---

## Verdict: PARTIALLY REAL

---

## Evidence Basis

### Dual deposit system (highest claimed risk)

**Status: Partially real — revised down from highest risk.**

Both `checkin_settlement_router.py` (line 331) and `deposit_settlement_router.py` (line 116) write to the same `cash_deposits` table. The original fear of two disconnected tables is **disproven**. Data connects. Checkout settlement finalize updates `cash_deposits` by `booking_id + tenant_id` — same join key.

**Residual real concern:** Deposit IDs in both routers are timestamp-seeded (`sha256("DEP:{booking_id}:{now}")`), not booking-deterministic. There is no `UNIQUE(booking_id, tenant_id)` constraint on `cash_deposits` found in any migration. If both `checkin_settlement_router` (worker path) and `deposit_settlement_router` (admin/financial capability path) were called for the same booking, two deposit records could exist. This is unlikely in normal operations (the manual deposit endpoint requires `require_capability("financial")` — a manager-only gate), but is not technically blocked.

**Root cause of the over-statement:** The memo and evidence file read two INSERTs to the same table and elevated the risk based on the assumption of different tables. Same-table dual-write is a significantly smaller problem.

### SYSTEM_MAP staleness

**Status: Proven and real.** `live-system.md` was last updated at Phase 1033; current is Phase 1053. Settlement engine, self check-in portal, guest messaging, and five core DB tables are absent. This was confirmed independently and is being addressed under Phase 1054 (Documentation Reconciliation).

### Router ordering dependency (134 routers)

**Status: Confirmed.** The financial router ordering constraint is real and documented in `main.py` comments. Risk is forward-looking (next addition that violates order), not a current breakage.

### Task automation depends on upstream events

**Status: Confirmed with mitigation.** DLQ sweep exists (10-minute cycle). Pre-arrival scanner provides a secondary trigger for bookings already in `booking_state`. A webhook lost before `booking_state` is written creates a gap with no recovery path until DLQ replay succeeds.

---

## Fix Needed

**No canonical fix triggered by this audit item.**

The dual-deposit dual-recording concern is a schema hygiene item (missing UNIQUE constraint), not an active data integrity failure. Fixing it would require a migration to add `UNIQUE(booking_id, tenant_id, status='collected')` or a composite guard. This is not an urgent production risk given the capability gate on the manual path.

SYSTEM_MAP staleness is being resolved by Phase 1054.

---

## If Fixed, What Changed

N/A — no fix implemented in this pass.

---

## Why Not Fixed

- Dual deposit risk: Not an active failure. Residual risk is low given the `require_capability("financial")` gate on the manual deposit path. A constraint migration is a Phase 1058+ candidate, not an emergency.
- SYSTEM_MAP: Phase 1054 is the correct venue and has already been planned.
- Router ordering: Forward-looking risk only. No current breakage.
