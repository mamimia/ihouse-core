# Guest Portal — Screen Map (V1)

**Surface:** Guest Portal (public, token-gated)
**Shell:** None — standalone page, no sidebar, no bottom nav
**Theme:** [V1 PROPOSAL] Warm/light palette — sand, stone, muted green, soft gold. NOT the dark worker theme.
**Character:** Calm, premium, hospitality-first. The guest's digital home during their stay.

> **Grounding key:** [BUILT] = confirmed in current product/screenshots. [INFERRED] = derived from codebase reading. [V1 PROPOSAL] = new design direction.

> **Critical rule:** No internal identifiers ever. No property codes. No booking refs. No task IDs. No system status strings. Human names only.

---

## Portal States (Contextual)

The guest portal is ONE URL (`/guest/[token]`) but its content should adapt to booking lifecycle:

| State | When | What Changes |
|-------|------|-------------|
| **Pre-Arrival** | Before check-in date | Self check-in gate shown, pre-arrival form, no access details yet |
| **In-Stay** [PRIMARY] | After check-in, before checkout | Full portal: essentials, house guide, help, extras, stay info |
| **Near-Departure** | Within 24h of checkout | Departure block appears, checkout guidance prominent |
| **Post-Departure** | After checkout | Reduced portal: feedback, "Save This Stay", thank-you |
| **Token Expired** | After TTL | Graceful "This link has expired" — contact info shown |

[BUILT] The API supports status-aware data. [V1 PROPOSAL] The frontend should render different layouts per state.

---

## Screen Inventory

### Main Portal (Single Scrollable Page)

The portal is one continuous page with 8-9 blocks. Unlike worker UIs, there is no multi-screen navigation. The guest scrolls through their stay companion.

---

### Block 1 — Welcome / Stay Header
**[BUILT — needs correction]**

**Current (from screenshot):**
```
┌─────────────────────────┐
│    ● Active             │
│ Welcome, Bon            │
│ KPG-500          ← WRONG│
└─────────────────────────┘
```

**V1 Proposal:**
```
┌─────────────────────────┐
│ ┌───────────────────────┐│
│ │                       ││
│ │  [Hero Image]         ││
│ │  Property cover photo ││
│ │                       ││
│ └───────────────────────┘│
│                         │
│ Welcome, Bon Voyage     │
│ Emuna Villa             │
│ Mar 28 → Apr 7          │
│ ● Active                │
│                         │
│ Your host: Nana G       │
│ Replies in minutes      │
└─────────────────────────┘
```

**What must change:**
- "KPG-500" → property name ("Emuna Villa") or fallback ("Your Villa")
- Add hero image (property cover photo if available)
- Add full date range (not just times)
- Add host mention (name + response time)
- Status badge: hospitality language only ("Active" ✓, not "IN_STAY")

**Data sources:**
- Property name: `property_name` from portal API [BUILT]
- Cover photo: property photo URL [BUILT — available in property data]
- Guest name: canonical sanitized name [BUILT]
- Dates: check-in/check-out from booking [BUILT]
- Status: normalized via `_stayStatusChip()` [BUILT]
- Host info: [PARTIALLY BUILT — contact endpoint has phone/email but no host name/photo]

---

### Block 2 — Home Essentials
**[BUILT — visible in screenshot]**

```
┌─────────────────────────┐
│ 🏠 HOME ESSENTIALS      │
│                         │
│ ┌─ Row ────────────────┐│
│ │ 🔑 Wi-Fi             ││
│ │    VILLA_EMUNA_5G    ││
│ │    [Copy Password 📋]││
│ └──────────────────────┘│
│ ┌─ Row ────────────────┐│
│ │ ⏰ Check-in Time      ││
│ │    15:00              ││
│ └──────────────────────┘│
│ ┌─ Row ────────────────┐│
│ │ ⏰ Check-out Time     ││
│ │    11:00              ││
│ └──────────────────────┘│
│ ┌─ Row ────────────────┐│
│ │ 📍 Address            ││
│ │    [Navigate →]       ││
│ └──────────────────────┘│
│ ┌─ Row ────────────────┐│
│ │ 🚨 Emergency          ││
│ │    +66 812 345 678    ││
│ └──────────────────────┘│
│ ┌─ Row ────────────────┐│
│ │ 📜 House Rules        ││
│ │    [View →]           ││
│ └──────────────────────┘│
└─────────────────────────┘
```

