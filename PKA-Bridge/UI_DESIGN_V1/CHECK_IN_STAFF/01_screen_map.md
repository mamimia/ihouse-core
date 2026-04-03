# Check-In Staff — Screen Map (V1)

**Role:** checkin
**Shell:** MobileStaffShell (forced dark theme, safe area handling)
**Theme:** Dark header, dark card backgrounds, deep-moss accents (arrival identity)
**Navigation:** 4-tab BottomNav (Home, Check-in, Tasks, Settings)

> **Grounding key:** [BUILT] = confirmed in current product screenshots. [INFERRED] = derived from codebase reading. [V1 PROPOSAL] = new design direction.

---

## Screen Inventory (10 screens)

### S00 — Worker Home [BUILT]
**URL:** `/worker`
**Purpose:** Worker's landing page after login. Overview of status and quick access to work.
**Evidence:** Screenshot 22.22.02 — confirmed exact layout.

**Layout:**
```
┌─────────────────────────┐
│ App Header (dark)       │
│ "Home"        EN · Sign Out│
├─────────────────────────┤
│ WELCOME                 │
│ Hello, {name}  Check-in │
│                Staff    │
├─────────────────────────┤
│ MY STATUS               │
│ [📁 Open] [● Overdue]  │
│ [📅 Today]              │
│   9         0        0  │
├─────────────────────────┤
│ WORK                    │
│ ┌──────────────────────┐│
│ │ 📋 Go to Check-ins   ││
│ │    9 tasks waiting  > ││
│ └──────────────────────┘│
├─────────────────────────┤
│ NEXT UP                 │
│ ┌─ Task Card ──────────┐│
│ │ CHECKIN         HIGH  ││
│ │ Check-in Prep Ack'd  ││
│ │ 🏠 Zen Pool Villa    ││
│ │ 📅 Thu, Mar 26       ││
│ │        [📍 Navigate]  ││
│ └──────────────────────┘│
│ ┌─ Task Card ──────────┐│
│ │ CHECKIN         HIGH  ││
│ │ Check-in Prep Pending ││
│ │ 🏠 Emuna Villa       ││
│ │        [📍 Navigate]  ││
│ └──────────────────────┘│
├─────────────────────────┤
│ Bottom Nav (4 tabs)     │
│ Home*|Check-in|Tasks|⚙ │
└─────────────────────────┘
```

**Key observations from screenshot:**
- MY STATUS strip: 3 counters (Open/Overdue/Today) with colored icons
- WORK section: single CTA card, chevron right, task count subtitle
- NEXT UP: preview cards with priority badge (HIGH/MEDIUM), status, property, date, Navigate button
- Navigate button is pink/copper, opens maps

---

### S01 — Arrivals List [BUILT]
**URL:** `/ops/checkin`
**Purpose:** "What do I need to do?" — the worker's daily arrivals view.
**Evidence:** Screenshots 22.23.22 and 22.23.35 — confirmed exact layout.

**Layout:**
```
┌─────────────────────────┐
│ Breadcrumb              │
│ Home > Operations >     │
│       Check-In          │
├─────────────────────────┤
│ Check-in                │
│ WEDNESDAY, MARCH 25     │
│ Arrivals                │
│ Today + next 7 days     │
├─────────────────────────┤
│ Summary Strip (3 cards) │
│ [TODAY] [UPCOMING] [NEXT│
│   0       10     ⏱in   │
│                  15h36m │
│                 by 14:00│
├─────────────────────────┤
│ UPCOMING                │
│ ┌─ Task Card ──────────┐│
│ │ Zen Pool Villa  ⏱15h ││
│ │ KPG-582        36m38s││
│ │ 🔒Check-in 📅2026-03-26│
│ │               Upcoming││
│ │ [Start Check-in →]    ││
│ └──────────────────────┘│
│ ┌─ Task Card ──────────┐│
│ │ Emuna Villa    ⏱63h  ││
│ │ KPG-588        36m38s││
│ │ 🔒Check-in 📅2026-03-28│
│ │ CHECKIN_PREP—KPG-500  ││
│ │               Upcoming││
│ │ [Start Check-in →]    ││
│ │                    ⭐  ││
│ └──────────────────────┘│
├─────────────────────────┤
│ Bottom Nav (4 tabs)     │
│ Home|Check-in*|Tasks|⚙ │
└─────────────────────────┘
```

**Confirmed from screenshots:**
- Summary strip: TODAY / UPCOMING / NEXT (with countdown to specific time)
- Cards: Dark background, subtle border, rounded corners (~12px)
- Card content: Property name (bold) + countdown (right), KPG code (dimmed), type+date badges, task reference, status badge, action buttons
- Countdown format: precise "XXh XXm XXs" with "Upcoming" label
- Two-step flow: [Acknowledge] (outline) + [Start Check-in →] (green filled)
- Priority star (amber) at card's right edge
- **No left-accent border** in current product — cards are plain dark with subtle border

