# Check-In & Check-Out (Combined) — Screen Map (V1)

**Role:** checkin_checkout (synthesized)
**Shell:** MobileStaffShell (dark theme)
**Theme:** Dark header, dark card backgrounds, dual-accent identity (deep-moss for arrivals, signal-copper for departures)
**Navigation:** 4-tab BottomNav (Today, Arrivals, Departures, Tasks)
**Character:** Dual-mode, schedule-aware, transition-focused. The only worker role that operates across two operational domains. The UI must keep arrival and departure work distinct while feeling like one coherent workspace.

> **Grounding key:** [BUILT] = confirmed in current product screenshots. [INFERRED] = derived from codebase reading. [V1 PROPOSAL] = new design direction.

---

## Screen Inventory (4 unique screens + inherited flows)

This role has 4 screens of its own (Home, Hub, Merged Tasks, Profile). All actual work happens inside the inherited check-in and check-out flows.

### S00 — Worker Home [BUILT]
**URL:** `/worker`
**Purpose:** Worker's landing page — separate from the hub.
**Evidence:** Screenshot 22.30.27 — confirmed exact layout.

**Layout:**
```
┌─────────────────────────┐
│ App Header (dark)       │
│ "Home"        EN · Sign Out│
├─────────────────────────┤
│ WELCOME                 │
│ Hello, {name} Check-in  │
│          & Check-out    │
├─────────────────────────┤
│ WORK                    │
│ ┌──────────────────────┐│
│ │ 🏠 Go to Check-in &  ││
│ │    Check-out          ││
│ │ Your combined         ││
│ │ operations hub      > ││
│ └──────────────────────┘│
├─────────────────────────┤
│ MY STATUS               │
│ [📁 Open] [● Overdue]  │
│ [📅 Today]              │
│   0         0        0  │
├─────────────────────────┤
│ Bottom Nav (4 tabs)     │
│ Today|Arrivals|Depart|Tasks│
└─────────────────────────┘
```

**Note from screenshot:** Home page has WORK section above MY STATUS (reversed order from other worker roles). No NEXT UP section visible.

---

### S01 — Operations Hub [BUILT]
**URL:** `/ops/checkin-checkout`
**Purpose:** "What's happening today across arrivals and departures?"
**Evidence:** Screenshot 22.28.41 — confirmed exact layout.

**Layout:**
```
┌─────────────────────────┐
│ Breadcrumb              │
│ Home > Operations >     │
│       Checkin Checkout   │
├─────────────────────────┤
│ Check-in & Check-out    │
│ WEDNESDAY, MARCH 25     │
│ Your Shifts             │
│ Check-ins (7 days) &    │
│ Check-outs (task world) │
├─────────────────────────┤
│                         │
│ ┌─ Check-in Block ─────┐│
│ │ 📋 Check-in          ││
│ │ Next 7 days·task world││
│ │                   10  ││
│ │ ⏱ Next arrival in    ││
│ │   15h 31m             ││
│ │                       ││
│ │ [Start Check-Ins      ││
│ │  (10 pending) →]      ││
│ │ (green CTA)           ││
│ └──────────────────────┘│
│                         │
│ ┌─ Check-out Block ────┐│
│ │ 🚪 Check-out          ││
│ │ Task world            ││
│ │          8 upcoming   ││
│ │ ⏱ Next checkout in 2d││
│ │                       ││
│ │ [Process Check-outs   ││
│ │  (8) →]               ││
│ │ (copper CTA)          ││
│ └──────────────────────┘│
│                         │
│ ┌─ Profile & Settings ─┐│
│ │ ⚙ Home·Sign out·     ││
│ │   Language           >││
│ └──────────────────────┘│
│                         │
├─────────────────────────┤
│ Bottom Nav (4 tabs)     │
│ Today*|Arrivals|Depart  │
│ |Tasks                  │
└─────────────────────────┘
```

**Confirmed from screenshot:**
- Title "Your Shifts" with subtitle "Check-ins (7 days) & Check-outs (task world)"
- Two operational blocks (not summary cards): Check-in block (green CTA) + Check-out block (copper CTA)
- Count displayed large: "10" for check-ins, "8 upcoming" for check-outs
- Countdown: "Next arrival in 15h 31m", "Next checkout in 2d"
- Profile & Settings row at bottom (not a card, a link row)
- Bottom nav: Today (📅 with date number) | Arrivals | Departures | Tasks

**[V1 PROPOSAL] Same-Day Turns section:**
When a property has both a departure and arrival on the same day, show a compact chain: `OUT 11:00 → CLEAN → IN 14:00`. This does NOT exist in current product but addresses the missing turnaround visualization.

