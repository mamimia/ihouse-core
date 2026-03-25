# Canonical Rule: Staffing → Future Task Assignment

> **Status: LOCKED**  
> **Phase: 888**  
> **Approved: 2026-03-26**  
> **Scope: All worker roles, all properties, all tenants**

---

## Rule Definition

When a staff member's property assignment changes, the system automatically
adjusts **future PENDING tasks** on that property to reflect the current staffing truth.

### 1. State Safety Boundary

| Task Status | Auto-mutated by staffing changes? |
|---|---|
| **PENDING** | ✅ Yes |
| **ACKNOWLEDGED** | ❌ Never |
| **IN_PROGRESS** | ❌ Never |
| **COMPLETED** | ❌ Never |
| **CANCELED** | ❌ Never |

**Rationale**: ACKNOWLEDGED and beyond represent active human commitments.
Automatically reassigning them would override decisions already made by workers
or operators. Those require explicit human action.

### 2. Assignment Scenarios

#### New Assignment
When a worker is assigned to a property:
- All **future PENDING** tasks on that property where:
  - `worker_role` matches the worker's roles
  - `assigned_to IS NULL` (unassigned)
  - `due_date >= today`
- Are updated: `assigned_to = {worker_user_id}`

#### Removal (No Replacement)
When a worker is removed from a property:
- All **future PENDING** tasks on that property where:
  - `assigned_to = {removed_worker_user_id}`
  - `due_date >= today`
- Are updated: `assigned_to = NULL` (becomes UNASSIGNED)
- These tasks become visible as unassigned for follow-up or escalation.

#### Replacement (A → B)
When worker A is removed and worker B is assigned:
- Step 1 (remove A): Future PENDING tasks assigned to A → cleared to NULL
- Step 2 (assign B): Future PENDING tasks with NULL → assigned to B
- **Net result**: Tasks move from A → B with no stale or ambiguous intermediate state.

### 3. Role Coverage

The rule applies identically across all worker role types:

| UI Role Value | Task System Roles Matched |
|---|---|
| `cleaner` | `CLEANER` |
| `checkin` | `CHECKIN`, `PROPERTY_MANAGER` |
| `checkout` | `CHECKOUT`, `INSPECTOR` |
| `maintenance` | `MAINTENANCE`, `MAINTENANCE_TECH` |

#### Combined Check-in/Check-out

> **"Combined" is NOT a separate role value.**

A worker holding both `checkin` and `checkout` in their `worker_roles` array
is a **dual-role worker**. The backfill processes each role independently:

```
worker_roles: ["checkin", "checkout"]
→ matches: CHECKIN, PROPERTY_MANAGER, CHECKOUT, INSPECTOR
→ backfills both CHECKIN_PREP and CHECKOUT_VERIFY tasks
```

There is no `"combined"` or `"checkin_checkout"` enum value in the system.

### 4. Implementation Location

| Component | File |
|---|---|
| Backfill on assign | `_backfill_tasks_on_assign()` in `permissions_router.py` |
| Clear on unassign | `_clear_tasks_on_unassign()` in `permissions_router.py` |
| Role mapping | `_ROLE_TO_TASK_ROLES` dict in `permissions_router.py` |
| Triggered by | `POST /staff/assignments` and `DELETE /staff/assignments/{user_id}/{property_id}` |
| Generation-time assign | `write_tasks_for_booking_created()` in `task_writer.py` |

### 5. Invariants

1. **Only PENDING tasks with future due dates are ever auto-mutated**
2. **ACKNOWLEDGED+ tasks are NEVER touched by staffing changes**
3. **Behavior is identical across all roles** — no role-specific exceptions
4. **Backfill is best-effort** — if it fails, the assignment itself still succeeds
   (failure is logged but does not block the staffing change)
5. **Audit events are written** for both backfill and clear operations

### 6. What This Rule Does NOT Cover

- Manual task reassignment by an admin (separate feature, not part of this rule)
- Notification to workers when their tasks change (future enhancement)
- Conflict resolution when multiple workers of the same role are assigned to the
  same property (current behavior: first match wins, deterministic by query order)
- Retroactive repair of past tasks (only future tasks are affected)

---

> **This rule is formally locked as of 2026-03-26.**  
> **Do not modify without explicit product decision.**
