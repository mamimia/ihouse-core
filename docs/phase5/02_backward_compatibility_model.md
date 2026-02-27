# iHouse Core Phase 5
## 02 Backward Compatibility Model

Status: Draft
Scope: Event processing and replay layer

### Core Principle

Backward compatibility means:

Any historical event ever written to the event log
must remain replayable
under any future schema version
without manual intervention.

Replay safety is mandatory.

---

## Compatibility Contract

For every event_type:

1. All historical versions must be upcastable to canonical version.
2. Upcasting must be deterministic.
3. Rebuild must succeed across:
   - Old DB schema
   - New DB schema
   - Mixed historical event versions

---

## Compatibility Matrix

For each event_type:

| Event Version | Canonical Version | Requires Upcaster | Replay Allowed |
|---------------|------------------|-------------------|----------------|
| v1            | v3               | Yes               | Yes            |
| v2            | v3               | Yes               | Yes            |
| v3            | v3               | No                | Yes            |

Rules:

1. event_version must always be less or equal to canonical version.
2. Any version gap must be resolved by chained upcasters.
3. Missing upcaster is a deployment blocker.

---

## Breaking Change Definition

A change is considered breaking if:

1. It changes meaning of a field.
2. It removes a required field.
3. It changes type of a required field.
4. It changes implicit behavior.

Breaking changes require:

New event_version  
Upcaster implementation  
Replay test fixture  

---

## Non Breaking Changes

Allowed without version bump:

1. Adding optional payload fields.
2. Adding metadata fields.
3. Adding projection only fields.
4. Adding indexes.
5. Adding nullable DB columns.

Even when version bump is not required,
projection logic must remain replay safe.

---

## Replay Invariance Rule

Given:

Replay(A historical log)
Replay(A historical log after schema migration)

The final projection fingerprints must be identical.

If not identical:

Migration is invalid.

---

## Deployment Gate

Before merging a migration:

1. Replay full event log in staging.
2. Run validate_rebuild twice.
3. Verify fingerprint equality.
4. Run smoke suite.
5. Verify no missing upcasters.

Deployment blocked on failure.

---

## Event Immutability Law

Events are append only.
Events are never edited.
Events are never reinterpreted.

Schema evolves.
Events do not.

---

This document defines compatibility guarantees required for production SaaS reliability.
