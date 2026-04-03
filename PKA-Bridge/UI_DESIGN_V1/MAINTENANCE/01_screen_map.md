# Maintenance — Screen Map (V1)

**Role:** maintenance
**Shell:** MobileStaffShell (dark theme)
**Theme:** Dark header, dark card backgrounds, amber/red urgency accents (priority-driven identity)
**Navigation:** 3-tab BottomNav (Home, Maintenance, Tasks) — possibly 4 with Settings (not clearly visible in screenshots)
**Character:** Issue-driven, priority-led, evidence-based. The most reactive worker UI — jobs arrive by urgency, not schedule.

> **Grounding key:** [BUILT] = confirmed in current product screenshots. [INFERRED] = derived from codebase reading. [V1 PROPOSAL] = new design direction.

> **Screenshot limitation:** All 3 maintenance screenshots show EMPTY states (no open issues, no pending tasks). The populated card layout, SLA visualization, and category display are NOT visible in screenshots. They are [INFERRED] from codebase reading.

---

## Screen Inventory (7 screens)

### S00 — Worker Home [BUILT]
**URL:** `/worker`
**Purpose:** Worker's landing page. Same shared shell as all single-role workers.
**Evidence:** Screenshot 22.33.20 — confirmed exact layout.

**Layout:**
```
┌─────────────────────────┐
│ App Header (dark)       │
│ "Home"        EN · Sign Out│
├─────────────────────────┤
│ WELCOME                 │
│ Hello, {name} Maintenance│
├─────────────────────────┤
│ MY STATUS               │
│ [📁 Open] [● Overdue]  │
│ [📅 Today]              │
│   0         0        0  │
├─────────────────────────┤
│ WORK                    │
│ ┌──────────────────────┐│
│ │ 🔧 Go to Maintenance ││
│ │    No open tasks    > ││
│ └──────────────────────┘│
├─────────────────────────┤
│ (no NEXT UP when empty) │
├─────────────────────────┤
│ Bottom Nav              │
│ Home*|Maintenance|Tasks │
└─────────────────────────┘
```

---

### S01 — Job Queue (List) [BUILT — empty state confirmed, populated state INFERRED]
**URL:** `/ops/maintenance`
**Purpose:** "What needs fixing, and how urgent is it?"
**Evidence:** Screenshot 22.33.29 — empty state confirmed. Summary strip labels confirmed.

**Layout:**
```
┌─────────────────────────┐
│ App Header (dark)       │
│ "Maintenance"           │
├─────────────────────────┤
│ Summary Strip [BUILT]   │
│ [OPEN ISSUES][CRITICAL] │
│ [TASKS]                 │
│   4          1       2  │
├─────────────────────────┤
│ ░ Job List ░            │
│                         │
│ ── CRITICAL (red) ──────│
│ ┌─ Job Card (red) ─────┐│
│ │▌ Pool pump failure    ││
│ │  🏠 Villa Emuna       ││
│ │  ⚠ CRITICAL — SLA:4m ││
│ │  Category: pool       ││
│ │  [Start Job]          ││
│ └──────────────────────┘│
│                         │
│ ── OPEN ────────────────│
│ ┌─ Job Card (amber) ───┐│
│ │▌ AC not cooling       ││
│ │  🏠 KPG Residence     ││
│ │  🔧 Reported 2h ago  ││
│ │  Category: ac_heating ││
│ │  [Acknowledge]        ││
│ └──────────────────────┘│
│ ┌─ Job Card (blue) ────┐│
│ │▌ Leaking faucet       ││
│ │  🏠 Baan Suan         ││
│ │  🔧 Reported 45m ago ││
│ │  Category: plumbing   ││
│ │  [Acknowledge]        ││
│ └──────────────────────┘│
│                         │
│ ── IN PROGRESS ─────────│
│ ┌─ Job Card (moss) ────┐│
│ │▌ Replace ceiling fan  ││
│ │  🏠 Baan Suan         ││
│ │  In progress · 1h 20m ││
│ │  [Resume →]           ││
│ └──────────────────────┘│
│                         │
│ ── RESOLVED TODAY ──────│
│ ┌─ Done Card (dim) ────┐│
│ │  ✓ Fix door lock      ││
│ │  Resolved · 09:45     ││
│ └──────────────────────┘│
│                         │
├─────────────────────────┤
│ Bottom Nav              │
│ Home | Maintenance*     │
│ | Tasks                 │
└─────────────────────────┘
```