**Confirmed from screenshot:** Check-in time (15:00) and Check-out time (11:00) shown as simple rows with icons.

**[V1 PROPOSAL] Enhancements:**
- Wi-Fi with copy-to-clipboard button (most requested feature)
- Full date + time (not just time): "Check-in: Mar 28, 15:00"
- Address with one-tap navigate (Waze/Google Maps)
- Emergency contact with one-tap call

---

### Block 3 — How This Home Works
**[BUILT — visible in screenshot]**

```
┌─────────────────────────┐
│ 🏠 HOW THIS HOME WORKS  │
│                         │
│ ┌─ Accordion Item ─────┐│
│ │ ❄️ Air Conditioning   ││
│ │    main AC in living  ││
│ │    room               ││
│ └──────────────────────┘│
│ ┌─ Accordion Item ─────┐│
│ │ 🔥 Hot Water          ││
│ │    24 h               ││
│ └──────────────────────┘│
│ ┌─ Accordion Item ─────┐│
│ │ 🍳 Stove / Kitchen    ││
│ │    use plastic spoon  ││
│ └──────────────────────┘│
│ ┌─ Accordion Item ─────┐│
│ │ 🅿️ Parking            ││
│ │    2 bikes or a car   ││
│ └──────────────────────┘│
│ ┌─ Accordion Item ─────┐│
│ │ 🏊 Pool               ││
│ │    use with safe      ││
│ └──────────────────────┘│
│ ┌─ Accordion Item ─────┐│
│ │ 👕 Laundry            ││
│ │    call us for pickup ││
│ └──────────────────────┘│
│ ┌─ Accordion Item ─────┐│
│ │ 📺 TV / Entertainment ││
│ │    use remote         ││
│ └──────────────────────┘│
│ ┌─ Accordion Item ─────┐│
│ │ 📝 Extra Notes        ││
│ │    have fun           ││
│ └──────────────────────┘│
└─────────────────────────┘
```

**Confirmed from screenshot:** 8 instruction categories visible with icons and text. Currently displayed as flat list items (not accordions).

**[V1 PROPOSAL]:** Convert to collapsible accordion items. Each expands to show full instruction text (some properties have long instructions per the V2 product vision examples). This section is already one of the strongest parts of the portal.

---

### Block 4 — Your Host
**[V1 PROPOSAL — not built]**

```
┌─────────────────────────┐
│ 👤 YOUR HOST             │
│                         │
│ ┌─────────────────────┐ │
│ │ [Photo]  Nana G     │ │
│ │          Your host  │ │
│ │          Replies in │ │
│ │          minutes    │ │
│ │                     │ │
│ │ [💬 Message]        │ │
│ │ [📱 LINE]           │ │
│ │ [📞 Call]           │ │
│ └─────────────────────┘ │
│                         │
│ For urgent home issues, │
│ contact us here first.  │
└─────────────────────────┘
```

**Why this matters:** The current portal has a "Need Help" send box at the bottom but no human presence. The guest needs to feel there is a real person behind the system. This block creates trust.

**Data source:** Contact endpoint returns phone, email, WhatsApp link [BUILT]. Host name/photo would need to be configured per property [NOT BUILT — needs property-level host profile].

---

### Block 5 — Need Help / Messages
**[BUILT — visible in screenshot, needs enhancement]**

**Current (from screenshot):**
```
┌─────────────────────────┐
│ 💬 NEED HELP?           │
│                         │
│ Send a message to your  │
│ host                    │
│                         │
│ ┌──────────────────────┐│
│ │ Type your message... ││
│ └──────────────────────┘│
│                         │
│ [Send Message]          │
└─────────────────────────┘
```