**[V1 PROPOSAL] Urgency enhancements:**
- Overdue: red card top-border + "+XX min" blinking timer
- Imminent (<30min): copper countdown, pulsing
- Approaching (30-60min): amber countdown
- Later today: standard
- Upcoming (future days): muted card

---

### S02 — Step 1: Arrival Confirmation
**Purpose:** Worker confirms guest arrival and reviews booking at a glance.

**Layout:**
```
┌─────────────────────────┐
│ Status Bar              │
├─────────────────────────┤
│ Step Header (dark)      │
│ ← Back    Step 1 of N   │
│ ████░░░░░ progress bar  │
├─────────────────────────┤
│ ░ Scrollable ░          │
│                         │
│ Property: Villa Emuna   │
│ Status: ● Ready         │
│ (or ⚠ Not Ready badge) │
│                         │
│ ┌─ Booking Block ──────┐│
│ │ Guest    Bon Voyage   ││
│ │ Guests   2            ││
│ │ Property Villa Emuna  ││
│ │ Check-in Wed Dec 20   ││
│ │ Check-out Sat Dec 23  ││
│ │ Nights   3            ││
│ │ Source   Airbnb       ││
│ │ Ref      ABCD-1234    ││
│ └──────────────────────┘│
│                         │
│ ┌─ Operator Note ──────┐│
│ │ ⚠ Late arrival...    ││
│ └──────────────────────┘│
│                         │
│ ┌─ Settlement Policy ──┐│
│ │ 💰 Deposit: THB 1000 ││
│ │ ⚡ Electricity: 5.5/kWh│
│ └──────────────────────┘│
│                         │
│ [📍 Navigate to Property]│
│ [Guest Arrived ✓]       │
│                         │
├─────────────────────────┤
│ Bottom Nav              │
└─────────────────────────┘
```

**Key design notes:**
- Property Ready/Not Ready badge is prominent (green/amber)
- Settlement Policy shown as informational banner (what this check-in involves)
- Navigation button uses Waze (mobile) or Google Maps (desktop)
- "Guest Arrived ✓" is the primary CTA (deep-moss color)

---

### S03 — Step 2: Walk-Through Photos
**Purpose:** Match current property condition to reference photos.

**Layout:**
```
┌─────────────────────────┐
│ Step Header             │
│ ← Back    Step 2 of N   │
│ ██████░░░ progress bar  │
├─────────────────────────┤
│ Counter: 2 of 4 captured│
├─────────────────────────┤
│ ░ Photo Grid ░          │
│                         │
│ ┌──────┬───────────────┐│
│ │ Ref  │ [📷 Capture]  ││
│ │ photo│               ││
│ │Living│               ││
│ └──────┴───────────────┘│
│ ┌──────┬───────────────┐│
│ │ Ref  │ [✅ Captured] ││
│ │ photo│ [Retake]      ││
│ │Bedrm │               ││
│ └──────┴───────────────┘│
│ ... more rooms ...      │
│                         │
│ [Continue (2/4) →]      │
│ ⚠ Not all matched      │
│                         │
├─────────────────────────┤
│ Bottom Nav              │
└─────────────────────────┘
```

**States:**
- No reference photos configured: "No reference photos configured. You may skip this step."
- All captured: "Continue →" (no warning)
- Partial: "Continue (X/Y) →" with amber warning

---

### S04 — Step 3: Electricity Meter (Conditional)
**Purpose:** Capture opening meter reading via OCR.
**Condition:** Only shown if `electricity_enabled` on property.

**Layout:**
```
┌─────────────────────────┐
│ Step Header             │
│ ← Back    Step 3 of N   │
├─────────────────────────┤
│                         │
│ "Capture the opening    │
│  meter reading"         │
│ ⚡ Rate: 5.5 THB/kWh   │
│                         │
│ ┌─ OCR Capture ────────┐│
│ │                       ││
│ │  [Camera View]        ││
│ │  or                   ││
│ │  [Review + Manual]    ││
│ │                       ││
│ │  Confidence: ●●●      ││
│ │  HIGH / MEDIUM / LOW  ││
│ │                       ││
│ └──────────────────────┘│
│                         │
│ [Complete] or [Skip]    │
│                         │
├─────────────────────────┤
│ Bottom Nav              │
└─────────────────────────┘
```

**OCR states:** Camera → Processing (6s timeout) → Review → Manual correction if low confidence

---

### S05 — Step 4: Guest Contact Info
**Purpose:** Capture phone/email for portal link delivery.

