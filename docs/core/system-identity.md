# iHouse Core – System Identity

## Phase
Current:
Phase 16C – Hard Idempotency Gate

Last closed:
Phase 16B – Deterministic Core Alignment

---

## System Type

Deterministic Domain Event Execution Kernel.

Not skill-driven.
Not function-triggered.
Not execution-primitive-based.

All execution originates from canonical business events.

---

## Event Authority

Only canonical business events allowed externally.

Internal handlers are implementation details.

Unknown event types cause hard rejection.

---

## Persistence Authority

Supabase is the single source of truth.

SQLite not allowed in production runtime.

---

## Financial-Grade Direction

System moving toward financial-grade guarantees:

- Hard idempotency
- Atomic envelope gate
- Deterministic replay
- Strict concurrency enforcement