**[V1 PROPOSAL] Enhanced:**
```
┌─────────────────────────┐
│ 💬 NEED HELP?           │
│                         │
│ ┌─ Recent Messages ────┐│
│ │ You: Is there a pool  ││
│ │      towel?           ││
│ │ Host: Yes, in the     ││
│ │       cabinet near... ││
│ └──────────────────────┘│
│                         │
│ ┌──────────────────────┐│
│ │ Type your message... ││
│ └──────────────────────┘│
│ [Send]                  │
│                         │
│ [📞 Call Now]           │
│ [💬 WhatsApp]           │
└─────────────────────────┘
```

**Changes:**
- Show recent message thread (not just send box) — API supports GET messages [BUILT]
- Add direct call/WhatsApp buttons (contact data available [BUILT])
- Move host block (Block 4) above this so the guest sees WHO they're messaging

---

### Block 6 — Around You / Extras
**[PARTIALLY BUILT — API exists, UI unclear]**

```
┌─────────────────────────┐
│ 📍 AROUND YOU            │
│                         │
│ ┌─ Card ───────────────┐│
│ │ 🛵 Scooter Rental    ││
│ │    From 300 THB/day   ││
│ │    [Request →]        ││
│ └──────────────────────┘│
│ ┌─ Card ───────────────┐│
│ │ 💆 Massage           ││
│ │    From 500 THB      ││
│ │    [Request →]        ││
│ └──────────────────────┘│
│ ┌─ Card ───────────────┐│
│ │ 🧹 Extra Cleaning    ││
│ │    800 THB           ││
│ │    [Request →]        ││
│ └──────────────────────┘│
│                         │
│ 📍 [Open in Maps →]     │
└─────────────────────────┘
```

**Built:** Extras API with pricing, ordering lifecycle (request → confirm → deliver) [BUILT]. Location API with GPS + Waze/Google Maps links [BUILT].

**Not visible:** This section is not visible in the current screenshots. May be hidden when no extras are configured.

---

### Block 7 — Your Stay
**[PARTIALLY BUILT — API returns data, visibility unclear]**

```
┌─────────────────────────┐
│ 📋 YOUR STAY             │
│                         │
│ Guests: 2               │
│ Deposit: Held ✓         │
│                         │
│ (near checkout:)        │
│ Special notes from host │
│ "Please leave keys on   │
│  the kitchen counter"   │
└─────────────────────────┘
```

**Built:** Guest count, deposit status, checkout notes returned from portal API [BUILT]. Not visible in screenshots.

**[V1 PROPOSAL]:** Keep this minimal. Show guest count, deposit status (simple badge: "Held" / "Returned" / "Pending"), and host notes if any. Do NOT show financial details, electricity readings, or settlement breakdowns.

---

### Block 8 — Departure
**[V1 PROPOSAL — not in main portal, separate route exists]**

```
┌─────────────────────────┐
│ 🚪 WHEN YOU LEAVE        │
│ (shown only near checkout│
│  — within 24h)          │
│                         │
│ Check-out: Apr 7, 11:00 │
│                         │
│ Before you go:          │
│ ✓ Lock all doors        │
│ ✓ Turn off AC           │
│ ✓ Leave keys on counter │
│                         │
│ [Confirm Departure →]   │
│ (links to /guest-checkout│
│  /[token])              │
└─────────────────────────┘
```

**Built:** Guest checkout flow at `/guest-checkout/[token]` with 3 steps: confirm departure, key return, feedback [BUILT — Phase 1045]. But NOT linked from main portal.

**[V1 PROPOSAL]:** Show departure block contextually when checkout is within 24 hours. Link to the checkout flow. Don't show this block during mid-stay.

---

### Block 9 — Save This Stay
**[V1 PROPOSAL — not built, from product vision]**

