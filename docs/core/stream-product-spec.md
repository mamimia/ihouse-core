# Ops Manager Stream — Locked Product Definition
**Phase 1035 — locked before implementation**  
**Date:** 2026-04-01

---

## What Stream IS

The Manager Stream is a **real-time operational command surface**, not an audit log.

Its purpose: give the Ops Manager a single view that answers  
**"What needs my attention right now, and what is coming up that I need to be ready for?"**

History of what happened belongs in `/admin/audit`, not here.

---

## Data Source Model

| Tab | Old (wrong) source | New (correct) source |
|---|---|---|
| Tasks | `audit_events` — past events | `tasks` table — live status |
| Bookings | `audit_events` — history | `bookings` table — operational window |
| Sessions | `audit_events` — admin noise | **Removed from OM Stream entirely** |

---

## Tab 1: Tasks

### Visibility rules
Status drives visibility. **Date does not.**

| Include | Exclude |
|---|---|
| PENDING | COMPLETED — always hidden |
| ACKNOWLEDGED | CANCELED — always hidden |
| IN_PROGRESS | |
| MANAGER_EXECUTING | |

**Old open tasks are overdue, not historical.**  
A PENDING task from 3 days ago belongs at the top of the list as OVERDUE, not hidden.  
A COMPLETED task from yesterday is gone. Forever.

### Sort order (urgency-first)
1. **OVERDUE** — due_date < today, any open status → red badge, top of list
2. **TODAY** — due_date = today → amber badge
3. **UPCOMING** — due in next 7 days → sorted by due_date asc
4. **No due date / far future** → sorted by created_at asc, shown last

### Row display
- Property **human name first** ("Emuna Villa"), code secondary in small text ("KPG-500")
- Task kind label (Cleaning / Check-in / Check-out / Maintenance)
- Status chip
- Assigned worker **display name** (not UUID)
- Due date and urgency indicator
- Click → `ManagerTaskDrawer`

---

## Tab 2: Bookings

**Operational booking runway. Not booking event history.**

### Data source
`bookings` table. Operational window: **yesterday → +7 days**.

### Visibility rules
- SHOW: confirmed bookings with arrival OR departure in the operational window
- HIDE: cancelled/rejected, fully past (both dates before yesterday)

### Sort order
1. Today's departures (checkout urgency)
2. Today's arrivals
3. Tomorrow's departures
4. Tomorrow's arrivals
5. Further future, ascending

### Row display
- Property human name first
- Guest name
- Arrival / Departure dates
- Status label: "Arriving Today" / "Active Stay" / "Departing Today" / "Arriving in Xd"
- Task hint if relevant (e.g. "Cleaning: Pending")

---

## Tab 3: Sessions — REMOVED

`ACT_AS_STARTED` and `PREVIEW_OPENED` are developer/admin testing artifacts.  
No operational value to an Ops Manager.  
Sessions audit belongs in `/admin/audit` only.

**After Phase 1035: tabs are Tasks | Bookings only. Default tab: Tasks.**

---

## Property Naming Rule — All OM Surfaces

**Human name is the primary label everywhere.**

```
✓  Emuna Villa
   KPG-500          ← smaller, dimmer text

✗  CLEANING · KPG-500
```

Applies to: Stream rows, ManagerTaskCard header, TakeoverPanel, ReassignPanel context.

---

## Reassign Worker Selector — Proof Requirements

Not provable until:
1. A real worker with a display name appears in the selector (not just "open pool")
2. List filtered by task kind (cleaner for cleaning, checkin staff for checkin, etc.)
3. Empty state reads clearly ("No [Cleaning staff] found for [Emuna Villa]") — no raw `property_id` interpolation
4. Manual UUID entry is a collapsed hidden fallback, not the default visible path

Root cause of current broken state:  
When `GET /tasks/detail/{id}` fails → fallback shell has `property_id = ''`  
→ `/manager/team?task_kind=...` returns nothing → broken empty string displayed.  
Fix: do not show the Reassign panel until task is fully loaded from the detail endpoint.

---

## Note / Handoff / Reason — Locked Semantics

| Concept | Stored | Visible to |
|---|---|---|
| **Internal Manager Note** | `tasks.notes[]` `source="manager_note"` | Manager + Admin only |
| **Reassignment Reason** | `task_actions.details.reason` | Manager + Admin audit only |
| **Worker Handoff Message** | `tasks.notes[]` `source="handoff"` | Worker sees on their task surface |

These are three separate things. Never collapsed into one.

---

## Phase 1035 — Closure Conditions

This phase is NOT closed until all nine are proven:

1. Stream Tasks tab queries `tasks` table (not `audit_events`)
2. Stream Bookings tab queries `bookings` table (not `audit_events`)
3. Sessions tab is absent from the OM Stream
4. At least one task row on Stream is clickable and opens `ManagerTaskDrawer` with real task data
5. `ReassignPanel` shows a real named worker, or a correct "no compatible workers" message (not broken empty string)
6. Reassign execution → `assigned_to` changes in DB → verified by SQL query
7. Handoff message → written to `tasks.notes[]` with `source="handoff"` → verified DB or curl
8. Property human name is primary label in all OM surfaces
9. Broken empty state `"No workers found for ."` is fixed
