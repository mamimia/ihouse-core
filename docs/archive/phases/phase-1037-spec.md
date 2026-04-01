# Phase 1037 — Hub Restructure: Clean Separation of Hub vs Stream

**Status:** SPEC LOCKED — implementation pending  
**Date locked:** 2026-04-01  
**Branch:** `checkpoint/supabase-single-write-20260305-1747`  
**Prerequisite:** Phase 1036 (Stream Hardening — canonical ordering, Add Task, booking scope)

---

## Problem Statement

Hub (`/manager`) and Stream (`/manager/stream`) currently overlap because:

1. Hub contains a "Live Stream" section that still queries `audit_events` (100 events, with filter buttons for `all | task | booking`). This is the original pre-Phase-1035 stream prototype. It was never removed when Phase 1035 built the real `/manager/stream` page.

2. Hub's operational metrics (Takeovers active, Task acked, Task completed, etc.) are derived by counting audit event action types — not from live task table queries. This means they can show stale or misleading counts.

3. The Task Board in Hub renders the full unfiltered task list with a "Take Over" button on every row. This is correct behavior for that button, but the list is not capped — it becomes a second full work queue.

4. Morning Briefing is implemented as a component but **not rendered in Hub**. It exists as dead code.

5. Booking Audit Lookup is embedded in Hub as a primary widget. It is an admin/audit utility, not a day-to-day operational control.

---

## Locked Product Definition

### Hub `/manager`
**Purpose:** Compact command dashboard. Answers: "What needs my attention right now?"

The manager should be able to open Hub and in 10 seconds understand:
- Are there any critical alerts?
- What is today's operational summary?
- Are there any urgent tasks that require intervention this morning?
- What is arriving / departing today?

Hub is NOT a full work queue. It is NOT an audit feed.
Hub is the entry point. Stream is the full operational surface.