```
┌─────────────────────────┐
│                         │
│ Save this stay for later│
│                         │
│ Keep this place, Wi-Fi, │
│ notes, and useful       │
│ details in your pocket. │
│                         │
│ [Save to My Pocket →]   │
│                         │
│ (small, low-pressure,   │
│  near bottom of page)   │
└─────────────────────────┘
```

**Not built.** My Pocket system does not exist yet. This is a future bridge. V1 can include the UI block as a placeholder or defer entirely.

---

### Footer [BUILT]

```
┌─────────────────────────┐
│        Ð                │
│ Powered by Domaniqo     │
│ info@domaniqo.com       │
└─────────────────────────┘
```

---

## Self Check-In Flow (Separate Surface)

**Route:** `/self-checkin/[token]` [BUILT — Phase 1012]

This is a separate flow, not part of the main portal page. But it should be accessible FROM the portal when the guest's booking is in pre-arrival or arrival state.

### Gate 1 — Pre-Access
```
Step 1: Identity Photo Upload
Step 2: Agreement Acceptance
Step 3: Deposit Payment
→ Access Code Released
```

### Gate 2 — Post-Entry
```
Follow-up steps (non-blocking)
Additional documentation
```

**[V1 PROPOSAL]:** When booking status is pre-arrival, the main portal should show a prominent "Complete Your Check-In" CTA that links to `/self-checkin/[token]`. After access is released, the portal transitions to full in-stay mode.

---

## Guest Checkout Flow (Separate Surface)

**Route:** `/guest-checkout/[token]` [BUILT — Phase 1045]

### Steps
```
Step 1: Confirm Departure (required)
Step 2: Key/Access Return (required)
Step 3: Feedback (optional — 1-5 rating)
```

**[V1 PROPOSAL]:** Near checkout, the main portal's Departure block links here. After completion, the portal transitions to post-departure state (thank-you, feedback confirmation, Save This Stay).

---

## Navigation Model

```
Main Portal (scrollable single page)
│
├── Block 1: Welcome (always)
├── Block 2: Home Essentials (always)
├── Block 3: How This Home Works (always)
├── Block 4: Your Host (always)
├── Block 5: Need Help (always)
├── Block 6: Around You (if extras configured)
├── Block 7: Your Stay (always)
├── Block 8: Departure (24h before checkout only)
├── Block 9: Save This Stay (future / deferred)
├── Footer
│
├──→ /self-checkin/[token] (pre-arrival CTA)
└──→ /guest-checkout/[token] (departure CTA)
```

No bottom nav. No sidebar. Back button returns to native browser. This is a standalone experience.

---

## Open Questions

### Q1: Theme Direction
Current portal uses dark navy theme (same as worker shell). Product vision specifies warm/light (sand, stone, muted green). When is the theme switch happening? Is V1 the moment, or does it wait for a full design pass?

### Q2: Host Profile Data
The "Your Host" block needs host name and optionally photo. Where does this data come from? Is it per-property, per-tenant, or per-manager? Currently no host profile field exists.

### Q3: Message Thread Display
Should the portal show the full message history or just the last 2-3 messages? Full history could get long for multi-day stays.

### Q4: Self Check-In Portal Link
Should the main portal show a "Complete Your Check-In" CTA that links to `/self-checkin/[token]`? Or should these remain separate URLs delivered separately?

### Q5: Departure Block Timing
When exactly should the departure block appear? 24h before checkout? 48h? Only on checkout day? Should it replace other blocks or appear as an additional section?

### Q6: Post-Departure State
After the guest checks out, what should the portal show? Options: thank-you + feedback prompt + "Save This Stay", or reduced version of the portal, or "This stay has ended" with contact info only.

### Q7: Save This Stay / My Pocket
Is My Pocket in scope for V1, or should the "Save This Stay" block be deferred entirely? Including the UI without the backend would set expectations that can't be met.

### Q8: Property Code in Frontend
The backend API does NOT expose property codes to guests. But the frontend currently shows "KPG-500" on the welcome card. Is this a frontend rendering bug (showing a code that shouldn't be there), or is the API actually returning it?
