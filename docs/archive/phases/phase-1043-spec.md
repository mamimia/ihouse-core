# Phase 1043 — Morning Briefing Truth-Model Correction

**Status:** CLOSED  
**Commit:** `97d3414`  
**Date closed:** 2026-04-02  
**Branch:** `checkpoint/supabase-single-write-20260305-1747`

---

## Product Rule — locked here

> The OM Morning Briefing surfaces **operational-now or operationally-actionable** signals only.  
> Scheduled future work must not be framed as a current problem.  
> Developer/internal/system-debug signals must not surface to OM unless they are scoped, current, human-readable, and actionable.

---

## Scope — 4 surgical changes, 2 files

| # | Change | File |
|---|--------|------|
| 1 | `_fetch_tenant_tasks_summary` — add date-awareness; return `overdue`, `due_today`, `due_soon` (3 days), `future` buckets separately | `src/api/ai_context_router.py` |
| 2 | `_fetch_dlq_summary` — removed entirely from the OM morning briefing context call | `src/api/manager_copilot_router.py` + `src/api/ai_context_router.py` |
| 3 | LLM system prompt — remove DLQ from priority signal list | `src/api/manager_copilot_router.py` |
| 4 | `_build_heuristic_briefing` — rewrite task wording using date-aware buckets; remove DLQ branches | `src/api/manager_copilot_router.py` |

---

## What this phase does NOT do

- Does not redesign Hub layout
- Does not touch `_fetch_tenant_operations` (arrivals/departures/cleanings) — verified correct in Phase 1042
- Does not touch active bookings logic — verified tenant-isolated and correct (13 for `tenant_mamimia_staging`, scoped by `tenant_id`)
- Does not touch outbound sync logic — not a current issue on this tenant
- Does not remove `_fetch_dlq_summary` from the codebase — it remains available for admin surfaces
- Does not change the DLQ Inspector admin endpoints

---

## Verification pre-implementation (from Phase 1042 audit)

| Fact | Verified |
|------|---------|
| All 30 open tasks have `due_date` populated | ✅ `missing_due_date = 0` |
| Due today = 0, overdue = 0, future = 30 | ✅ DB confirmed |
| Active bookings are tenant-scoped | ✅ `tenant_mamimia_staging` = 13, `tenant_e2e_amended` = 48 (separate) |
| DLQ table has no `tenant_id` column | ✅ Schema confirmed |
| DLQ entries are stale test artifacts | ✅ All 18–25 days old |

---

## Implementation detail

### Change 1 — Date-aware task summary

`_fetch_tenant_tasks_summary` now returns:

```python
{
  "overdue": int,           # due_date < today, still open
  "due_today": int,         # due_date == today
  "due_soon": int,          # due_date in [tomorrow, today+3]
  "future": int,            # due_date > today+3
  "actionable_now": int,    # overdue + due_today
  "total_open": int,        # all buckets
  "by_priority_actionable": {…},  # priority breakdown of actionable_now tasks only
  "critical_past_ack_sla": int,   # unchanged — CRITICAL PENDING > 5 min
}
```

The old `"by_priority"` (counted everything without date-filter) is replaced by `"by_priority_actionable"` which counts only overdue + due_today tasks.

### Change 2 — DLQ removed from OM briefing context

`_get_operations_context()` in `manager_copilot_router.py` no longer calls `_fetch_dlq_summary`.  
The `"dlq"` key is removed from the context dict passed to the LLM and heuristic builder.

`_fetch_dlq_summary` remains in `ai_context_router.py` for use by admin surfaces (`GET /ai/context/operations-day` still includes it for admin use — unchanged).

### Change 3 — LLM system prompt

Removed: `"DLQ alerts"` from the priority signal list.  
`_SYSTEM_PROMPT` now reads: `"Lead with the most urgent items (SLA breaches, overdue tasks, high-activity arrival/departure days)."`

### Change 4 — Heuristic briefing rewrite

`_build_heuristic_briefing` now:
- Uses `actionable_now` (overdue + due_today) instead of `total_open`
- Wording: if actionable_now > 0: "N task(s) need attention today (X overdue, Y due today)."  
  If actionable_now == 0 and future > 0: "No tasks need immediate attention. N task(s) scheduled ahead."
- `by_priority_actionable` used for the priority breakdown — not the full future-inclusive count
- DLQ conditional branches entirely removed
- Top action priority: `critical_sla → actionable_tasks → high_arrival → sync_degraded → default`
- Action items list: DLQ item removed

---

## Active bookings — audit note

**Verified correct, no change needed.**  
`_fetch_tenant_operations` filters `booking_state` with `tenant_id = <jwt tenant>` and `status = 'active'`. This correctly returns only this tenant's live bookings across their properties. The briefing line "13 active booking(s)" is accurate. No property-level OM scoping is applied — that would require the OM's specific property assignments, which is a future capability if needed.

---

## Closure Conditions

- [x] `_fetch_tenant_tasks_summary` returns date-aware buckets (`overdue`, `due_today`, `due_soon`, `future`, `actionable_now`)
- [x] Heuristic briefing correctly says `"No tasks overdue or due today. 2 task(s) coming up in the next 3 days."` — staging PROVEN
- [x] Heuristic briefing correctly surfaces `"Total_open task(s) scheduled ahead."` as non-alarming background info when actionable_now = 0
- [x] DLQ removed from OM briefing context in `_get_operations_context()`
- [x] DLQ removed from LLM system prompt priority list
- [x] DLQ conditional branches removed from `_build_heuristic_briefing()`
- [x] DLQ action item removed from structured `action_items` list
- [x] `_fetch_dlq_summary` still present in codebase (not deleted) for admin context endpoint `GET /ai/context/operations-day`
- [x] 152 tests passed, 0 failed (affected test files updated to reflect new contract)
- [x] Staging PROVEN — briefing reads: `"No tasks overdue or due today. 2 task(s) coming up in the next 3 days."` / `"Top action: Confirm daily operations are on track."` / No DLQ text visible
- [x] Commit `97d3414` pushed to `checkpoint/supabase-single-write-20260305-1747`

**Status: CLOSED — Morning Briefing truth model corrected for OM.**
