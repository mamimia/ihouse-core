# iHouse Core – Construction Log

## Phase 16
Canonical Domain Event Migration

System migrated from execution-primitive-based events
to canonical business domain events.

Supabase declared single source of truth.
SQLite forbidden in production runtime.

---

### Phase 16A – Canonical Schema Lock (Closed)

DB schema locked to canonical at database level.

Completed:
- event_kind ENUM enforced
- event_log.kind converted to enum
- Legacy indexes removed
- booking_state.last_event_id exists
- FK to event_log(event_id) enforced
- Concurrency enforced via expected_last_event_id

Outcome:
Database layer canonical and constrained.

---

### Phase 16B – Deterministic Core Alignment (Closed)

Completed:
- Canonical routing registry active
- Unknown event types rejected
- Internal handlers aligned
- Supabase enforced runtime mode
- Enum values synchronized with runtime
- Deterministic execution flow validated

Remaining limitation discovered:
Idempotency occurs after initial envelope write.

---

### Phase 16C – Hard Idempotency Gate (Open)

Goal:
Financial-grade enforcement of envelope idempotency.

Requirements:
- Unique constraint or upsert on envelope_id
- No duplicate envelope_received writes
- Idempotency validated before event_log mutation
- Atomic write gate

Phase 16 not considered financially complete until Phase 16C closes.

