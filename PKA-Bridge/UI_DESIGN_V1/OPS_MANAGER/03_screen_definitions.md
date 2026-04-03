# OPS Manager — Screen Definitions (V1)

Each screen is defined with: layout structure, component inventory, data requirements, and state variants.

---

## S01 — Hub (Default Landing)

### Layout (Mobile)
```
┌─────────────────────────┐
│ Status Bar (26px)       │
├─────────────────────────┤
│ App Header (50px)       │
│ "Operations Hub"        │
│  date · time     [AV]  │
├─────────────────────────┤
│ KPI Strip (48px)        │
│ Total|Done|Active|OD|OT%│
├─────────────────────────┤
│ ░ Scrollable Content ░  │
│                         │
│ ┌─ Morning Briefing ──┐ │
│ │ date · progress bar  │ │
│ │ summary · attention  │ │
│ └──────────────────────┘ │
│                         │
│ ── NEEDS ATTENTION (n) ─│
│ ┌─ Alert Card (red) ──┐ │
│ │ OVERDUE  +23 MIN     │ │
│ │ Property — Task      │ │
│ │ [Intervene →]        │ │
│ └──────────────────────┘ │
│ ┌─ Alert Card (amber) ┐ │
│ │ SLA RISK  14:00      │ │
│ │ Property — Task      │ │
│ │ [Review →]           │ │
│ └──────────────────────┘ │
│                         │
│ ── OPERATIONAL STREAMS ─│
│ ┌─ Stream Card ────────┐│
│ │ [icon] Check-In      ││
│ │ 2 workers · 4 today  ││
│ │ [3 done] [1 pending] ││
│ │ View stream →        ││
│ └──────────────────────┘│
│ ┌─ Stream Card (red) ──┐│
│ │ [icon] Check-Out     ││
│ │ Maria G. · 3 today   ││
│ │ [1 overdue] [2 done] ││
│ │ View stream → Interv.││
│ └──────────────────────┘│
│ ┌─ Stream Card (amber) ┐│
│ │ [icon] Cleaner       ││
│ │ Noi C. · 4 cleans    ││
│ │ [2 active] [1 done]  ││
│ │ View stream → Monitor││
│ └──────────────────────┘│
│ ┌─ Stream Card (amber) ┐│
│ │ [icon] Maintenance   ││
│ │ Aroon S. · 3 jobs    ││
│ │ [1 crit] [2 high]    ││
│ │ View stream → Review ││
│ └──────────────────────┘│
│                         │
│ ░ end scroll ░          │
├─────────────────────────┤
│ Bottom Nav (56px)       │
│ Hub* | Alerts | Stream  │
│       | Team            │
└─────────────────────────┘
```

### Layout (Desktop)
```
┌────────┬────────────────────────────────────────────┐
│ OM     │ App Header                                  │
│ Side   ├──────────────────────┬─────────────────────┤
│ bar    │ Left Column (60%)    │ Right Column (40%)  │
│ 220px  │                      │                     │
│        │ KPI Strip            │ Activity Feed       │
│ [Hub]* │ Morning Briefing     │ (live audit stream) │
│ Alerts │ Needs Attention      │                     │
│ Stream │ Operational Streams  │ Booking Lookup      │
│ Team   │                      │ (search + inspect)  │
│ ───    │                      │                     │
│ Book.  │                      │                     │
│ Tasks  │                      │                     │
│ Cal    │                      │                     │
│        │                      │                     │
│ [mode] │                      │                     │
└────────┴──────────────────────┴─────────────────────┘
```

### Components
- AppHeader (dark)
- KPIStrip (5 metrics)
- MorningBriefingCard
- AlertCard (red variant, amber variant)
- StreamCard (4 instances, each with icon, name, worker, status pills)
- ActivityFeedList (desktop only in hub; mobile in separate view)
- BottomNav / OMSidebar

### Data
- GET `/manager/audit` — activity feed
- GET `/manager/tasks` — task counts for KPI + streams
- Computed: overdue count, on-time percentage

### States
| State | Appearance |
|-------|------------|
| Loading | Spinner replacing scroll area |
| All clear | Briefing 100% green, no attention section, all streams green |
| Alerts present | Needs Attention section visible, red/amber stream cards |
| Takeover active | Right drawer (desktop) or full-screen (mobile) with embedded wizard |

---

## S08 — Stream Tab Overview

