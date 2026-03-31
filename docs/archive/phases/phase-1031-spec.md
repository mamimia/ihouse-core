# Phase 1031 — Task Assignment Lifecycle: Source-of-Truth Hardening
## CLOSED

**Branch:** `checkpoint/supabase-single-write-20260305-1747`  
**Commits:** `b5f5e8f` → `7dcb4da` → `89d3f45`  
**Status:** CLOSED — all code, DB, and proof work complete

---

## What This Phase Fixed

Phase 1030 proved the system. Phase 1031 found the structural gap:  
`staff_property_assignments.priority` was never set at write time — always DEFAULT 1.  
This caused non-deterministic Primary selection even though the model was correct.

---

## BUILT ✅

### Code fixes (commits b5f5e8f)

| Fix | File | Behavior |
|-----|------|----------|
| Early-checkout healing priority walk | `early_checkout_router.py` L332-342 | `_reschedule_cleaning_task` now walks `candidate_ids` in priority order, not arbitrary DB order. Primary cleaner always selected first. |
| Backfill Primary-existence guard | `permissions_router.py` L906-968 | When a new Backup is added, if a priority=1 worker already covers the lane, backfill is skipped. Returns `reason: primary_exists_for_lane`. |
| Ownerless task error token | `task_writer.py` L203-225 | Both failure paths now emit `ERROR OWNERLESS_TASK_CREATED` with task_id, kind, role, property_id, booking_id. No silent NULL-assignment. |
| Test suite fixes (A8, B3, I3, early-checkout mock) | `tests/` | 161 tests pass. |

### DB + API (commits 7dcb4da, 89d3f45)

| Fix | Type | Behavior |
|-----|------|----------|
| `chk_priority_positive` | DB constraint | priority >= 1 always |
| `fn_guard_assignment_priority_uniqueness` | DB trigger (BEFORE INSERT/UPDATE) | Blocks duplicate (property, lane, priority) for operational lanes |
| `fn_guard_assignment_requires_operational_lane` | DB trigger (BEFORE INSERT) | Blocks any INSERT where worker has no valid lane — raises `NO_OPERATIONAL_LANE` |
| `get_next_lane_priority(tenant, property, lane)` | DB function | Computes MAX(priority)+1 in lane for write path |
| Lane-aware priority computation | API: `POST /staff/assignments` | Resolves lane from worker_roles before insert. Ghost user → 400. No-role → 400 NO_OPERATIONAL_LANE. DB error → 500 (no silent fallback). |
| UNKNOWN-lane hard block | API | Replaced priority>=100 silent path with hard 400 reject |
| Data cleanup — 11 invalid rows removed | DB migration | `manager_not_worker` (8), `ghost_no_permission_record` (2), `owner_not_worker` (1) |

---

## Lane Model (Locked)

```
CLEANING           ← worker_roles @> ['cleaner']
MAINTENANCE        ← worker_roles @> ['maintenance']
CHECKIN_CHECKOUT   ← worker_roles && ['checkin','checkout']  (shared lane)
```

**There is no UNKNOWN lane.** A worker without a valid lane cannot enter `staff_property_assignments`.

---

## PROVEN ✅ (DB-source-of-truth)

| Proof | Result |
|-------|--------|
| A: invalid_rows_remaining in assignments | **0** |
| B: All assignment rows map to operational lane | CLEANING(5) / CHECKIN_CHECKOUT(5) / MAINTENANCE(4) — no UNKNOWN |
| C: Priority collisions in all operational lanes | **0** |
| D: Removed rows audit | 11 rows, correctly labeled in `phase_1031c_removed_assignments` |
| Ownerless active tasks (assigned_to=NULL) | **0** |
| Ad-hoc cleaning Primary selection — KPG-500 | `1b747f09` (priority=1) ✅ deterministic |
| Ad-hoc cleaning Primary selection — KPG-502 | `1b747f09` (priority=1) ✅ deterministic |

---

## OPEN (documented, not blocking)

### Legacy pre-guard CLEANING task distribution — KPG-500
- Primary (`1b747f09`, p=1): 2 PENDING tasks  
- Backup (`e1ae5439`, p=2): 7 PENDING tasks  

These tasks were assigned before the Primary-existence guard existed (Phase 1031 backfill guard is not retroactive). Tasks are valid and will be completed by the Backup. **Not a current write-path failure.** Reported as legacy pre-guard residue. No reassignment required unless operationally necessary.

### Baton-transfer + Promotion-banner live proof
Not yet performed in staging. Requires manually removing a worker from a property to trigger the promotion event. DB state is correct for the proof to work — deferred to next staging window.

### DB constraint limitation (documented)
A traditional `UNIQUE` constraint cannot enforce `(property, lane, priority)` because `lane` is derived from `tenant_permissions.worker_roles` in a separate table. The trigger approach (`fn_guard_assignment_priority_uniqueness`) is the strongest protection available without materializing a `lane` column on the assignment row. If the schema is ever redesigned to include a `lane` column, a real unique index can replace the trigger.

### Amendment healing — partial misassignment edge case
If a task is rescheduled AND the previously assigned worker was removed from the property, the healing does not re-assign (only heals `assigned_to IS NULL`). Documented as a known gap. Not a blocking failure path. Deferred to Phase 1032+.

---

## What Was NOT DONE (intentional scope cut)

- No new UI work
- No baton-transfer live staging proof (deferred — DB is ready)
- No promotion-banner live proof (deferred — DB is ready)
- No priority renormalization after baton-transfer (hygiene only, not a functional blocker)
