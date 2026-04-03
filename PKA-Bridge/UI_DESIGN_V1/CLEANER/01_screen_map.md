# Cleaner — Screen Map (V1)

**Role:** cleaner
**Shell:** MobileStaffShell (dark theme)
**Theme:** Dark header, dark card backgrounds, deep-moss accents (completion/readiness identity)
**Navigation:** 4-tab BottomNav (Home, Cleaner, Tasks, Settings)
**Character:** Spatial, progress-driven, evidence-based. The most tactile worker UI.

> **Grounding key:** [BUILT] = confirmed in current product screenshots. [INFERRED] = derived from codebase reading. [V1 PROPOSAL] = new design direction.

---

## Screen Inventory (6 screens)

### S00 — Worker Home [BUILT]
**URL:** `/worker`
**Purpose:** Worker's landing page. Same shared shell as all single-role workers.
**Evidence:** Screenshot 22.18.48 — confirmed exact layout.

**Layout:**
```
┌─────────────────────────┐
│ App Header (dark)       │
│ "Home"        EN · Sign Out│
├─────────────────────────┤
│ WELCOME                 │
│ Hello, {name}  Cleaner  │
├─────────────────────────┤
│ MY STATUS               │
│ [📁 Open] [● Overdue]  │
│ [📅 Today]              │
│   9         0        0  │
├─────────────────────────┤
│ WORK                    │
│ ┌──────────────────────┐│
│ │ 🧹 Go to Cleaning    ││
│ │    9 tasks waiting  > ││
│ └──────────────────────┘│
├─────────────────────────┤
│ NEXT UP                 │
│ ┌─ Task Card ──────────┐│
│ │ CLEANER        MEDIUM ││
│ │ Cleaning   Acknowledged│
│ │ 🏠 Emuna Villa       ││
│ │ 📅 Sat, Mar 28       ││
│ │        [📍 Navigate]  ││
│ └──────────────────────┘│
├─────────────────────────┤
│ Bottom Nav (4 tabs)     │
│ Home*|Cleaner|Tasks|⚙  │
└─────────────────────────┘
```

---

### S01 — Today's Tasks (List) [BUILT]
**URL:** `/ops/cleaner`
**Purpose:** "Which property do I clean next?"
**Evidence:** Screenshot 22.20.46 — confirmed exact layout.

**Layout:**
```
┌─────────────────────────┐
│ Breadcrumb              │
│ Home > Operations >     │
│       Cleaner           │
├─────────────────────────┤
│ Cleaning                │
│ WEDNESDAY, MARCH 25     │
│ Today's Tasks           │
│ Cleaning tasks assigned │
│ to you                  │
├─────────────────────────┤
│ Summary Strip (3 cards) │
│ [TASKS] [DONE]  [NEXT]  │
│  10       0    ⏱in 2d  │
│              clean by   │
│              10:00      │
├─────────────────────────┤
│ UPCOMING                │
│ ┌─ Task Card ──────────┐│
│ │ Zen Pool Villa ⏱59h  ││
│ │ KPG-582       39m 14s││
│ │ 🧹Cleaning 📅2026-03-28│
│ │              PENDING  ││
│ │ [Acknowledge]         ││
│ │ [Start Cleaning →]    ││
│ │                    ⭐  ││
│ └──────────────────────┘│
├─────────────────────────┤
│ Bottom Nav (4 tabs)     │
│ Home|Cleaner*|Tasks|⚙  │
└─────────────────────────┘
```

**Confirmed from screenshots:**
- Summary strip: TASKS / DONE / NEXT (with countdown)
- Cards: Same dark card pattern, no left-accent border
- Task references visible: "Pre-arrival cleaning for ICAL-36ff7d9905e0" — includes booking source
- CTA: "Start Cleaning →" in green
- Two-step: [Acknowledge] + [Start Cleaning →]

**[V1 PROPOSAL] Card enhancements:**
- Room/item count on card: "5 rooms · 6 photos" (not in current screenshots)
- In-progress cards show partial completion: "12/21 items · 3/6 📷" (not in current screenshots)
- Cleaning window shown instead of just countdown (not in current screenshots)

---

### S02 — Task Detail
**Purpose:** Task overview before starting the clean.

**Layout:**
```
┌─────────────────────────┐
│ Back Header → List      │
│ "Villa Emuna"           │
├─────────────────────────┤
│                         │
│ ┌─ Info Block ─────────┐│
│ │ Property  Villa Emuna ││
│ │ Property ID  EMUNA-01 ││
│ │ Due Date   Apr 3      ││
│ │ Task       Cleaning   ││
│ └──────────────────────┘│
│                         │
│ (Description callout if │
│  present — sage color)  │
│                         │
│ [Start Cleaning 🧹]    │
│  or                     │
│ [Resume Cleaning →]     │
│                         │
│ [📍 Navigate to Property]│
│                         │
├─────────────────────────┤
│ Bottom Nav              │
└─────────────────────────┘
```

---

### S03 — Active Checklist (Core Screen)
**Purpose:** The cleaning workspace. This is where the cleaner spends most of their time.

