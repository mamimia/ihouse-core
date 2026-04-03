# Check-Out Staff — Screen Map (V1)

**Role:** checkout
**Shell:** MobileStaffShell (dark theme)
**Theme:** Dark header, dark card backgrounds, signal-copper accents (departure identity)
**Navigation:** 4-tab BottomNav (Home, Check-out, Tasks, Settings)

> **Grounding key:** [BUILT] = confirmed in current product screenshots. [INFERRED] = derived from codebase reading. [V1 PROPOSAL] = new design direction.

---

## Screen Inventory (8 screens)

### S00 — Worker Home [BUILT]
**URL:** `/worker`
**Purpose:** Worker's landing page. Same shared shell as all single-role workers.
**Evidence:** Screenshot 22.26.47 — confirmed exact layout.

**Layout:**
```
┌─────────────────────────┐
│ App Header (dark)       │
│ "Home"        EN · Sign Out│
├─────────────────────────┤
│ WELCOME                 │
│ Hello, {name}  Check-out│
│                Staff    │
├─────────────────────────┤
│ MY STATUS               │
│ [📁 Open] [● Overdue]  │
│ [📅 Today]              │
│   8         0        0  │
├─────────────────────────┤
│ WORK                    │
│ ┌──────────────────────┐│
│ │ 📦 Go to Check-outs  ││
│ │    8 tasks waiting  > ││
│ └──────────────────────┘│
├─────────────────────────┤
│ NEXT UP                 │
│ ┌─ Task Card ──────────┐│
│ │ CHECKOUT       MEDIUM ││
│ │ Checkout Verification ││
│ │           Pending     ││
│ │ 🏠 Zen Pool Villa    ││
│ │ 📅 Sat, Mar 28       ││
│ │        [📍 Navigate]  ││
│ └──────────────────────┘│
├─────────────────────────┤
│ Bottom Nav (4 tabs)     │
│ Home*|Check-out|Tasks|⚙│
└─────────────────────────┘
```

---

### S01 — Departures List [BUILT]
**URL:** `/ops/checkout`
**Purpose:** "Who is leaving today?"
**Evidence:** Screenshot 22.27.48 — confirmed exact layout.

**Layout:**
```
┌─────────────────────────┐
│ Breadcrumb              │
│ Home > Operations >     │
│       Check-Out         │
├─────────────────────────┤
│ Check-out               │
│ WEDNESDAY, MARCH 25     │
│ Check-out               │
│ Departures · task world │
├─────────────────────────┤
│ Summary Strip (3 cards) │
│ [OVERDUE] [TODAY] [NEXT]│
│    0        0    ⏱in 2d│
│              checkout 11:00│
├─────────────────────────┤
│ UPCOMING                │
│ ┌─ Task Card ──────────┐│
│ │ Zen Pool Villa ⏱60h  ││
│ │ KPG-582       32m 11s││
│ │ 🔒Check-out 📅2026-03-28│
│ │              PENDING  ││
│ │ [Acknowledge]         ││
│ │ [Start Check-out →]   ││
│ │                    ⭐  ││
│ └──────────────────────┘│
├─────────────────────────┤
│ Bottom Nav (4 tabs)     │
│ Home|Check-out*|Tasks|⚙│
└─────────────────────────┘
```

**Confirmed from screenshots:**
- Summary strip: OVERDUE / TODAY / NEXT (with countdown and "checkout 11:00" deadline)
- Card design: Same dark card pattern as check-in, no left-accent border
- CTA: "Start Check-out →" in copper/brown color
- Two-step: [Acknowledge] + [Start Check-out →]
- Subtitle: "Departures · task world" confirms task-world sourcing

**[V1 PROPOSAL] Early checkout badge:** Amber "⚡ EARLY" badge on card if `is_early_checkout=true`.

---

### S02 — Step 1: Property Inspection
**Purpose:** Compare property condition to check-in state.

**Layout:**
```
┌─────────────────────────┐
│ Step Header (copper)    │
│ ← Back    Step 1 of 5   │
│ ██░░░░░░░ progress bar  │
├─────────────────────────┤
│                         │
│ (Early checkout banner  │
│  if applicable — amber) │
│                         │
│ Tab Bar:                │
│ [Reference][Check-in]   │
│ [Checkout*]             │
├─────────────────────────┤
│ Room Buttons:           │
│ [Living][Bedroom]       │
│ [Bathroom][Kitchen]     │
│ [Balcony][Other]        │
├─────────────────────────┤
│ Photo Grid:             │
│ Reference | Check-in    │
│ [ref img] | [c/i img]   │
│                         │
│ Checkout Capture:       │
│ [📷 Capture] or [✅]   │
├─────────────────────────┤
│ Inspection Notes:       │
│ [textarea]              │
│                         │
│ Inspection Status:      │
│ [✅ All Good]           │
│ [⚠️ Issues Found]      │
│                         │
│ [📍 Navigate to Prop]   │
│ [Continue → Meter]      │
├─────────────────────────┤
│ Bottom Nav              │
└─────────────────────────┘
```

