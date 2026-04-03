# OPS Manager — Screen Map (V1)

**Role:** Operational Manager (manager)
**Shell:** OMSidebar (desktop) / OMBottomNav (mobile)
**Theme:** Dark command center (midnight backgrounds, white/green/red/amber data)
**Access:** FULL_ACCESS in middleware — navigational isolation only, not enforced

---

## Navigation Structure

### Primary Tabs (Bottom Nav / Sidebar Cockpit Section)
1. **Hub** → `/manager` — Operational command center
2. **Alerts** → `/manager/alerts` — Escalation monitor
3. **Stream** → `/manager/stream` — Live task + booking board
4. **Team** → `/manager/team` — Worker coverage matrix

### Secondary (Sidebar / "More" sheet on mobile)
5. **Bookings** → `/manager/bookings` — Coordination overlay
6. **Tasks** → `/manager/tasks` — Full task board with interventions
7. **Calendar** → `/manager/calendar` — Monthly view

### Utility
8. **Profile** → `/manager/profile` — Identity, notifications, capabilities

---

## Screen Inventory

### S01 — Hub (Default Landing)
**URL:** `/manager`
**Purpose:** Morning command center. The first screen the manager sees.
**Sections:**
- App header: "Operations Hub" + date/time + avatar
- KPI strip: Total tasks | Done | Active | Overdue | On-Time %
- Morning Briefing card (collapsible): progress bar, summary stats, attention count
- Needs Attention section: critical/overdue alert cards (red, pulsing)
- Operational Streams section: 4 stream cards (Check-In, Check-Out, Cleaner, Maintenance) each showing worker, task counts, status pills
- Activity Feed: live audit stream (grouped by action type — task acknowledged, completed, flags updated, takeover initiated, reassigned)
- Task Execution Drawer: responsive (desktop slide-in / mobile full-screen) — embeds actual worker wizards for manager takeover

**States:**
- Loading: center spinner
- All clear: briefing card shows 100%, no attention items, green state
- Alerts present: attention cards rise to top, stream cards show red/amber borders
- Takeover active: execution drawer open with embedded wizard

**Links to:**
- Morning Briefing card → S02 (Briefing Cockpit)
- Alert cards → S03/S06 (Alert Detail)
- Stream cards → S08 (Stream Overview) filtered to that stream
- Activity feed items → Task detail inline expansion
- Avatar → S08 (Profile)

---

### S02 — Morning Briefing Cockpit
**URL:** `/manager` (expanded briefing state or modal)
**Purpose:** Full operational snapshot for the day.
**Sections:**
- Dark cockpit header: date, progress bar, percentage
- KPI row (2×2 grid): check-ins, check-outs, cleans, maintenance jobs
- Attention alerts (if any): blinking dot + red text
- Stream summary rows: per-stream status pills (done/active/overdue)
- Worker availability rows: name, status badge (available/busy/overloaded)

**Back:** → S01 (Hub)

---

### S03 — Alert Detail (Critical / Overdue)
**URL:** `/manager/alerts/{id}` (or inline on mobile)
**Purpose:** Full context for a critical situation requiring intervention.
**Sections:**
- Alert header: red/amber background, LIVE badge (blinking), property name, subtitle
- Impact assessment: guest impact, SLA status
- Detail blocks: property info, assigned worker, timeline, booking context
- Intervention options: Reassign Worker, Contact Guest, Escalate to Owner, Call Worker

**States:**
- Live/unresolved: LIVE badge active, intervention buttons enabled
- Resolved: green header, "Resolved" badge, intervention buttons removed

**Links to:**
- "Reassign" → S04 (Pick Worker)
- "Escalate" → S07 (Escalate to Owner)
- Back → S01 or S17 (Alerts list)

---

### S04 — Reassign: Pick Worker
**URL:** `/manager/alerts/{id}/reassign` (or drawer)
**Purpose:** Select replacement worker for a task.
**Sections:**
- Back header → Alert Detail
- Available workers list: avatar, name, current load, ETA, availability tag
- Unavailable workers (dimmed): name, reason

**Links to:**
- Worker card tap → S05 (Reassign Confirmed)
- Back → S03

---

### S05 — Reassign: Confirmed
**URL:** (transient success state)
**Purpose:** Confirmation that reassignment was executed.
**Sections:**
- Green success header: checkmark icon, "Worker Reassigned"
- Summary: new worker name, property, estimated arrival
- Return button → Hub

---

### S06 — Alert Detail (Warning / SLA Risk)
**URL:** `/manager/alerts/{id}`
**Purpose:** Context for non-critical but time-sensitive situations.
**Sections:**
- Amber header with property name
- Risk assessment: time until guest arrival, current task status
- Detail blocks: maintenance job details, worker progress, property access
- Intervention options: Escalate to Owner, Send Update, Reassign

