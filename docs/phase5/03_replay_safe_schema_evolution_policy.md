# iHouse Core Phase 5
## 03 Replay Safe Schema Evolution Policy

Status: Draft
Scope: Database migrations and projection storage

---

## Core Principle

Schema may evolve.
Event log must remain valid forever.

Replay must succeed:
- Before migration
- After migration
- Across mixed event versions

If replay breaks, migration is invalid.

---

## Migration Classification

Every migration must be classified as one of:

A. Additive
B. Transformative
C. Structural Rewrite

---

### A. Additive Migration

Safe by default.

Examples:
- Add nullable column
- Add index
- Add new projection table
- Add optional field

Rules:
1. Must not require rewriting historical data.
2. Must not assume presence of new fields in old events.
3. Must preserve projection determinism.

No replay risk if rules followed.

---

### B. Transformative Migration

Changes projection structure but not event meaning.

Examples:
- Split one projection table into two
- Rename projection column
- Change index strategy

Rules:
1. Full rebuild required after migration.
2. Rebuild must pass validate_rebuild.
3. Fingerprints must match across double replay.
4. Old events must upcast successfully.

Deployment blocked if mismatch detected.

---

### C. Structural Rewrite

High risk.
Requires formal approval.

Examples:
- Changing primary keys of projection tables
- Changing uniqueness constraints that affect rebuild
- Changing projection identity logic

Rules:
1. Must provide deterministic rebuild proof.
2. Must provide replay comparison test.
3. Must document invariants explicitly.
4. Must include rollback strategy.

---

## Forbidden Migration Patterns

1. Deleting columns that historical projections depend on.
2. Adding NOT NULL columns without default.
3. Requiring manual data backfill before replay.
4. Changing semantics of existing projection logic without version bump.
5. Using wall clock time inside projections.

Any of the above invalidates migration.

---

## Replay Safety Invariant

For any migration M:

Let P_before = projection fingerprint before migration  
Let P_after  = projection fingerprint after migration and rebuild  

Invariant:
P_before == P_after

If false:
Migration is rejected.

---

## Migration Checklist

Before merge:

[ ] Event version changes reviewed  
[ ] Upcasters implemented  
[ ] Full rebuild executed  
[ ] validate_rebuild passes  
[ ] Fingerprints identical  
[ ] Smoke suite passes  
[ ] Rollback documented  

---

## Schema Version Tracking

Each event meta_json includes:

schema_version_at_write

This is diagnostic only.
Replay must never branch on schema version.

Schema version is for:
- Audit
- Observability
- Forensics

Not for logic.

---

This policy locks schema evolution into replay-safe discipline.
