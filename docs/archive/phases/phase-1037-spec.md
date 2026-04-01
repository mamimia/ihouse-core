# Phase 1037 — Hub Restructure + Booking Runway Correction

**Status:** SPEC LOCKED — v2 (revised after second product review)
**Date locked:** 2026-04-01
**Branch:** `checkpoint/supabase-single-write-20260305-1747`
**Prerequisite:** Phase 1036

---

## 1. Hub vs Stream — Locked Product Split

### Hub `/manager`
**Purpose:** Compact command dashboard. Answers: *"What needs my attention right now?"*

Open Hub → understand in 10 seconds whether anything is critical. Not a work queue. Not an audit feed.
Hub is the entry point. Stream is the full operational surface.

**Locked layout order (top → bottom):**
1. Header — title, timestamp, Refresh
2. Alert Rail — max 5 critical/high/warning alerts, sourced from `GET /manager/alerts`
3. Morning Briefing Cockpit — compact widget, *Generate Briefing* → AI summary + action items + key counts
4. Operational Summary Strip — 4 live metric chips: Overdue / Due Today / Unassigned / In Progress (from live task data)
5. Priority Task Snapshot — top 8 most urgent open tasks, canonical order, click → ManagerTaskDrawer, *"View all in Stream →"* CTA
6. Today's Booking Snapshot — arrivals + departures + active in-stay bookings today, max 5 rows, *"View full runway →"* CTA

**Removed from Hub:**
- Old "Live Stream" section (audit_events feed) → removed entirely (belongs in `/admin/audit`)
- BookingAuditLookup → moved out (admin/audit utility, not a day-to-day control)
- Full unfiltered Task Board → replaced by Priority Task Snapshot (max 8 rows)
- Audit-event-derived metrics → replaced by live task table counts
- Morning Briefing (was dead code — defined but not rendered) → now rendered near top

---

### Stream `/manager/stream`
**Purpose:** Full live operational runway. *"Everything that is happening and everything coming up."*

Stream is the intervention surface. The manager works here.
- Full task list (all open, urgency sort, canonical ordering)
- Click row → ManagerTaskDrawer (Takeover / Reassign / Handoff note / Add Task)
- Full booking runway (in-stay + today + upcoming 7 days)

Stream stays exactly as built in Phase 1035–1036. No structural changes needed.

---

## 2. Booking Runway — Corrected Definition

### The wrong model (Phase 1035 original)
The Phase 1035 implementation filters for bookings where `start_date` OR `end_date` falls in the window `yesterday → +7 days`. This is **too narrow** because:
- A booking checked in 3 days ago has `start_date` outside the window
- It is still operationally active — the guest is in the property right now
- It gets hidden from the manager even though it is the most live booking possible

### The correct model (Phase 1037)
A booking is operationally alive until the guest checks out. The runway must show:

| Category | Condition | Label |
|---|---|---|
| **Departing Today** | `end_date = today` | "Departing Today" |
| **Arriving Today** | `start_date = today` | "Arriving Today" |
| **Active In-Stay** | `start_date < today AND end_date > today` (guest is in property right now) | "Active Stay — Out [date]" |
| **Departing Tomorrow** | `end_date = today + 1` | "Departing Tomorrow" |
| **Arriving Tomorrow** | `start_date = today + 1` | "Arriving Tomorrow" |
| **Upcoming Runway** | `start_date` or `end_date` in next 7 days | "Arriving in Xd" |

**Visibility rule: show booking until checkout is confirmed (booking status = checked_out / completed).**
Not until `end_date` falls out of a rolling window.

### Backend fix required (Phase 1037)
Current `GET /manager/stream/bookings` uses two queries:
- `start_date BETWEEN window_start AND window_end`
- `end_date BETWEEN window_start AND window_end`

A booking where `start_date < window_start` and `end_date > window_start` (i.e., an in-stay booking)
matches neither query and is invisible.

**Fix:** add a third query to capture active in-stay bookings:
```
start_date < today AND end_date >= today AND status NOT IN ('cancelled', 'rejected', 'completed', 'checked_out')
```
Merge all three results, deduplicate by `booking_id`.

---

## 3. Check-in / Check-out — Final Product Rule

### Do NOT build ad-hoc check-in or check-out as generic task types

Check-in and Check-out tasks are **booking-generated**. They exist because a booking exists.
They carry booking context: guest name, arrival time, door code, guest count.
Creating them ad-hoc would produce orphaned tasks with none of that context.

This is the correct final policy. Not a temporary restriction.

### What already exists (code truth)