**Links to:**
- "Escalate" → S07
- Back → S01 or S17

---

### S07 — Escalate to Owner
**URL:** (modal/drawer from alert)
**Purpose:** Formal escalation with reason and method selection.
**Sections:**
- Alert summary (read-only)
- Escalation form: reason, impact description, urgency level
- Contact method selection: LINE, Phone, Email
- Send button

**Links to:**
- Success → return to Alert Detail with "Escalated" status
- Cancel → back to Alert Detail

---

### S08 — Stream Tab Overview
**URL:** `/manager/stream`
**Purpose:** Bird's-eye view of all operational streams.
**Sections:**
- Stream selector tabs: Check-In | Check-Out | Cleaner | Maintenance
- Status strip: pills showing done/active/overdue per selected stream
- Task list with canonical ordering:
  - Check-Out items (time-critical, first)
  - Cleaning items (dependent on checkout)
  - Check-In items (dependent on cleaning)
- Each row: urgency bar | property | status + urgency badge | worker | due time | chevron

**Two sub-tabs:** Tasks | Bookings

**Links to:**
- Task row → S10 (Task Item Detail) or inline expansion
- Stream tab change → filters list

---

### S09 — Check-Out Runway (Stream Filtered)
**URL:** `/manager/stream?lane=checkout`
**Purpose:** Focused checkout operations view.
**Sections:**
- Filter strip: status pills (overdue/active/done counts)
- Tab bar: Active | Upcoming | Complete
- Task cards: property, guest, worker, time, status, urgency

**Links to:**
- Card → S10 (Item Detail)

---

### S10 — Stream Item Detail
**URL:** `/manager/stream/{task_id}` (or inline panel)
**Purpose:** Full detail for a single stream task with intervention options.
**Sections:**
- Dark header: property name, task type badge
- Detail block: guest, worker, time window, status, progress
- Turnover chain visualization (checkout → clean → checkin sequence for same property)
- Manager notes history
- Action buttons: Add Note | Reassign | Takeover/Execute

**Links to:**
- "Reassign" → worker picker
- "Takeover" → execution drawer (embeds worker wizard)
- Back → S08/S09

---

### S11 — Cleaner Runway
**URL:** `/manager/stream?lane=cleaning`
**Purpose:** Cleaning operations with room-level visibility.
**Sections:**
- Status pills, tab bar (Active | Upcoming | Complete)
- Clean cards: property, worker, room count, photo progress, status

**Links to:**
- Card → S12

---

### S12 — Cleaner Item Detail
**URL:** inline panel from S11
**Purpose:** Room-level cleaning progress with manager options.
**Sections:**
- Property header with status
- Room progress list: room names with completion dots
- Photo count badge
- Worker assignment + "Assign Support" button

**Links to:**
- "Assign Support" → S13

---

### S13 — Assign Support Worker
**URL:** (drawer from S12)
**Purpose:** Add a backup cleaner to an active cleaning task.
**Sections:**
- Available cleaners list (same pattern as S04)
- Capacity indicators per worker

---

### S14 — Maintenance Runway
**URL:** `/manager/stream?lane=maintenance`
**Purpose:** Priority-ranked maintenance jobs.
**Sections:**
- Priority filter: Critical | High | Normal
- Job cards: property, issue type, worker, SLA deadline, priority badge

**Links to:**
- Card → S15

---

### S15 — Maintenance Item Detail
**URL:** inline panel from S14
**Purpose:** Full maintenance job context.
**Sections:**
- Property header + priority badge
- Job details: issue description, category, reporter, access code
- SLA timeline
- Before/after photo slots
- Action buttons: Reassign | Escalate | Update Priority

---

### S16 — Check-In Runway (Calm State)
**URL:** `/manager/stream?lane=checkin`
**Purpose:** Check-in operations — typically calmer than checkout.
**Sections:**
- Status pills, tab bar
- Check-in cards: property, guest, worker, arrival time, status
- Dependencies shown: "Waiting on cleaning" badge if predecessor incomplete

---

### S17 — Alerts: Full List
**URL:** `/manager/alerts`
**Purpose:** Complete alert history with filtering.
**Sections:**
- Stat cards: Critical count | Warnings count | Total
- Filter buttons: All | Critical | Warning | Info
- Alert list: severity icon, action label, entity, timestamp, payload preview
- Auto-refresh: 30s polling

**States:**
- No alerts: green checkmark, "No active alerts" (positive empty state)
- Alerts present: color-coded list sorted by severity then time

**Links to:**
- Alert card → S03/S06