**Section ordering:** CRITICAL first (always top), then OPEN (by age, oldest first), then IN PROGRESS, then RESOLVED TODAY.

**Card features unique to maintenance:**
- IssueAgeChip: live SLA countdown for CRITICAL, elapsed time for others
- Category badge with icon (pool, plumbing, electrical, etc.)
- Left accent color by priority: red (CRITICAL), amber (HIGH), blue (MEDIUM), gray (LOW)
- CRITICAL cards bypass acknowledge — show "Start Job" directly
- Non-critical cards require "Acknowledge" before "Start Job" becomes available

**SLA urgency (left accent + chip):**
- CRITICAL + SLA exceeded: red accent, blinking chip "⚠ CRITICAL — SLA exceeded +{elapsed}"
- CRITICAL + SLA active: red accent, pulsing chip "⚠ CRITICAL — SLA: {countdown}"
- HIGH (acknowledged, nearing 1h): amber accent
- MEDIUM: blue accent
- LOW: gray accent

---

### S02 — Job Detail
**Purpose:** Full issue context before starting work.

**Layout:**
```
┌─────────────────────────┐
│ Back Header → List      │
│ "Pool pump failure"     │
├─────────────────────────┤
│                         │
│ ┌─ Priority Banner ────┐│
│ │ ⚠ CRITICAL            ││
│ │ SLA: 3m remaining     ││
│ └──────────────────────┘│
│                         │
│ ┌─ Info Block ─────────┐│
│ │ Property  Villa Emuna ││
│ │ Category  Pool        ││
│ │ Severity  Urgent      ││
│ │ Reported  12:34 today ││
│ │ Reporter  Cleaner     ││
│ └──────────────────────┘│
│                         │
│ ┌─ Description ────────┐│
│ │ "Pool pump making     ││
│ │  loud grinding noise, ││
│ │  water not circulating││
│ │  properly."           ││
│ └──────────────────────┘│
│                         │
│ ┌─ Before Photos ──────┐│
│ │ [📷][📷] (from report)││
│ │ (tap to zoom)         ││
│ └──────────────────────┘│
│                         │
│ ┌─ Property Access ────┐│
│ │ 🔑 Access Code: 4521  ││
│ │ [📍 Navigate (Waze)] ││
│ │ [📞 Call Manager]     ││
│ └──────────────────────┘│
│                         │
│ [Start Job 🔧]          │
│  or                     │
│ [Resume Job →]          │
│                         │
├─────────────────────────┤
│ Bottom Nav              │
└─────────────────────────┘
```

**Key elements:**
- Priority banner at top — always visible, color-coded, with live SLA countdown for CRITICAL
- Before photos from problem report shown inline (tap to zoom full-screen)
- Access code displayed prominently (not buried in copilot)
- Navigation and call buttons for field access
- Description block shows full reporter text

---

### S03 — Active Work
**Purpose:** The workspace. Worker documents their fix here.

**Layout:**
```
┌─────────────────────────┐
│ Back Header → Detail    │
│ "Pool pump failure"     │
├─────────────────────────┤
│                         │
│ ┌─ Issue Summary (dim) ┐│
│ │ Pool · Villa Emuna    ││
│ │ "Pool pump grinding   ││
│ │  noise, no circ..."   ││
│ └──────────────────────┘│
│                         │
│ ┌─ SLA Status ─────────┐│
│ │ ⚠ CRITICAL — SLA:2m  ││
│ │ (or: 🔧 Working 45m) ││
│ └──────────────────────┘│
│                         │
│ ── BEFORE EVIDENCE ─────│
│ [📷][📷] (from report)  │
│ (read-only thumbnails)  │
│                         │
│ ── WORK LOG ────────────│
│ ┌─ Notes ──────────────┐│
│ │ [textarea]            ││
│ │ "What did you do?     ││
│ │  What was the issue?" ││
│ └──────────────────────┘│
│                         │
│ ── AFTER EVIDENCE ──────│
│ [📷 Take After Photo]   │
│ (captured photos shown  │
│  as thumbnails below)   │
│ [📷✓][📷✓]              │
│                         │
│ ── COMPLETION ──────────│
│ [✅ Complete & Resolve]  │
│                         │
│ ── OR ──────────────────│
│ [⚠ Cannot Complete]     │
│ (expand blocked form)   │
│                         │
│  ┌─ Blocked Form ──────┐│
│  │ Reason: [dropdown]   ││
│  │  · Parts needed      ││
│  │  · Need specialist   ││
│  │  · Access blocked    ││
│  │  · Waiting for guest ││
│  │    to vacate         ││
│  │  · Other             ││
│  │ Notes: [textarea]    ││
│  │ [Submit Blocked]     ││
│  └─────────────────────┘│
│                         │
│ [📞 Call Manager]        │
│                         │
├─────────────────────────┤
│ Bottom Nav              │
└─────────────────────────┘
```

