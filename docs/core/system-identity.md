# iHouse Core – System Identity

## Phase
Phase 16 – Canonical Domain Event Migration

---

## System Type

Deterministic Domain Event Execution Kernel.

Not skill-driven.
Not function-triggered.
Not execution-primitive-based.

All execution originates from canonical business events.

---

## Event Model

External contract accepts only canonical domain events.

Internal handlers are implementation details.

Event types represent business transitions only.

Technical orchestration is never exposed as an event type.

---

## Canonical Event Authority

Only events defined in the canonical registry are allowed.

Event types must be:

- SCREAMING_SNAKE_CASE
- Unique
- Business meaningful

Any unknown event type causes hard runtime rejection.

---

## Execution Model

Canonical Event
→ Domain Dispatcher
→ Internal Handlers
→ Deterministic State Commit
→ Supabase Event Log

---

## Persistence

Supabase is the single source of truth.

SQLite is no longer allowed in production runtime.

Startup fails if DB_ADAPTER != supabase in production mode.

---

## Replay

Rebuild must derive identical state from:

Supabase public.event_log only.

Deterministic state hash validation required for Phase 16 closure.

---

## Structural Rule

Code and identity must evolve together.

Any architectural change requires synchronized documentation update.