**Layout:**
```
┌─────────────────────────┐
│ Step Header             │
│ ← Back    Step 4 of N   │
├─────────────────────────┤
│                         │
│ "Capture guest contact  │
│  for portal link"       │
│                         │
│ Phone Number *          │
│ [+66 812 345 678]      │
│ ⚠ Phone is recommended │
│                         │
│ Email (optional)        │
│ [guest@example.com]     │
│                         │
│ [Continue →]            │
│                         │
├─────────────────────────┤
│ Bottom Nav              │
└─────────────────────────┘
```

---

### S06 — Step 5: Deposit Collection (Conditional)
**Purpose:** Record deposit payment.
**Condition:** Only shown if `deposit_enabled` on property.

**Layout:**
```
┌─────────────────────────┐
│ Step Header             │
│ ← Back    Step 5 of N   │
├─────────────────────────┤
│                         │
│ ┌─ Deposit Required ───┐│
│ │ THB 1,000             ││
│ │ (large, red/amber)    ││
│ └──────────────────────┘│
│                         │
│ Payment Method:         │
│ (●) 💵 Cash received   │
│ ( ) 🏦 Transfer received│
│ ( ) 💳 Card hold       │
│                         │
│ Note (optional)         │
│ [Any notes...]          │
│                         │
│ [Confirm & Record →]   │
│                         │
├─────────────────────────┤
│ Bottom Nav              │
└─────────────────────────┘
```

---

### S07 — Step 6: Guest Identity (OCR)
**Purpose:** Capture and verify guest identity document.

**Layout:**
```
┌─────────────────────────┐
│ Step Header             │
│ ← Back    Step 6 of N   │
├─────────────────────────┤
│                         │
│ Select document type:   │
│ [📘 Passport]           │
│ [🪪 National ID]       │
│ [🚗 Driving License]   │
│                         │
│ (after selection:)      │
│ ┌─ OCR Capture ────────┐│
│ │  [Camera View]        ││
│ │  (landscape/portrait  ││
│ │   based on doc type)  ││
│ └──────────────────────┘│
│                         │
│ (after capture:)        │
│ ┌─ Review Form ────────┐│
│ │ Full Name    [OCR]    ││
│ │ Doc Number   [OCR]    ││
│ │ DOB          [OCR]    ││
│ │ Nationality  [OCR]    ││
│ │ Expiry       [OCR]    ││
│ │                       ││
│ │ ⚠ Low confidence on: ││
│ │   Doc Number (72%)    ││
│ └──────────────────────┘│
│                         │
│ [Complete] or [Skip]    │
│                         │
├─────────────────────────┤
│ Bottom Nav              │
└─────────────────────────┘
```

---

### S08 — Step 7: Complete Check-in (Summary)
**Purpose:** Final review before marking guest as checked in.

**Layout:**
```
┌─────────────────────────┐
│ Step Header             │
│ ← Back    Step 7 of N   │
├─────────────────────────┤
│                         │
│ 🏠 Ready to complete    │
│ "This will mark the     │
│  booking as InStay and  │
│  the property as        │
│  Occupied."             │
│                         │
│ ┌─ Summary ────────────┐│
│ │ Guest       Bon V.    ││
│ │ Property    Emuna     ││
│ │ Walk-through 4/4      ││
│ │ Meter       312 kWh   ││
│ │ Contact     +66...    ││
│ │ Deposit     THB 1000  ││
│ │             Cash      ││
│ │ Passport    AB123456  ││
│ └──────────────────────┘│
│                         │
│ [✅ Complete Check-in]  │
│                         │
├─────────────────────────┤
│ Bottom Nav              │
└─────────────────────────┘
```

---

### S09 — Success: QR Handoff
**Purpose:** Deliver guest portal access.

**Layout:**
```
┌─────────────────────────┐
│ Status Bar              │
├─────────────────────────┤
│ Success Header (green)  │
│ ✅ Check-in Complete    │
│ "Guest is now checked   │
│  in at Villa Emuna"     │
├─────────────────────────┤
│                         │
│ ┌─ QR Box ─────────────┐│
│ │  [QR CODE IMAGE]      ││
│ │  Guest Portal QR      ││
│ │  "Show this to guest" ││
│ └──────────────────────┘│
│                         │
│ "Guest scans → opens    │
│  stay portal"           │
│                         │
│ [📱 Send via SMS]       │
│ [📧 Send via Email]     │
│                         │
│ (after sending:)        │
│ ✅ Portal link sent     │
│                         │
│ [Done — Return to       │
│  Arrivals]              │
│                         │
├─────────────────────────┤
│ Bottom Nav              │
└─────────────────────────┘
```

---

## Screen Count: 10 screens (S00–S09)
- 1 home screen [BUILT]
- 1 arrivals list screen [BUILT]
- 7 wizard steps (5 always + 2 conditional) [BUILT — wizard flow confirmed in code]
- 1 success screen [BUILT — QR delivery confirmed in code]

## Bottom Nav [BUILT]
4 tabs: Home (🏠) | Check-in (📋) | Tasks (✓) | Settings (⚙)