---

### S18 — Team: Live Staffing
**URL:** `/manager/team`
**Purpose:** Worker coverage matrix across all managed properties.
**Sections:**
- Summary stats: Workers | Properties | Coverage Gaps
- Property coverage cards (collapsible, one per property):
  - Property name, worker count, open task count
  - Coverage gap pills (red): "No Primary Cleaner" etc.
  - 3-lane matrix: Cleaning | Maintenance | Checkin/Checkout
  - Primary (star) and Backup (dot) workers per lane
- Cross-property worker roster (bottom):
  - All workers deduplicated
  - Each: avatar, name, assignments, open task count

**States:**
- Empty: "No properties assigned yet" + lane legend
- Loaded: stats + property cards + worker roster

**Links to:**
- Worker card → S19/S21 (Worker Detail)

---

### S19 — Worker Detail: Overloaded
**URL:** `/manager/team/{worker_id}` (or inline panel)
**Purpose:** Individual worker view when flagged as overloaded.
**Sections:**
- Dark header: avatar, name, role, status badge (OVERLOADED/red)
- Load bar: visual capacity indicator (red zone)
- Active task list: current assignments with time/priority
- Performance metrics summary
- Action: "Redistribute Work" button

**Links to:**
- "Redistribute" → S20

---

### S20 — Redistribute Work
**URL:** (drawer from S19)
**Purpose:** Select tasks to move off an overloaded worker.
**Sections:**
- Task selection list with checkboxes
- Each task: property, type, urgency pill
- Target worker dropdown or auto-suggest
- Confirm redistribution button

---

### S21 — Worker Detail: At Capacity
**URL:** `/manager/team/{worker_id}`
**Purpose:** Worker view when at capacity (amber, not critical).
**Sections:**
- Same structure as S19 but amber status
- Load bar in amber zone
- Monitoring note instead of redistribute CTA

---

### S22 — Bookings: Active Stays
**URL:** `/manager/bookings`
**Purpose:** Operational coordination overlay on active bookings.
**Sections:**
- Search input: filter by ref, property, guest name
- Booking cards (collapsible):
  - Status badge | ref + VIP + property | guest + dates | coordination status
  - Expanded: ETA, coordination status, last update, source
  - Operational notes block
  - Actions: Add Note | Approve Early Checkout

**Links to:**
- Booking card → S23/S24/S25 (Booking Detail variants)

---

### S23 — Booking Detail: Active Stay
**URL:** `/manager/bookings/{id}` (or inline)
**Purpose:** Full booking context for an active stay.
**Sections:**
- Property header with active badge
- Guest info, dates, check-in/out times
- Operational notes timeline
- Task chain: checkout → clean → next checkin
- Booking flags: DND, VIP, Late Arrival, etc.

---

### S24 — Booking Detail: Early Check-Out
**URL:** `/manager/bookings/{id}`
**Purpose:** Handling an early checkout request.
**Sections:**
- Same as S23 but with early checkout workflow
- Reason display
- Approve/Deny buttons
- Impact assessment: cleaning reschedule needed, next guest impact

---

### S25 — Late Arrival Coordination
**URL:** `/manager/bookings/{id}`
**Purpose:** Managing a guest arriving after normal hours.
**Sections:**
- Booking context with late arrival flag
- Self check-in status (Gate 1 / Gate 2 progress)
- Worker availability for late check-in
- Communication options to guest

---

### S26 — Calendar
**URL:** `/manager/calendar`
**Purpose:** Monthly overview of bookings and tasks.
**Sections:**
- Month grid with navigation (← Month Year →) + Today button
- Day cells: day number, booking count ("X stays"), task dots (colored by kind), "+N" overflow
- Selected date detail panel:
  - Stays list: ref, property, guest
  - Tasks list: kind dot, title, property, status badge

**Links to:**
- Stay → S22 (Bookings)
- Task → S18 (Tasks page)

---

### S27 — Profile
**URL:** `/manager/profile`
**Purpose:** Personal settings and capabilities.
**Sections:**
- Identity: name, email, role ("Operational Manager"), status, user ID
- Supervised properties: chip list
- Notification preferences: LINE ID, phone number (editable)
- Active capabilities: delegated permission badges (read-only)

---

## Screen Count Summary

| Section | Screens | IDs |
|---------|---------|-----|
| A. Hub | 2 | S01–S02 |
| B. Alert Detail | 5 | S03–S07 |
| C. Stream | 9 | S08–S16 |
| D. Team / Alerts | 5 | S17–S21 |
| E. Bookings | 4 | S22–S25 |
| F. Calendar | 1 | S26 |
| G. Profile | 1 | S27 |
| **Total** | **27** | |