**Early Check-out:** Already fully built and deployed.
- Backend: `POST /admin/bookings/{id}/early-checkout/request` → `POST /admin/bookings/{id}/early-checkout/approve`
- Frontend component: `EarlyCheckoutPanel.tsx` (full lifecycle: record request → approve → revoke → completed)
- Manager surface: `EarlyCheckoutModal` in `/manager/bookings/page.tsx` — "Approve Early C/O" button on active bookings

**The correct action:** reuse this. Do not rebuild it. Do not add it to Add Task.

### Manager-facing path for Early Check-out (Phase 1037 connection)
The existing flow lives at `/manager/bookings`. Stream's Booking tab should surface a direct link
to the Early Check-out panel for in-stay bookings, not replicate the flow inline.

When a booking row is clicked in Stream Bookings:
- If `status = checked_in / active` → show booking detail with "Early Check-out" action button → opens `EarlyCheckoutPanel`
- This reuses `EarlyCheckoutPanel.tsx` with `embedded={true}`

No new endpoint. No new component. Connection only.

### Late Check-in / Late Arrival
Late arrival is an operational coordination concern, not a task exception flow.
Handled via coordination_status on the booking overlay (`/manager/bookings`).
Do not create a "Late Check-in" task type.

### Self Check-in
Self check-in is a **property-level configuration** (check-in method: self-serve vs. staffed).
It is NOT an exception flow and must never be conflated with Late Check-in or Early Check-out.

---

## 4. Add Task — Confirmed Scope

Add Task remains useful for:
| Kind | Correct use |
|---|---|
| **Extra Cleaning** | Unscheduled cleaning not from a booking (mid-stay refresh, guest complaint, inter-stay extra) |
| **Maintenance** | Physical repair, inspection, equipment fault, property issue |
| **General Task** | Any operational intervention that doesn't fit above |

**CHECKIN_PREP / CHECKOUT_VERIFY:** Not in Add Task. Final policy. The modal must explain this in one sentence.

---

## 5. General Task — Locked Definition

**Product definition:**
A manager-initiated operational task that does not fit any canonical operational category.
Not a cleaning. Not a maintenance repair. Not a booking-linked exception.

**Examples:** restocking supplies, security walkthrough, post-complaint follow-up,
utility task, access coordination, amenity setup, owner-requested inspection  

**UI label:** "General Task" (not "General Operational Task" — too verbose)

---

## 6. Priority Semantics — Locked

Applies to all ad-hoc tasks (Extra Cleaning, Maintenance, General Task):

| Priority | Definition | Current effect | Future effect |
|---|---|---|---|
| **MEDIUM** | Default. Non-urgent, planned work. | Sort order only | No change |
| **HIGH** | Same-day urgency. Guest-impacting. | Sort order only | Alert trigger (future phase) |
| **CRITICAL** | Immediate. Property or guest at risk. | Sort order + timing gate bypass | SLA notification (future phase) |

**The Add Task modal must show a one-line definition per priority level.**
No guessing required from the manager. Examples shown in the selector.

---

## 7. Property Naming — All OM Surfaces

Human property name is the primary label. Property code is secondary (smaller, dimmer).

Applies to each of these surfaces — Phase 1037 must enforce all:
- [ ] Hub Priority Task Snapshot
- [ ] Hub Today's Booking Snapshot
- [ ] Stream task rows ✓ (done Phase 1035)
- [ ] Stream booking rows ✓ (done Phase 1035)
- [ ] ManagerTaskDrawer header (currently shows raw `property_id`)
- [ ] TakeoverModal header chip (currently shows `task.task_kind · task.property_id` — raw code)
- [ ] EarlyCheckoutModal header (currently shows raw `booking.property_id`)
- [ ] Add Task modal property selector (currently shows code from `task.property_id`)

---

## 8. Canonical Ordering — unchanged

Within same property + same operational day (due_date), task display order:
```
CHECKOUT_VERIFY  (1) ← guest departs
CLEANING         (2) ← property turned over
CHECKIN_PREP     (3) ← new guest arrives
MAINTENANCE      (4)
GENERAL          (5)
```
This ordering must appear in both Hub (Priority Task Snapshot) and Stream (full list).
`KindSequenceBadge` component already built in Phase 1036.

---

## 9. Implementation Scope — Phase 1037

### Backend (1 fix required)
- `GET /manager/stream/bookings`: add third query for active in-stay bookings (`start_date < today AND end_date >= today AND status NOT IN cancelled/completed/checked_out`). Merge + deduplicate.

### Frontend

**Hub (`manager/page.tsx`) — full restructure:**
- Remove: old Live Stream section (audit_events feed)
- Remove: BookingAuditLookup as primary widget
- Remove: audit-event-derived metrics
- Remove: full unbounded TaskBoard
- Add: Morning Briefing at top (already built — just render it)
- Add: Operational Summary Strip (4 chips from live task data)
- Add: Priority Task Snapshot (max 8 tasks, canonical order, click → ManagerTaskDrawer)
- Add: Today's Booking Snapshot (arrivals + departures + active in-stay today, max 5 rows)