**[V1 PROPOSAL] Urgency enhancements:**
- Departures block, any overdue: red accent, overdue count in red
- Departures block, imminent (<1h): amber countdown
- Arrivals block, imminent (<2h): amber countdown
- Both calm: standard accent colors (moss/copper)

---

### S02 — Merged Task List [BUILT]
**URL:** `/tasks` (with combined role context)
**Purpose:** "All my tasks — arrivals and departures — in one list."
**Evidence:** Screenshot 22.29.08 — confirmed mixed task list.

**Layout:**
```
┌─────────────────────────┐
│ App Header (dark)       │
│ "My Tasks"              │
│ Today · Wednesday, Mar 25│
├─────────────────────────┤
│ Tab Toggle:             │
│ [Pending] [Done]        │
├─────────────────────────┤
│ ┌─ Task Card ──────────┐│
│ │ Zen Pool Villa ⏱15h  ││
│ │ KPG-582       30m 52s││
│ │ 🔒Check-in 📅2026-03-26│
│ │           ACKNOWLEDGED││
│ │ [Start Check-in →]    ││
│ │                    ⭐  ││
│ └──────────────────────┘│
│ ┌─ Task Card ──────────┐│
│ │ Emuna Villa    ⏱60h  ││
│ │ KPG-588       30m 52s││
│ │ 🔒Check-out 📅2026-03-28│
│ │              PENDING  ││
│ │ [Acknowledge]         ││
│ │ [Start Check-out →]   ││
│ │                    ⭐  ││
│ └──────────────────────┘│
│ ┌─ Task Card ──────────┐│
│ │ Zen Pool Villa ⏱60h  ││
│ │ 🔒Check-out 📅2026-03-28│
│ │              PENDING  ││
│ │ [Acknowledge]         ││
│ │ [Start Check-out →]   ││
│ └──────────────────────┘│
│ (more cards...)         │
├─────────────────────────┤
│ Bottom Nav (4 tabs)     │
│ Today|Arrivals|Depart   │
│ |Tasks*                 │
└─────────────────────────┘
```

**Confirmed from screenshot:**
- Pending/Done tab toggle (same as single-role workers)
- Mixed check-in and check-out cards interleaved
- Check-in cards show 🔒Check-in badge, check-out cards show 🔒Check-out badge
- Same dark card pattern as other worker roles
- No separate filter chips for type — tasks are just interleaved
- Both types use Acknowledge + Start pattern

**[V1 PROPOSAL] Filter chips.** Add All/Arrivals/Departures filter chips for days with many mixed tasks. Not in current product.

---

### S03 — Profile
**URL:** `/worker` (via hub link)
**Purpose:** Shared worker profile with combined role display.

**Layout:**
```
┌─────────────────────────┐
│ App Header (dark)       │
│ "Profile"               │
├─────────────────────────┤
│                         │
│ [Avatar / Initials]     │
│ Name                    │
│ Role: Check-in &        │
│       Check-out Staff   │
│ Status: Active          │
│                         │
│ ── CAPABILITIES ────────│
│ [📋 Arrivals]           │
│ [🚪 Departures]         │
│ (both chips shown)      │
│                         │
│ ── ASSIGNED PROPERTIES ─│
│ [Villa Emuna]           │
│ [KPG Residence]         │
│ [Baan Suan]             │
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

**Unique to combined role:** Shows both capability chips (Arrivals + Departures) to make the dual-role explicit. Role label reads "Check-in & Check-out Staff" — not just "Worker".

---

## Inherited Flows (Not Re-Designed Here)

### Arrivals Tab → Check-In Flow
When the worker taps "Arrivals" in bottom nav or "View Arrivals →" on the hub:
- Enters the full CHECK_IN_STAFF flow (see `CHECK_IN_STAFF/01_screen_map.md`)
- 9 screens: S01 List → S02-S08 Wizard → S09 Success/QR
- Deep-moss accent throughout
- Bottom nav switches to show the 4-tab combined nav (not the check-in 3-tab nav)

### Departures Tab → Check-Out Flow
When the worker taps "Departures" in bottom nav or "View Departures →" on the hub:
- Enters the full CHECK_OUT_STAFF flow (see `CHECK_OUT_STAFF/01_screen_map.md`)
- 7 screens: S01 List → S02-S06 Steps → S07 Success
- Signal-copper accent throughout
- Bottom nav switches to show the 4-tab combined nav (not the checkout 3-tab nav)

**Critical UX requirement:** The bottom nav must remain the 4-tab combined nav regardless of which flow the worker is inside. This is how the combined role stays coherent — the worker can always switch between arrival work, departure work, and the hub via bottom nav.

---

## Navigation Flow

```
                    ┌─────────────┐
                    │  S01 Today  │
                    │    Hub      │
                    └──┬──────┬──┘
                       │      │
              ┌────────┘      └────────┐
              ▼                        ▼
     ┌────────────────┐      ┌─────────────────┐
     │ Arrivals Tab   │      │ Departures Tab  │
     │ (Check-In Flow)│      │ (Check-Out Flow)│
     │ 9 screens      │      │ 7 screens       │
     └────────────────┘      └─────────────────┘
              │                        │
              └────────┐  ┌────────────┘
                       ▼  ▼
                ┌──────────────┐
                │  S02 Tasks   │
                │  (merged)    │
                └──────────────┘