**Layout:**
```
┌─────────────────────────┐
│ Back Header → Detail    │
│ "Villa Emuna"           │
├─────────────────────────┤
│ Progress Bars (3)       │
│ ████████░░ Items 17/21  │
│ ████░░░░░░ Photos 3/6   │
│ ██████████ Supplies 7/7 │
├─────────────────────────┤
│ ░ Checklist Content ░   │
│                         │
│ ── BEDROOM ─────────────│
│ [✓] Change bed sheets   │
│ [✓] Replace pillowcases │
│ [ ] Dust surfaces       │
│ [✓] Vacuum floor        │
│ [ ] Empty trash    [📷] │
│                         │
│ ── BATHROOM ────────────│
│ [✓] Clean toilet        │
│ [ ] Clean shower   [📷] │
│ [ ] Mirror & sink  [📷] │
│ [✓] Replace towels      │
│ [ ] Check soap/shampoo  │
│ [✓] Mop floor           │
│                         │
│ ── KITCHEN ─────────────│
│ (items...)              │
│                         │
│ ── LIVING ROOM ─────────│
│ (items...)              │
│                         │
│ ── EXTERIOR ────────────│
│ (items...)              │
│                         │
│ ═══ SUPPLY CHECK ═══════│
│ Sheets      [ok ✅]     │
│ Towels      [ok ✅]     │
│ Soap        [low ⚠️]   │
│ Shampoo     [ok ✅]     │
│ Toilet Paper[ok ✅]     │
│ Trash Bags  [ok ✅]     │
│ Cleaning Sup[ok ✅]     │
│                         │
│ ═══ ISSUE REPORTING ════│
│ [🚨 Report Issue]       │
│ (expands inline form)   │
│                         │
│ ── Completion Gate ─────│
│ [✅ Mark as Ready]      │
│  or                     │
│ [🔒 Complete All First] │
│ (disabled if gate fails)│
│                         │
├─────────────────────────┤
│ Bottom Nav              │
└─────────────────────────┘
```

**Design priorities for this screen:**
1. **Room grouping is spatial.** Each room header is a landmark. Worker scrolls through rooms.
2. **Progress bars at top.** Three bars always visible: Items, Photos, Supplies. Worker always knows how close to done.
3. **Photo capture inline.** Camera button [📷] next to items that require photos. Shows [📷 ✓] when taken.
4. **Supply cycling is simple.** Tap to cycle: unchecked → ok → low → empty. Color-coded.
5. **Issue reporting collapses.** Doesn't clutter the checklist unless worker needs it.
6. **Completion gate is honest.** Button disabled with clear reason until all 3 flags are green.

---

### S04 — Complete Confirmation
**Purpose:** Final review before marking property as ready.

**Layout:**
```
┌─────────────────────────┐
│ Back Header → Checklist │
│ "Ready to Submit"       │
├─────────────────────────┤
│                         │
│ ┌─ Summary Block ──────┐│
│ │ Property  Villa Emuna ││
│ │ Checklist 21/21 ✓    ││
│ │ Photos    6/6 ✓      ││
│ │ Supplies  All OK ✓   ││
│ └──────────────────────┘│
│                         │
│ [✅ Mark as Ready]      │
│                         │
├─────────────────────────┤
│ Bottom Nav              │
└─────────────────────────┘
```

---

### S05 — Success (Property Ready)
**Purpose:** The payoff. This should feel satisfying.

**Layout:**
```
┌─────────────────────────┐
│                         │
│      ✅                 │
│                         │
│  Cleaning Complete      │
│                         │
│  Villa Emuna is now     │
│  Ready                  │
│                         │
│ (or: "Ready with Issues"│
│  if open issues exist)  │
│                         │
│ [Done — Return to Tasks]│
│                         │
├─────────────────────────┤
│ Bottom Nav              │
└─────────────────────────┘
```

**Emotional design:** This is the most satisfying completion screen in the system. Large green check, clear "Ready" status. The cleaner's work directly produces a tangible result: a property is ready for the next guest.

If issues were reported: amber variant with "Ready with Issues" and note about open problems.

---

## Screen Count: 6 screens (S00–S05)
- 1 home screen [BUILT]
- 1 task list screen [BUILT]
- 1 task detail screen [INFERRED from code]
- 1 active checklist screen [BUILT — CleanerWizard confirmed in code]
- 1 completion confirmation [INFERRED]
- 1 success screen [INFERRED]

## Bottom Nav [BUILT]
4 tabs: Home (🏠) | Cleaner (🧹) | Tasks (✓) | Settings (⚙)

## Navigation Flow

```
S00 Home → S01 List → S02 Detail → S03 Checklist → S04 Complete → S05 Success → S01 List
                         ↑ Resume (if IN_PROGRESS)
```

- S02 → S03: "Start Cleaning" or "Resume Cleaning"
- S03 → S04: "Mark as Ready" (only if gate passes)
- S04 → S05: "Mark as Ready" (API call)
- S05 → S01: "Done — Return to Tasks"
- All screens have ← Back to previous

---

## Open Questions

### Q1: Room Navigation
Currently rooms are scroll sections on one long screen. Should there be a room selector/tab bar at the top for quick jumping?

### Q2: Photo Grid vs. Inline
Photos are captured inline next to checklist items. Should there also be a "photo gallery" view showing all captured photos for review before completion?

### Q3: Supply Low/Empty Actions
When supplies are marked "low" or "empty", should the cleaner see a "Request restock" button or just log the status?

### Q4: Time Tracking
Should the system track cleaning start/end time for performance metrics? Currently no timestamps captured.

### Q5: Partial Save Indicator
State persists to DB, but the worker doesn't see "Saved" indicators. Should there be a subtle auto-save confirmation?