**Stream bookings tab (`manager/stream/page.tsx`) — booking click-through:**
- Clicking a booking row for an active/checked_in booking → show booking action panel
- Include "Early Check-out" action → opens `EarlyCheckoutPanel` with `embedded={true}`
- No new endpoint. Reuse of existing `EarlyCheckoutPanel` and `GET/POST /admin/bookings/{id}/early-checkout`

**Add Task modal — property naming + priority UX:**
- Property selector: show `property_name` (human-first), not raw `property_id`
- Priority selector: show one-line definition per level
- CHECKIN_PREP/CHECKOUT_VERIFY block: one clear explanatory sentence

**Property naming enforcement pass:**
- ManagerTaskDrawer header: resolve `property_name` from task data (already in response since Phase 1035)
- TakeoverModal header chip: replace raw `task.task_kind · task.property_id` with `kindLabel · property_name`
- EarlyCheckoutModal header: replace raw `booking.property_id` with property name (requires lookup or pass-through)

---

## 10. Phase 1037 — Closure Conditions

**Hub restructure:**
1. Hub no longer contains an audit event feed.
2. Hub no longer contains BookingAuditLookup as a primary widget.
3. Hub metrics come from live task data, not audit_events.
4. Morning Briefing renders at top of Hub.
5. Hub task list shows max 8 rows with "View all in Stream →" CTA.
6. Clicking a Hub task row opens ManagerTaskDrawer (not a TakeoverModal).

**Booking runway:**
7. Stream Bookings tab shows active in-stay bookings (guest currently in property).
8. Screenshot proof: at least one in-stay booking visible in Stream Bookings tab.

**Early Check-out reuse:**
9. Stream booking rows for active/checked_in bookings expose the Early Check-out action.
10. Clicking it opens `EarlyCheckoutPanel` (existing component, not a new component).

**Human naming:**
11. ManagerTaskDrawer header shows human property name.
12. TakeoverModal shows human property name, not raw code.
13. Add Task property selector shows human names.

**Priority UX:**
14. Add Task priority selector shows one-line definition per level.

**Canonical ordering:**
15. Hub Priority Task Snapshot uses canonical ordering (Checkout → Cleaning → Check-in within same property+day).

---

## Addendum: Phase 1037 — Staff Onboarding Access Hardening (delivered 2026-04-02)

> This work was delivered in the same phase slot. The Hub/booking items above represent
> the original OM-1 spec scope. The staff onboarding items below represent the actual
> work completed in this session.

### Problem
The "Add Staff Member" (manual create) path was failing with 500 errors because:
1. It called `invite_user_by_email` (SMTP-triggered → spam/invisible link)
2. It did not create a Supabase Auth user before writing `tenant_permissions`
3. Hard Delete only removed `tenant_permissions`, leaving orphaned `auth.users` records
   which blocked re-inviting the same email

### Solution (4 sub-commits, all deployed)

**1037a — `POST /admin/staff`:**
New `manual_create_staff` endpoint provisions Supabase Auth UUID first (`generate_link(type=invite)`), then writes `tenant_permissions`. INV-1037-IDENTITY enforced: `comm_preference.email == auth_email`.

**1037b — SMTP bypass:**
Replaced `invite_user_by_email` with `generate_link`. Admin receives raw URL in success overlay. Two actions: **Copy** + **✉ Email** (mailto:). No spam. No missing link.

**1037c — True hard delete:**
`DELETE /admin/staff/{user_id}` atomically removes `tenant_permissions` + `staff_assignments` + `auth.users`.

**1037d — Two-pass auth (bulletproof):**
Pass A = `generate_link(type=invite)`. Pass B (on any of 7 "already exists" signals) = `generate_link(type=magiclink)`. Last resort = `422 USER_ALREADY_EXISTS` with human message. Never a raw 500.

**Cleanup:** orphaned `esweb3@gmail.com` in `auth.users` deleted via Supabase admin SQL.

### Files Changed
| File | Change |
|------|--------|
| `src/api/staff_onboarding_router.py` | NEW: `manual_create_staff` + `hard_delete_staff` |
| `ihouse-ui/app/(app)/admin/staff/new/page.tsx` | MODIFIED: POST /admin/staff, magic_link overlay, mailto |
| `ihouse-ui/app/(app)/admin/staff/[userId]/page.tsx` | MODIFIED: DELETE /admin/staff/{id} |

### Result
**8,144 passed, 18 failed (pre-existing unrelated stubs), 22 skipped. TypeScript 0 errors.**

Commits: `0a8fc27` → `0300bdd` → `92eba9d` → `d006702`
