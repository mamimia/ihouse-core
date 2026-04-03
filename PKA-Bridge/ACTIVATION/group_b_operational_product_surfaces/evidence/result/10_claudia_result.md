# Audit Result: 10 — Claudia (Property Readiness Standards Architect)

**Group:** B — Operational Product Surfaces
**Reviewer:** Claudia
**Closure pass:** 2026-04-04
**Auditor:** Antigravity

---

## Closure Classification Table

| Item | Closure State |
|---|---|
| Readiness gate (operational_status transition) | ✅ **Proven resolved** — confirmed complete and correct |
| Full operational_status lifecycle | ✅ **Proven resolved** — confirmed correct across all paths |
| 3-flag completion gate (items + photos + supplies) | ✅ **Proven resolved** — confirmed correct |
| Template 3-level fallback | ✅ **Proven resolved** — confirmed correct |
| `force_complete` bypasses supply check with no role gate | ✅ **Fixed now** — admin/manager/ops role gate added |
| Post-cleaning status downgrade after new problem reports | ✅ **Fixed now** — downgrade applied on problem report creation |
| Silent property status write failure in `complete_cleaning()` | ✅ **Fixed now** — upgraded from `logger.warning` to `logger.error` with structured context |
| Supply tracking is status-based, not inventory | ✅ **Proven resolved** — confirmed intentional design |

---

## Fix 1: `force_complete` Role Gate

**File:** `src/api/cleaning_task_router.py`

`force_complete=True` now requires the caller to have role `admin`, `manager`, or `ops`. Any caller with a `cleaner` or other non-elevated role who submits `force_complete=True` receives a `403 CAPABILITY_DENIED` response.

```python
_FORCE_COMPLETE_ALLOWED_ROLES: frozenset = frozenset({"admin", "manager", "ops"})

if force:
    # JWT role decoded from Authorization header (unsigned, for role gate only)
    _caller_role = ...
    if _caller_role not in _FORCE_COMPLETE_ALLOWED_ROLES:
        return make_error_response(403, ErrorCode.CAPABILITY_DENIED, ...)
```

**Design note:** The role is decoded from the JWT payload without signature verification (purely for the role gate). This is correct because the JWT itself is already verified at the `jwt_auth` dependency level. The in-handler decode is only used to read the role claim from an already-authenticated token.

`force_complete` was previously available to any authenticated caller. The cleaning wizard UI does not expose this flag, but direct API callers could bypass the supply check. The gate closes this.

---

## Fix 2: Post-Cleaning Status Downgrade After New Problem Reports

**File:** `src/api/problem_report_router.py`

The gap: property set to `'ready'` at cleaning completion. A new problem report filed afterward leaves the property as `'ready'` until the next cleaning cycle.

The fix is in `create_problem_report()`. After writing the problem report and auto-creating the maintenance task, the handler now:
1. Reads the property's current `operational_status`
2. If it is `'ready'`, updates it to `'ready_with_issues'`
3. The update is non-blocking — report creation succeeds even if this update fails

```python
current_status = prop_res.data[0].get("operational_status", "")
if current_status == "ready":
    db.table("properties").update({
        "operational_status": "ready_with_issues",
    }).eq("property_id", property_id).eq("tenant_id", tenant_id).execute()
```

**Why application-level (not DB trigger):** A DB trigger on `problem_reports` INSERT would be the architecturally cleanest solution but requires infrastructure decisions (Supabase PostgreSQL trigger management). The application-level fix achieves the same effect with zero schema changes. It correctly only downgrades from `'ready'` — it does not interfere with other statuses (`occupied`, `needs_cleaning`, `maintenance`).

**Design note:** The response includes `_property_status_downgraded: true` when the downgrade occurs, giving the calling UI a signal to surface a notification.

---

## Fix 3: Silent Property Status Write Failure Visibility

**File:** `src/api/cleaning_task_router.py`

The `except` block that catches property status write failures was logging at `WARNING` level — likely filtered or ignored in production monitoring. Changed to `ERROR` with structured context:

```python
logger.error(
    "complete_cleaning: property state update FAILED for task=%s property=%s: %s. "
    "Task is COMPLETED but property operational_status was NOT updated. "
    "Manual admin correction required.",
    task_id, property_id, prop_exc,
)
```

This does NOT make the failure blocking — the cleaning task still completes successfully. But the error is now clearly surfaced at a log level that ops monitoring should catch, with the task_id and property_id included for easy lookup.

**Why not made atomic/blocking:** Making the status write blocking would cause successful cleaning completions to fail and retry if the Supabase `properties` table write hits a transient error. This would be worse than the current non-blocking design. The correct long-term fix (atomic transaction or reconciliation sweep) is a future architecture item. The log severity upgrade is the right interim mitigation.

---

## What Was Disproven

- **Readiness gate missing** (Ravi, Group A): Definitively disproven again. The gate exists at `cleaning_task_router.py` lines 816–857.
- **Supply tracking as inventory gap**: Not an issue — intentional status-based design.
- **Template system fragility**: Not an issue — 3-level fallback provides defaults.

---

## Residual Items (Future Architecture, Not Audit Fixes)

1. **Atomic status write**: Make the `properties.operational_status` update and task completion transactional. Required for eventual consistency guarantee. Needs Supabase transaction support or saga pattern.
2. **Reconciliation sweep**: Detect COMPLETED tasks where property is still `needs_cleaning` — for catching unlogged historic failures.
3. **Template editor UI**: Admin UI for creating/editing cleaning templates.
4. **Par level definitions**: Define measurable supply thresholds per unit size.