**Design priorities for this screen:**
1. **Issue context stays visible.** Summary and SLA at top — worker never forgets what they're fixing or how urgent it is.
2. **Before photos shown read-only.** Worker sees what was reported, captures "after" evidence of their fix.
3. **Work notes are freeform.** No rigid structure — maintenance work is unpredictable.
4. **"Cannot Complete" is a first-class action.** Not hidden. Expands inline with structured reason dropdown + notes. Creates a formal blocked state the manager can see and act on.
5. **Call Manager always available.** Escalation without leaving the work screen.
6. **SLA countdown persists in work view.** Worker always knows time pressure.

---

### S04 — Blocked Confirmation
**Purpose:** Acknowledge that the job has been flagged as blocked.

**Layout:**
```
┌─────────────────────────┐
│                         │
│      ⚠️                 │
│                         │
│  Job Flagged as Blocked │
│                         │
│  "Pool pump failure"    │
│  Villa Emuna            │
│                         │
│  Reason: Parts needed   │
│                         │
│  Your manager has been  │
│  notified.              │
│                         │
│ [Done — Return to Jobs] │
│                         │
├─────────────────────────┤
│ Bottom Nav              │
└─────────────────────────┘
```

**Note:** This screen addresses the missing "Cannot Complete" workflow identified in system reality. The job stays in the queue with a BLOCKED visual state (amber accent, dashed border) until the manager resolves it.

---

### S05 — Complete Confirmation
**Purpose:** The payoff — issue resolved, evidence captured.

**Layout:**
```
┌─────────────────────────┐
│                         │
│      ✅                 │
│                         │
│  Issue Resolved         │
│                         │
│  "Pool pump failure"    │
│  Villa Emuna            │
│                         │
│  Time on job: 1h 20m    │
│                         │
│ [Done — Return to Jobs] │
│                         │
├─────────────────────────┤
│ Bottom Nav              │
└─────────────────────────┘
```

