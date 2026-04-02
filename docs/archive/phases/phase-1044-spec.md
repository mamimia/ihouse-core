# Phase 1044 — OM Hub: Human-Operational Task Title Surface

**Status:** ACTIVE  
**Prerequisite:** Phase 1043 (Morning Briefing Truth-Model Correction)  
**Date opened:** 2026-04-02  
**Branch:** `checkpoint/supabase-single-write-20260305-1747`

---

## Problem Statement

Priority Tasks / task snapshot surfaces on the OM Hub still expose raw internal identifiers as the primary visible title:

- "Check-in prep for ICAL-6240ffab0a91"
- "Checkout verification for ICAL-f1aadf581047"
- "Checkout cleaning for ICAL-6240ffab0a91"

This is system-internal language, not operational UI. The OM is a field operations manager. They need to read property-human-name first, then task type. An ICAL booking ID is meaningless operationally.

---

## Root Cause Analysis

The `title` field is written at task creation time in `task_automator.py`:

```python
title=f"Check-in prep for {booking_id}"    # booking_id may be ICAL-...
title=f"Checkout cleaning for {booking_id}"
title=f"Checkout verification for {booking_id}"
```

The `GET /manager/tasks` backend already resolves `property_name` (the human `display_name` from properties table) and injects it into every task row. However, the frontend `ManagerTask` interface was missing the `property_name` field, and the display fell back to `task.title` — which is always the raw ICAL-polluted string.

---

## Product Rule (Phase 1044 Locked)

On any OM-facing task list or snapshot surface:

> **Default visible task title = `{property display name} — {human task kind label}`**
> 
> Internal identifiers (ICAL booking IDs, booking UUIDs, property codes) must NOT appear
> in the primary visible title. They may appear only in:
> - The detail view / drawer
> - Developer/admin-only surfaces
> - Secondary metadata (`property_id` code as dim tertiary text below the main title)

---

## Target Title Pattern

| Before (ICAL-polluted) | After (human-operational) |
|---|---|
| `Check-in prep for ICAL-6240ffab0a91` | `Emuna Villa — Check-in Prep` |
| `Checkout cleaning for ICAL-6240ffab0a91` | `Emuna Villa — Checkout Cleaning` |
| `Checkout verification for ICAL-f1aadf581047` | `Emuna Villa — Checkout Verification` |
| `Post-checkout cleaning — KPG-500 (early checkout Apr 5)` | `Emuna Villa — Post-checkout Cleaning` *(keeps special label if is_early_checkout)* |

Secondary text row: `KPG-500 · 2026-04-15`

---

## Scope of Change

### Frontend-only (no DB/backend change required)

Backend `GET /manager/tasks` already returns `property_name` (display_name resolved from `properties` table). The fix is purely presentational.

**Files changed:**
1. `ihouse-ui/app/(app)/manager/page.tsx`

**Specific changes:**
- Add `property_name?: string` to `ManagerTask` interface (L334)
- Add `buildOperationalTaskTitle(task)` pure function that returns the human title
- Update `PriorityTaskSnapshot` task row (L1588) to use `buildOperationalTaskTitle`
- Update `FullTaskBoard` task row (L961) to use `buildOperationalTaskTitle`
- Update `TakeoverModal` info block (L433) to use `buildOperationalTaskTitle`
- Update secondary metadata rows to show `property_id` as dim code text only

---

## `buildOperationalTaskTitle` Logic

```typescript
const OPERATIONAL_KIND_LABEL: Record<string, string> = {
  CLEANING:              'Checkout Cleaning',
  CHECKIN_PREP:          'Check-in Prep',
  CHECKOUT_VERIFY:       'Checkout Verification',
  GUEST_WELCOME:         'Guest Welcome',
  MAINTENANCE:           'Maintenance',
  SELF_CHECKIN_FOLLOWUP: 'Self Check-in Follow-up',
  GENERAL:               'General Task',
};

function buildOperationalTaskTitle(task: ManagerTask): string {
  const propertyLabel = task.property_name || task.property_id;
  const kindLabel = OPERATIONAL_KIND_LABEL[task.task_kind] ?? task.task_kind;
  return `${propertyLabel} — ${kindLabel}`;
}
```

**Special case:** If `task.is_early_checkout === true`, use `'Post-checkout Cleaning'` instead of `'Checkout Cleaning'`.

---

## Surfaces Updated

1. **Hub `/manager` — PriorityTaskSnapshot** (component `PriorityTaskSnapshot`)
   - Primary title row: `buildOperationalTaskTitle(t)`  
   - Secondary row: `{t.property_id} · {t.due_date}`

2. **Full Task Board `/manager/tasks`** (component `TaskRow`)
   - Primary title row: `buildOperationalTaskTitle(task)`
   - Secondary row: `{task.property_id} · Due {task.due_date}`

3. **Takeover Modal** (component `TakeoverModal`)  
   - Info block title: `buildOperationalTaskTitle(task)`

---

## Surfaces NOT Changed (intentional)

- `task.title` raw value in detail drawer / `ManagerTaskCard` → internal data, acceptable there
- `booking_id` in worker-facing routes → outside OM scope for this phase
- `task_automator.py` title generation → not changed (DB is append-only truth, not display layer)
- `task.task_kind` code chip in Full Task Board header column → acceptable as secondary chip

---

## Closure Conditions

- [ ] `ManagerTask` interface has `property_name?: string`
- [ ] `buildOperationalTaskTitle()` implemented and used in all 3 surfaces
- [ ] `PriorityTaskSnapshot` on Hub shows `"Emuna Villa — Check-in Prep"` format
- [ ] `FullTaskBoard` task rows show same human format
- [ ] `TakeoverModal` shows same human format
- [ ] `property_id` code (e.g. `KPG-500`) remains as dim secondary text only
- [ ] No ICAL identifiers visible on primary task list surface
- [ ] Vercel deploy successful
- [ ] Staging screenshot proof captured

**Status: OPEN**
