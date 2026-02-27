# iHouse Core Phase 5
## 04 Cross Version Rebuild Guarantees

Status: Draft
Scope: Deterministic rebuild across schema upgrades

---

## Core Guarantee

For any historical event log L:

Rebuild(L) under schema version S1
must produce the same canonical projection state as
Rebuild(L) under schema version S2

Provided that:
- All required upcasters exist
- Migration policy was followed

---

## Definitions

Historical Log:
Any prefix of the event log at any time in history.

Schema Version:
Database structure at a specific migration level.

Canonical Projection State:
The full projection dataset reduced to a deterministic fingerprint.

Fingerprint:
Stable hash derived from ordered projection rows.

---

## Invariant

For any log L and schema versions S_old, S_new:

Fingerprint(
    Rebuild(L, S_old)
) 
==
Fingerprint(
    Rebuild(L, S_new)
)

If false:
Schema evolution violated replay safety.

---

## Rebuild Execution Model

Rebuild must:

1. Clear all projections
2. Read events ordered by row_id ASC
3. Upcast each event to canonical version
4. Apply deterministic projection logic
5. Never branch on schema version
6. Never branch on wall clock time

---

## Cross-Version Test Strategy

For every non-additive migration:

1. Snapshot current production log L
2. Rebuild under old schema → capture fingerprint F_old
3. Apply migration
4. Rebuild under new schema → capture fingerprint F_new
5. Assert F_old == F_new

Mandatory in staging before deploy.

---

## Projection Logic Stability

Projection handlers must:

- Be pure functions of canonical event
- Not read from external services
- Not read mutable global state
- Not depend on insertion order beyond row_id ASC

---

## Schema Change That Is Allowed to Change Fingerprint

Only allowed when:

- A formal domain change is introduced
- A new event type defines new behavior
- Old events are not reinterpreted

Even then:
The change must be explicit and documented.

Silent fingerprint drift is forbidden.

---

## Replay Audit Capability

System must support:

- Rebuild at arbitrary schema version
- Compare fingerprints
- Produce diff report of mismatched rows

If diff cannot be explained deterministically:
Migration is invalid.

---

This document guarantees that replay remains invariant across time.
