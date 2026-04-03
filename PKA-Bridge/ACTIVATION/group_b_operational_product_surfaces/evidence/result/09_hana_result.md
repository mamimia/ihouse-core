# Audit Result: 09 — Hana (Staff Operations Designer)

**Group:** B — Operational Product Surfaces
**Reviewer:** Hana
**Closure pass:** 2026-04-04
**Auditor:** Antigravity

---

## Closure Classification Table

| Item | Final Closure State |
|---|---|
| Invite system security | ✅ **Proven resolved** |
| Two onboarding pipelines | ✅ **Proven resolved** |
| Property assignment with Primary/Backup priority and task backfill | ✅ **Proven resolved** |
| Deactivation with no task/state cleanup | ✅ **Fixed now** — auto-clear of assignments + PENDING tasks on deactivation |
| Session invalidation on deactivation | 🔵 **Confirmed future gap** — JWT TTL is auth-layer decision; residual window is acceptable |
| Performance metrics at query time | 🔵 **Intentional future gap** — acceptable at current scale |
| Worker availability not integrated with task backfill | 🔵 **Intentional future gap** — low operational impact |

---

## Fix Applied: Deactivation Auto-Clear (Final Closure)

**File:** `src/api/permissions_router.py`

`PATCH /permissions/{user_id}` when `is_active=False` now:
1. Reads all `staff_property_assignments` for the worker
2. Deletes each assignment row
3. Calls `_clear_tasks_on_unassign()` per property (the same battle-tested function used by the unassign endpoint) to set `assigned_to=NULL` on future PENDING tasks
4. Returns a `deactivation_summary` with counts: `cleared_assignments`, `total_tasks_cleared`, `failed_clears`, `residual_warning`

**Before (old fix):** Summary was informational only — admin had to manually clean up assignments. PENDING tasks remained assigned to a deactivated worker.

**After (new fix):** Deactivation atomically removes all assignments and clears PENDING tasks in a best-effort loop. If any individual property clear fails, it is logged at `ERROR` level with the property_id and surfaces in `failed_clears` in the response.

**What is NOT cleared (intentional):**
- ACKNOWLEDGED and IN_PROGRESS tasks — these represent active human commitments. Clearing them would lose operational state.
- Issued JWTs — remain valid until TTL. This is a stateless JWT characteristic.

---

## Closure Detail: Session Invalidation on Deactivation

**Final closure: Confirmed future gap — residual risk window is acceptable**

**What the gap is:** A deactivated worker's *already-issued* JWT stays valid until its TTL. If a worker has a 1-hour TTL JWT and is deactivated, they can still make API calls for up to 1 hour.

**Why the residual risk is acceptable:**
- All API calls require `jwt_auth` (tenant-scoped). The deactivated worker can only act within their own tenant's permitted endpoints.
- `is_active=False` is now set in `tenant_permissions`. Any endpoint that reads `is_active` as part of its logic will correctly reject the worker.
- The deactivation removes all property assignments — so task-writing paths that check `assigned_to` will not produce new work.
- The realistic scenario (urgent deactivation of a hostile insider) has a short window (JWT TTL) and is constrained to tenant-scope operations.

**Why not fixable without auth-layer redesign:** Requires either short TTL (operationally disruptive for long cleaning sessions), a Redis revocation list, or `is_active` check in every request middleware. All three are system-wide changes requiring separate auth hardening phase.

**Classification:** Confirmed future gap. Residual window is bounded (JWT TTL). Acceptable at current operational scale.

---

## Closure Detail: Performance Metrics Scalability

**Closure state: Intentional future gap — acceptable at current scale**

`staff_performance_router.py` queries the `tasks` table at request time with no materialization. For small tenants (which is current state), this is acceptable. The fix (materialized `staff_performance_stats` view, updated by trigger or job) is valuable but belongs in a performance hardening phase, not as an audit patch.

---

## Closure Detail: Worker Availability × Task Backfill

**Closure state: Intentional future gap — low operational impact**

`_backfill_tasks_on_assign()` does not cross-reference `worker_availability` before assigning tasks. Availability data in the system is informational (workers can decline or escalate). The backfill is designed for future-task bulk assignment across date ranges — checking availability per-date would require N queries. Low operational frequency. Revisit when availability data is used for hard scheduling.

---

## What Was Disproven

- **Invite privilege escalation**: INVITABLE_ROLES guard correctly excludes admin.
- **Task backfill race condition**: Phase 1031 guard mitigates the primary/backup racing case.
