# Phase 1031 — Task Assignment Lifecycle: Source-of-Truth Hardening

**Status:** IN PROGRESS  
**Branch:** `checkpoint/supabase-single-write-20260305-1747`  
**Commit at open:** `374b57c`  
**Commit at code-closure:** `b5f5e8f`

---

## Scope

Narrow: close the remaining source-of-truth code gaps in the Primary/Backup model, then run one bundled proof pass. No new UI work.

---

## Code Fixes — BUILT ✅

### Fix 1 — Early-checkout healing priority walk (`early_checkout_router.py`)

**Bug (pre-fix):** `_reschedule_cleaning_task` iterates over `roles_res.data` (arbitrary DB order) to find the first cleaner, instead of walking the already-priority-ordered `candidate_ids` list.

**Fixed:** Build a `roles_map` from `roles_res.data`, then walk `candidate_ids` in priority order. Guarantees Primary cleaner is always selected first.

**Status:** BUILT ✅ | 124 tests pass

---

### Fix 2 — Backfill: Primary-existence guard (`permissions_router.py`)

**Bug (pre-fix):** `_backfill_tasks_on_assign` assigns all NULL future tasks to the newly added worker — even if the new worker is a Backup and a Primary already exists for the same lane. The Backup would steal NULL tasks that belong to the Primary path.

**Fixed:** Before backfilling, check the new worker's priority. If priority ≠ 1, query for an existing priority=1 worker on the same property. If a Primary exists for a matching lane, skip backfill entirely. Return `{"reason": "primary_exists_for_lane"}`. The NULL tasks remain unassigned and will be claimed by the Primary path (booking creation, amendment, ad-hoc creation all use `ORDER BY priority ASC`).

**Guard failure mode:** If the guard itself fails (DB exception), log a WARNING and allow backfill to proceed — do not silently orphan tasks.

**Status:** BUILT ✅ | 124 tests pass

---

### Fix 3 — Ownerless task guard: explicit error token (`task_writer.py`)

**Bug (pre-fix):** Two silent failure modes:
1. If the Primary lookup returns no results → task written with `assigned_to=NULL`, emits generic WARNING.
2. If the entire auto-assign block throws → tasks written with `assigned_to=NULL`, emits generic WARNING.

**Fixed:**
- Both paths now emit **`ERROR`-level** log with token `OWNERLESS_TASK_CREATED`.
- Token includes: `task_id`, `kind`, `role`, `property_id`, `booking_id`.
- Tasks are still written (not dropped) — operational continuity is maintained.
- Ops can grep for `OWNERLESS_TASK_CREATED` to find all unassigned task creation events immediately.

**Status:** BUILT ✅ | 124 tests pass

---

## Amendment Healing — OPEN (documented)

**Current behavior:** Healing only repairs tasks where `assigned_to IS NULL`. If a task is misassigned (assigned to a worker who no longer covers the property), it will not be healed.

**Risk level:** Low. This edge case requires: (1) a rescheduled booking, (2) where the original assigned worker was removed from the property. This is an uncommon operational sequence.

**Decision:** OPEN — document as a known gap. Not safe to silently heal already-assigned tasks without additional safeguards (e.g., checking whether the assigned worker is still active on the property). Defer to a dedicated Phase 1032+ targeted fix.

---

## Priority Renormalization After Baton Transfer — HYGIENE

**Observation:** After removing Primary (priority=1), the promoted Backup (priority=2) becomes new Primary, but other workers remain at priority=3+. The stack numbering is non-contiguous.

**Impact:** None on actual selection behavior. All queries use `ORDER BY priority ASC` and select the minimum — the absolute values do not matter, only the relative order.

**Verdict:** HYGIENE only. Not a blocking functional bug. No fix required.

---

## Bundled Proof Targets

| # | Proof | Method | Status |
|---|-------|--------|--------|
| 1 | Baton-transfer E2E | Remove Primary → DB check PENDING tasks moved to Backup | PENDING PROOF |
| 2 | Promotion banner | DB check `comm_preference._promotion_notice` written | PENDING PROOF |
| 3 | Backfill E2E | POST /staff/assignments → DB check NULL tasks assigned | PENDING PROOF |
| 4 | Amendment healing | Reschedule booking → DB check CLEANING task assigned to Primary | PENDING PROOF |
| 5 | Ad-hoc cleaning | POST /tasks/adhoc → DB check Primary selected (priority=1) | PENDING PROOF |

---

## Invariants Locked

- **INV-1010:** Booking must have exactly one active CLEANING task per checkout date.
- **INV-1011:** Amendment reschedule healing covers unassigned tasks only (OPEN for misassigned).
- **INV-1012:** Lane-aware baton transfer. Primary removal triggers Backup promotion only within same worker_role lane.
- **INV-1031-A:** Backfill does not assign Backup when Primary already covers the lane.
- **INV-1031-B:** OWNERLESS_TASK_CREATED emitted on any NULL-assigned task creation path.
- **INV-1031-C:** Early-checkout healing always selects minimum-priority cleaner first.