**Emotional design:** Satisfying but understated. Maintenance completion is relief, not celebration. Clean confirmation with time-on-job as operational feedback (even though formal time tracking doesn't exist yet, the system knows when the job was started and completed).

---

### S06 — Profile
**Purpose:** Shared worker profile.

**Layout:**
```
┌─────────────────────────┐
│ App Header (dark)       │
│ "Profile"               │
├─────────────────────────┤
│                         │
│ [Avatar / Initials]     │
│ Name                    │
│ Role: Maintenance Staff │
│ Status: Active          │
│                         │
│ ── ASSIGNED PROPERTIES ─│
│ [Villa Emuna]           │
│ [KPG Residence]         │
│ [Baan Suan]             │
│                         │
│ ── SPECIALTY ───────────│
│ [Plumbing] [Electrical] │
│ [General]               │
│                         │
│ ── NOTIFICATIONS ───────│
│ LINE: Connected ✓       │
│ Phone: +66...           │
│                         │
│ ── SESSION ─────────────│
│ Logged in as: somchai   │
│ [Log Out]               │
│                         │
├─────────────────────────┤
│ Bottom Nav              │
└─────────────────────────┘
```

**Unique to maintenance:** Specialty chips shown. The system maps issue categories to specialties (pool, plumbing, electrical, furniture, gardening, general). Profile reflects which specialties this worker handles.

---

## Screen Count: 7 screens (S00–S06)
- 1 home screen [BUILT]
- 1 job queue list [BUILT — empty state confirmed, populated INFERRED]
- 1 job detail [INFERRED from code]
- 1 active work screen [INFERRED from code]
- 1 blocked confirmation [V1 PROPOSAL — "Cannot Complete" doesn't exist in current product]
- 1 complete confirmation [INFERRED]
- 1 profile [BUILT — shared worker profile shell]

## Bottom Nav [BUILT — screenshots show 3 tabs visible]
3-4 tabs: Home (🏠) | Maintenance (🔧) | Tasks (✓) | possibly Settings (⚙)

## Navigation Flow

```
S00 Home → S01 Job Queue → S02 Job Detail → S03 Active Work → S05 Complete → S01
                                                   ↓
                                             S04 Blocked → S01
```

- S01 → S02: Tap any job card
- S02 → S03: "Start Job" or "Resume Job"
- S03 → S05: "Complete & Resolve" (API: resolve problem report + complete task)
- S03 → S04: "Cannot Complete" → "Submit Blocked"
- S04 → S01: "Done — Return to Jobs"
- S05 → S01: "Done — Return to Jobs"
- All screens have ← Back to previous
- Profile accessible from Home tab

---

## States Per Screen

### S01 Job Queue
| State | Visual |
|-------|--------|
| Loading | Centered spinner |
| Empty [BUILT] | Green checkmark icon ✅ + "No open issues" (centered, dark background) |
| All resolved | Only RESOLVED TODAY section visible, summary strip shows 0/0/0 |
| Critical present | CRITICAL section pinned to top, red summary card pulses |
| SLA exceeded | Card chip blinks, red accent intensifies |

### S02 Job Detail
| State | Visual |
|-------|--------|
| No before photos | "No photos attached to report" (gray placeholder) |
| No access code | Access code row hidden, navigate + call still shown |
| Already in progress | CTA reads "Resume Job →" instead of "Start Job" |
| CRITICAL | Priority banner red with live countdown |
| Non-critical | Priority banner shows severity badge, no countdown |

### S03 Active Work
| State | Visual |
|-------|--------|
| Fresh start | Empty notes, no after photos, both CTAs available |
| Notes entered | "Complete & Resolve" stays available |
| After photo taken | Thumbnail appears below capture button |
| Blocked form open | "Cannot Complete" expanded, completion CTA dimmed |
| SLA exceeded while working | SLA chip switches to "SLA exceeded +{elapsed}", red |

### S04 Blocked
| State | Visual |
|-------|--------|
| Confirmed | Amber icon, reason displayed, manager notified message |

### S05 Complete
| State | Visual |
|-------|--------|
| Resolved | Green check, time-on-job shown |

---

## Open Questions

### Q1: After Photo Requirement
Currently after photos are optional (code requires notes only for completion). Should V1 require at least one after photo before "Complete & Resolve" becomes active? This would improve evidence quality but could block workers in situations where a photo isn't meaningful (e.g., "reset breaker").

### Q2: Before/After Comparison View
The system has before photos (from report) and after photos (from worker). Should there be a side-by-side comparison view, or is showing them in sequence (before read-only above, after capture below) sufficient for V1?

### Q3: Blocked State Lifecycle
When a job is flagged as "Cannot Complete", who unblocks it? Does the manager reassign, or can the original worker pick it back up? What status does the problem report enter?

### Q4: Job History
Should the maintenance worker see a history of their resolved jobs (past 7 days, past 30 days)? Currently RESOLVED TODAY is shown, but older history is not. This could help with recurring issues at the same property.

### Q5: Parts and Materials
No parts/materials tracking exists. Should V1 include even a simple "Parts used" text field on the work screen, or defer entirely to V2?

### Q6: Multi-Issue Properties
If a property has multiple open issues, should the job queue show them as separate cards (current behavior — one card per issue) or group them under the property with a count badge?

---

## Key Difference from Other Worker Roles

| Aspect | Cleaner | Maintenance |
|--------|---------|-------------|
| Work structure | Checklist (21 items, room-grouped) | Freeform (notes + photos) |
| Trigger | Scheduled task | Reactive issue report |
| Completion gate | 3-flag (items + photos + supplies) | Notes required, photos optional |
| SLA pressure | Cleaning window (soft) | CRITICAL 5-min / MEDIUM 1-hour (hard) |
| Urgency visual | Window-based accent | Priority-based accent + live countdown |
| Blocked flow | None (force-complete option) | "Cannot Complete" with structured reasons |
| Identity color | Deep-moss (readiness) | Amber/Red (urgency) |
