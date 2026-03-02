# iHouse Core – Construction Log

## Phase 16
Canonical Domain Event Migration (Big Bang)

System migrated from execution-primitive-based events
to canonical business domain events.

All event types redefined.
Skills demoted to internal handlers.
Supabase declared single source of truth.
SQLite forbidden in production runtime.
Deterministic rebuild hash required for closure.

---

## Phase Completion Protocol (Mandatory)

A Phase is not considered complete unless all of the following are executed:

1. Update vision.md if system identity changed.
2. Update system-identity.md if architecture changed.
3. Update live-system.md if runtime flow changed.
4. Update current-snapshot.md with exact system state.
5. Update construction-log.md with phase summary.
6. Update canonical-event-architecture.md if event contract changed.
7. Create a full project backup before structural modification.
8. Declare Phase officially closed.

No architectural modification is allowed without synchronized documentation update.

---

## Phase Context Load Rule

When starting a new chat session:

Type:

PHASE_CONTEXT_LOAD

Then load:

docs/core/current-snapshot.md
docs/core/system-identity.md
docs/core/canonical-event-architecture.md

This guarantees deterministic context alignment.

Drift is considered architectural violation.