### Layout (Mobile)
```
┌─────────────────────────┐
│ Status Bar              │
├─────────────────────────┤
│ App Header              │
│ "Operational Stream"    │
├─────────────────────────┤
│ Stream Selector (horiz) │
│ [C/I] [C/O] [CLN] [MNT]│
├─────────────────────────┤
│ Status Strip            │
│ [3 done][2 active][1 OD]│
├─────────────────────────┤
│ Tab Bar                 │
│ Tasks* | Bookings       │
├─────────────────────────┤
│ ░ Task List ░           │
│                         │
│ ┌─ Task Row ───────────┐│
│ │▌ Property Name [LATE]││
│ │  Worker · due 11:00  ││
│ │                    › ││
│ └──────────────────────┘│
│ ┌─ Task Row (red) ─────┐│
│ │▌ Property Name [OD]  ││
│ │  Worker · +23 min    ││
│ │                    › ││
│ └──────────────────────┘│
│ ... more rows ...       │
│                         │
├─────────────────────────┤
│ Bottom Nav              │
└─────────────────────────┘
```

### Layout (Desktop)
```
┌────────┬────────────────────────────────────────────┐
│ OM     │ Stream Header + Selector                    │
│ Side   ├─────────────────────────────────────────────┤
│ bar    │ Status Strip + Tab Bar                      │
│        ├─────────────────────┬───────────────────────┤
│        │ Task List           │ Detail Panel          │
│        │ (scrollable)        │ (inline selection)    │
│        │                     │                       │
│        │ [row] ← selected    │ ManagerTaskCard       │
│        │ [row]               │ with intervention     │
│        │ [row]               │ buttons               │
│        │ [row]               │                       │
│        │                     │                       │
└────────┴─────────────────────┴───────────────────────┘
```

### Components
- StreamSelector (horizontal pill tabs, colored by stream state)
- StatusStrip (done/active/overdue counts)
- FilterTabBar (Tasks | Bookings)
- TaskRow (urgency bar, property, status+urgency badges, worker, due time, chevron)
- ManagerTaskCard (inline expansion / right panel on desktop)
- BookingRow (mobile: stacked card; desktop: table row)

### Canonical Task Ordering (within same property+date)
1. Checkout tasks first (time-critical, blocks everything)
2. Cleaning tasks second (depends on checkout completion)
3. Check-in tasks third (depends on cleaning completion)

### Lane Filter Options
All | Cleaning | Check-in | Welcome | Check-out | Maintenance

### Data
- GET `/manager/tasks` — property-scoped task list
- GET `/bookings` — for bookings tab

---

## S17 — Alerts: Full List

### Layout (Mobile)
```
┌─────────────────────────┐
│ Status Bar              │
├─────────────────────────┤
│ App Header              │
│ "Alerts"                │
├─────────────────────────┤
│ Stat Cards (3)          │
│ [CRITICAL:2][WARN:5][9] │
├─────────────────────────┤
│ Filter Bar              │
│ All*|Critical|Warn|Info │
├─────────────────────────┤
│ ░ Alert List ░          │
│                         │
│ ┌─ Alert Item (red) ───┐│
│ │ ● SLA_BREACHED       ││
│ │   task/xyz · 3m ago  ││
│ │   payload preview    ││
│ └──────────────────────┘│
│ ┌─ Alert Item (amber) ─┐│
│ │ ▲ TASK_OVERDUE       ││
│ │   task/abc · 12m ago ││
│ │   payload preview    ││
│ └──────────────────────┘│
│                         │
├─────────────────────────┤
│ Bottom Nav              │
│ Hub | Alerts* | ...     │
└─────────────────────────┘
```

### States
| State | Appearance |
|-------|------------|
| No alerts | Green checkmark + "No active alerts" (positive state) |
| Loaded | Stat cards + filtered list |
| Auto-refresh | 30s polling, list updates in-place |

---

## S18 — Team: Live Staffing