```

- Bottom nav: Today | Arrivals | Departures | Tasks (always visible, always 4 tabs)
- Hub cards link to Arrivals/Departures list screens
- Same-day turn cards link to the relevant departure first (OUT before IN)
- Tasks tap → enters check-in or check-out flow depending on task kind
- Profile accessible from hub card

---

## States Per Screen

### S01 Today Hub
| State | Visual |
|-------|--------|
| Loading | Centered spinner |
| No arrivals today | Arrivals card shows "No arrivals today" (moss, calm) |
| No departures today | Departures card shows "No departures today" (copper, calm) |
| Both empty | Both cards show empty state, no same-day turns section |
| Overdue departures | Departures card: red top border, "⚠ {n} overdue" |
| Same-day turn exists | Turn section visible with chain indicator |
| Multiple turns | Multiple chain rows in turn section |
| Countdown imminent | Countdown text switches to amber, then red at 0 |

### S02 Merged Task List
| State | Visual |
|-------|--------|
| Loading | Centered spinner |
| Empty | "No tasks assigned" (neutral icon) |
| Filter active | Active chip highlighted, list filtered |
| Mixed types | Cards interleaved with type badges and accent colors |
| All complete | Only completed section visible |

---

## Open Questions

### Q1: Bottom Nav Persistence
When the combined role worker enters the check-in flow (via Arrivals tab), does the bottom nav show the 4-tab combined nav or switch to the 3-tab check-in nav? Current code uses the combined nav from CHECKIN_CHECKOUT_BOTTOM_NAV. Design assumes this stays — the 4-tab nav is the combined role's identity.

### Q2: Same-Day Turn Section
The current hub has no turn visualization. Should V1 include the same-day turn section shown in this design? It requires cross-referencing arrival and departure tasks for the same property on the same day. The data is available (both task lists are fetched), but the linkage logic doesn't exist yet.

### Q3: Task List Type Badge
Should the merged task list show task type (CHECKIN/CHECKOUT) as a badge on every card, or only when filtering is set to "All"? When filtered to Arrivals-only, the type badge is redundant.

### Q4: Hub vs. List Decision
The hub shows summary cards (counts + next deadline). The worker must tap into Arrivals or Departures to see individual bookings. Should the hub also show the next 2-3 tasks inline (without requiring a tab switch), or keep the hub as a pure summary layer?

### Q5: Route Access Gap
Middleware allows `checkin_checkout` role only `/ops/checkin-checkout` and `/worker`. But the bottom nav links to `/ops/checkin` and `/ops/checkout`. Are these accessible? If middleware blocks them, the bottom nav is broken. This may be a real bug — needs verification.

---

## Screen Count: 4 unique screens (S00–S03) + inherited flows
- 1 home screen [BUILT]
- 1 operations hub [BUILT]
- 1 merged task list [BUILT]
- 1 profile [BUILT]
- Inherited: 9 check-in screens + 7 check-out screens (not re-designed here)

## Bottom Nav [BUILT]
4 tabs: Today (📅) | Arrivals (📋) | Departures (🚪) | Tasks (✓)

---

## Key Difference from Single-Role Workers

| Aspect | Check-In Staff | Check-Out Staff | Combined |
|--------|---------------|-----------------|----------|
| Home screen | Arrival list | Departure list | Summary hub (both) |
| Bottom nav | Home/Check-in/Tasks (3) | Home/Check-out/Tasks (3) | Today/Arrivals/Departures/Tasks (4) |
| Nav identity | Deep-moss | Signal-copper | Dual (moss + copper) |
| Task fetch | Single role query | Single role query | Parallel fetch + merge |
| Role in JWT | `checkin` | `checkout` | `checkin_checkout` (synthesized) |
| Work flow | Own wizard | Own flow | Delegates to both single-role flows |
| Turn awareness | None | None | Same-day turn section (proposed) |