**Layout (top to bottom — locked order):**
1. Header (title + timestamp + Refresh)
2. Alert Rail (critical/high/warning — max 5 items, linked to full `/manager/alerts`)
3. Morning Briefing Cockpit (compact widget, Generate Briefing → today's AI summary + action items + key counts)
4. Operational Summary Strip (4 live metric chips from tasks table: Overdue, Due Today, Unassigned, In Progress)
5. Priority Task Snapshot (top 5–10 most urgent open tasks only — canonical order — with "View all in Stream →" CTA — no Take Over button on every row)
6. Today's Booking Snapshot (arrivals + departures today only — compact 3–5 rows — "View full runway →" CTA)

**What is removed from Hub:**
- Live Stream section (audit feed) → **removed entirely** (belongs in `/admin/audit`)
- Booking Audit Lookup → **moved to admin/audit tools area** (not a day-to-day control)
- Full unfiltered Task Board with Take Over buttons on all rows → **replaced** by Priority Task Snapshot (top 5–10, click row → goes to Stream/ManagerTaskDrawer)
- Audit-event-derived metrics → **replaced** by live task table counts

---

### Stream `/manager/stream`
**Purpose:** Full live operational runway. Answers: "Everything that is happening and everything coming up."

Stream is the intervention surface. The manager works here.
- Full task list (all open: PENDING / ACKNOWLEDGED / IN_PROGRESS / MANAGER_EXECUTING)
- Urgency sort + canonical ordering (Checkout → Cleaning → Checkin within same property+day)
- Click row → ManagerTaskDrawer (Takeover / Reassign / Handoff note)
- Add Task (POST /tasks/adhoc)
- Full booking runway (yesterday → +7 days)

Stream remains exactly as built in Phase 1035–1036.
No changes required to Stream.

---

## Priority Task Snapshot (replaces full Task Board in Hub)

### Rendering rules
- Show maximum **8 rows** (top 8 from urgency sort + canonical ordering)
- After 8: show "And N more — View full Stream →" link to `/manager/stream`
- No "Take Over" button on every row — clicking a row opens `ManagerTaskDrawer` (the correct intervention surface from Phase 1034)
- Column layout: [urgency bar] [Property Name (human-first)] [Kind label + sequence badge] [Status chip] [Due date] [›]
- Identical to Stream `TaskRow` component — share the component, do not duplicate

### Data source
Reuses `GET /manager/tasks` — no new endpoint needed.

---

## Operational Summary Strip (replaces audit-derived metrics)

4 metric chips derived from the live task response (not audit_events):

| Chip | Source |
|---|---|
| Overdue | tasks where due_date < today and status in (PENDING, ACKNOWLEDGED, IN_PROGRESS, MANAGER_EXECUTING) |
| Due Today | tasks where due_date = today |
| Unassigned | tasks where assigned_to IS NULL and taken_over_by IS NULL |
| In Progress | tasks where status IN (IN_PROGRESS, MANAGER_EXECUTING) |

---

## Today's Booking Snapshot (new compact widget)

- Source: `GET /manager/stream/bookings` — same endpoint as Stream
- Filter: arrivals + departures today only (urgency_label IN ['Arriving Today', 'Departing Today'])
- Show max 5 rows, compact layout: [property name] [guest name] [label chip]
- "View full runway →" link to `/manager/stream` (Bookings tab)

---

## Alert Rail (repoint to real data)

Current: derived from first 60 audit events by filtering action types.
Target: call `GET /manager/alerts` (already built in Phase 1033/1034).

If `/manager/alerts` is not available, fall back to derived — but mark clearly as "heuristic".  
No structural change needed — only the data source.

---

## Product Decisions — Locked

### Add Task modal: property naming
The property selector must show human names, not raw codes.
Implementation: extend `scopedPropertyIds` to carry `{id, name}` pairs derived from task list (which now includes `property_name`).

### Add Task modal: "General Operational Task"
Locked definition: any manager-initiated operational task that is not a cleaning or maintenance request.
Examples: restocking supplies, security walkthrough, utility task, post-complaint follow-up.
UI label must be: **"General Task"** (not "General Operational Task" — too verbose).

### Priority semantics (locked)
| Priority | Meaning | Current effect | Future |
|---|---|---|---|
| MEDIUM | Default. Scheduled, non-urgent. | Sort order only | No change |
| HIGH | Same-day urgency, guest-impacting. | Sort order only | Future: alert trigger |
| CRITICAL | Immediate. Property/guest at risk. | Sort order + timing gate bypass | Future: SLA notification |

The modal must show a one-line explanation of what each priority means. No guessing required from the manager.

### CHECKIN_PREP / CHECKOUT_VERIFY blocking — final policy
**This is the correct final policy.** Not temporary.  
Check-in and check-out tasks exist because a booking exists. Ad-hoc creation would produce orphaned tasks with no booking context. If a check-in/out task is missing, the correct action is to investigate the booking at `/admin/bookings`, not create a raw task. Modal explains this with one clear sentence.

---

## Implementation Scope

### Phase 1037 — Hub Restructure (frontend only, no new backend)

**Remove from Hub:**
- Old "Live Stream" section (audit_events feed)
- BookingAuditLookup component
- Audit-event-derived metrics
- Full TaskBoard component (replace with Priority Task Snapshot)

**Add to Hub:**
- Morning Briefing Widget (already built — just render it, near top)
- Operational Summary Strip (4 chips from task data, not audit_events)
- Priority Task Snapshot (max 8 tasks, click → ManagerTaskDrawer, "View all in Stream →" CTA)
- Today's Booking Snapshot (compact, arrivals + departures today only)

**Fix in Hub:**
- Alert Rail data source → `GET /manager/alerts` (or heuristic fallback clearly labeled)

**No backend changes required for Phase 1037.**

---

## Naming Rules — All OM Surfaces (Phase 1037 enforcement pass)

Human property name is the primary label. Property code is secondary (smaller, dimmer).

Applies to:
- Hub Priority Task Snapshot
- Hub Today's Booking Snapshot  
- Stream task rows ✓ (already done in Phase 1035)
- Stream booking rows ✓ (already done in Phase 1035)
- ManagerTaskDrawer header (currently shows raw `property_id`)
- TakeoverModal header chip (currently shows raw `task.task_kind · task.property_id`)
- ReassignPanel scope label ✓ (fixed in Phase 1035)
- Add Task modal: property selector must show name, not code

---

## Phase 1037 — Closure Conditions

1. Hub no longer contains an audit event feed ("Live Stream" section removed).
2. Hub no longer contains Booking Audit Lookup as a primary widget.
3. Hub metrics come from live task data, not audit_events counts.
4. Morning Briefing is rendered at the top of Hub (not dead code).
5. Hub Task list shows max 8 rows with "View all in Stream →" CTA.
6. Clicking a Hub task row opens ManagerTaskDrawer (not a new TakeoverModal path).
7. Add Task property selector shows human names, not raw codes.
8. Add Task priority selector shows a one-line explanation per priority level.
9. TakeoverModal header shows human property name, not raw property_id.
10. ManagerTaskDrawer header shows human property name, not raw property_id.
11. Screenshot proof: Hub loads cleanly showing the new compact layout.
12. Screenshot proof: Hub task snapshot correctly shows max 8 items with CTA.