### Layout (Mobile)
```
┌─────────────────────────┐
│ Status Bar              │
├─────────────────────────┤
│ App Header              │
│ "Team"                  │
├─────────────────────────┤
│ Summary Stats           │
│ [Workers:6][Props:4]    │
│ [Gaps: 1]               │
├─────────────────────────┤
│ ░ Property Cards ░      │
│                         │
│ ┌─ Property Card ──────┐│
│ │ Villa Emuna           ││
│ │ 3 workers · 2 tasks  ││
│ │ ⚠ CLEANING—No Primary││
│ │ ●●○ CLN|MNT|C/I      ││
│ │ ─── expanded: ───    ││
│ │ Cleaning:             ││
│ │  ⭐ Noi (Primary)     ││
│ │  🔵 Maria (Backup)   ││
│ │ Maintenance:          ││
│ │  ⭐ Aroon (Primary)   ││
│ │ Check-In/Out:         ││
│ │  ⭐ Maria (Primary)   ││
│ └──────────────────────┘│
│                         │
│ ── WORKERS ─────────────│
│ ┌─ Worker Row ─────────┐│
│ │ [AV] Maria Gonzalez  ││
│ │ Villa Emuna · C/O    ││
│ │ Primary · 3 tasks    ││
│ └──────────────────────┘│
│                         │
├─────────────────────────┤
│ Bottom Nav              │
│ Hub | Alerts | Stream   │
│       | Team*           │
└─────────────────────────┘
```

### Coverage Lane Dots
- Green (●): Primary + Backup assigned
- Amber (●): Primary only, no backup
- Red (○): No primary assigned (gap!)

---

## S27 — Profile

### Layout (Mobile)
```
┌─────────────────────────┐
│ Status Bar              │
├─────────────────────────┤
│ Back Header → Hub       │
│ "Profile"               │
├─────────────────────────┤
│ ░ Profile Content ░     │
│                         │
│ ┌─ Identity Block ─────┐│
│ │ Display Name     [v] ││
│ │ Email            [v] ││
│ │ Role    Op. Manager  ││
│ │ Status       Active  ││
│ │ User ID     xxx-xxx  ││
│ └──────────────────────┘│
│                         │
│ ┌─ Properties ─────────┐│
│ │ [Villa Emuna]        ││
│ │ [KPG Residence]      ││
│ │ [Baan Suan]          ││
│ └──────────────────────┘│
│                         │
│ ┌─ Notifications ──────┐│
│ │ LINE ID    [input]   ││
│ │ Phone      [input]   ││
│ │ [Save Preferences]   ││
│ └──────────────────────┘│
│                         │
│ ┌─ Capabilities ───────┐│
│ │ ✓ task_management    ││
│ │ ✓ booking_view       ││
│ │ ✓ staff_oversight    ││
│ │ (managed by admin)   ││
│ └──────────────────────┘│
│                         │
├─────────────────────────┤
│ Bottom Nav              │
└─────────────────────────┘
```

---

## Component Reference (OPS Manager Specific)

### MorningBriefingCard
- Dark gradient background (#0F1115 → #1A2030)
- Date label (uppercase, muted)
- Progress bar (green gradient fill)
- Summary text: "X ops today · Y done, Z active"
- Attention alert: blinking red dot + red text
- Tap → Briefing Cockpit

### StreamCard
- White card with optional colored border (by stream state)
- Top row: stream icon (colored circle bg) + name + worker count
- Status pills: done (green) / active (amber) / overdue (red)
- Footer: "View stream →" + optional intervention link
- Stream icon colors: Check-In (#E6EEE7), Check-Out (#FDECEA), Cleaner (#FEF3C7), Maintenance (#F5EAE3)

### AlertCard
- Red variant: red border, #FFF4F4 bg, pulse animation, "OVERDUE" badge
- Amber variant: amber border, #FFFCF0 bg, "SLA RISK" badge
- Content: property name, subtitle, full-width CTA button
- Time display: "+23 MIN" (red/blinking) or "CHECK-IN 14:00" (amber)

### TeamPropertyCard
- Collapsible card (tap to expand)
- Header: property name, worker count, task count
- Gap pills: red badges for missing coverage
- Lane dots: 3 circles (colored by coverage completeness)
- Expanded: 3-column matrix showing Primary/Backup per lane

### WorkerCard (Team context)
- Left: avatar circle (32px, colored bg, initials)
- Ring: colored by status (green/amber/red)
- Middle: name, role, current task
- Right: load number + status tag
- Variants: OK (no highlight), Warning (amber left border), Alert (red left border)

### ManagerTaskCard (Inline Expansion)
- Full task detail panel
- Property, kind, status, priority, assigned worker, due date
- Timeline: task events history
- Notes: manager notes with attribution
- Actions: Takeover/Execute | Reassign | Add Note
- On desktop: right panel (40% width)
- On mobile: pushes down below row or goes full-screen

### TurnoverChain
- Horizontal step visualization for same-property same-day flow
- Steps: Checkout → Clean → Check-In
- Each step: status indicator (done/active/blocked/pending)
- Arrows between steps
- Shows dependency chain at a glance