**Three-tab photo comparison** is unique to checkout — shows reference (standard), check-in (arrival condition), and checkout (current capture) side by side.

---

### S03 — Step 2: Closing Meter
**Purpose:** Capture closing electricity reading, calculate usage.

**Key feature:** Live delta preview card:
```
┌─ Opening Meter (blue) ──┐
│ 📸 [thumbnail]  312 kWh │
│ Recorded: Dec 20        │
└──────────────────────────┘
┌─ Usage Preview (amber) ─┐
│ Usage: 48 kWh           │
│ Est. charge: THB 264    │
└──────────────────────────┘
```

Uses same OcrCaptureFlow component as check-in meter step.

---

### S04 — Step 3: Report Issues
**Purpose:** Document any property problems found during inspection.
**Conditional flow:** Shown if inspection = "Issues Found", skipped if "All Good".

**Layout:**
```
┌─────────────────────────┐
│ Step Header             │
│ ← Back    Step 3 of 5   │
├─────────────────────────┤
│                         │
│ (Previous issues shown  │
│  as red cards if any)   │
│                         │
│ Category: [damage ▼]    │
│ Severity: [MEDIUM ▼]    │
│ Description: [textarea] │
│                         │
│ [🚨 Report Issue]       │
│ (disabled if no desc)   │
│                         │
│ [Continue → Deposit]    │
│                         │
├─────────────────────────┤
│ Bottom Nav              │
└─────────────────────────┘
```

Categories: damage, cleanliness, missing_items, appliance, plumbing, electrical, other.

---

### S05 — Step 4: Deposit Resolution
**Purpose:** Calculate and resolve guest deposit.

**Layout:**
```
┌─────────────────────────┐
│ Step Header             │
│ ← Back    Step 4 of 5   │
├─────────────────────────┤
│                         │
│ ┌─ Deposit Held (gold)─┐│
│ │ THB 1,000             ││
│ └──────────────────────┘│
│                         │
│ ┌─ Electricity (blue) ─┐│
│ │ ⚡ 48 kWh usage       ││
│ │ "Auto-deducted"       ││
│ └──────────────────────┘│
│                         │
│ ┌─ Issues (red) ───────┐│
│ │ ⚠ 2 issues reported  ││
│ │ "Consider deduction"  ││
│ └──────────────────────┘│
│                         │
│ Action:                 │
│ (●) 💵 Full Return     │
│ ( ) 📉 Damage Deduction│
│                         │
│ (if deduction selected:)│
│ Amount: [___] (max 1000)│
│ Reason: [___]           │
│                         │
│ [Calculate & Continue →]│
│                         │
├─────────────────────────┤
│ Bottom Nav              │
└─────────────────────────┘
```

If no deposit on file: "✓ No deposit on file — skip to completion."

---

### S06 — Step 5: Checkout Summary
**Purpose:** Final review before completion.

Shows: guest, property, nights, early checkout context (if applicable), inspection status, closing meter, issues count, settlement breakdown (deposit held, electricity deduction, damage deduction, net return).

CTA: "Complete Checkout" (primary, copper color).

---

### S07 — Success
"✅ Check-out completed" + "Return to List" button.

---

## Screen Count: 8 screens (S00–S07)
- 1 home screen [BUILT]
- 1 departures list screen [BUILT]
- 5 checkout steps [BUILT — flow confirmed in code]
- 1 success screen [BUILT]

## Bottom Nav [BUILT]
4 tabs: Home (🏠) | Check-out (📦) | Tasks (✓) | Settings (⚙)

## Navigation Flow

```
S00 Home → S01 List → S02 Inspection → S03 Meter → S04 Issues (conditional)
  → S05 Deposit → S06 Summary → S07 Success → S01 List
```

All steps have ← Back. Issues step conditional on "⚠️ Issues Found" toggle.

---

## Key Difference from Check-In

| Aspect | Check-In | Check-Out |
|--------|----------|-----------|
| Accent color | deep-moss (#334036) | signal-copper (#B56E45) |
| Photo mode | Match to reference | Before/after comparison (3 tabs) |
| Meter | Opening reading | Closing reading + delta calculation |
| Financial | Deposit collection | Deposit resolution + settlement |
| Issue reporting | None | Category + severity + description |
| Completion | "InStay" + QR handoff | "Checked Out" + CLEANING task auto-created |
| Emotional tone | Welcoming | Verifying, closing |
