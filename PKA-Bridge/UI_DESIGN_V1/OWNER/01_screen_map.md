# Owner Portal — Screen Map (V1)

**Role:** owner
**Shell:** Standard Sidebar (desktop-first, responsive)
**Theme:** Dark header, dark card backgrounds, green accent (financial identity)
**Navigation:** Sidebar: Dashboard, Bookings, Calendar, Financial
**Character:** Financial transparency, property portfolio, trust-building. The owner needs to trust that their properties are managed well and their money is accounted for.

> **Grounding key:** [BUILT] = confirmed in screenshots. [INFERRED] = from codebase. [V1 PROPOSAL] = new design.

---

## Screen Inventory (5 screens)

### S01 — Owner Portal Home [BUILT]
**URL:** `/owner`
**Evidence:** Screenshots 22.35.45 and 22.41.10

**Layout:**
```
┌─────────────────────────────────────┐
│ Sidebar    │ Revenue & payouts      │
│            │                        │
│ Dashboard  │ Owner Portal  [2026-03]│
│ Bookings   │               [refresh]│
│ Calendar   │                        │
│ Financial  │ ┌────┐┌────┐┌────┐┌────┐
│            │ │PROP││BOOK││GROS││NET ││
│            │ │ 3  ││ 12 ││4.2k││3.1k││
│            │ └────┘└────┘└────┘└────┘│
│            │                        │
│            │ PROPERTIES             │
│            │ Click to view statement│
│            │ ┌──────────────────┐   │
│            │ │ Villa Emuna      │   │
│            │ │ 5 bookings       │   │
│            │ │ THB 42,000 gross │   │
│            │ └──────────────────┘   │
│            │ ┌──────────────────┐   │
│            │ │ KPG Residence    │   │
│            │ │ 7 bookings       │   │
│            │ │ THB 38,500 gross │   │
│            │ └──────────────────┘   │
│            │                        │
│            │ CASHFLOW TIMELINE      │
│            │ Expected weekly inflows│
│            │ [Chart/Timeline]       │
│            │                        │
│            │ Domaniqo — Owner Portal│
│            │ Auto-refresh: 60s · SSE│
└────────────┴────────────────────────┘
```

**States:**
- Empty: "No property data for {month}" + "No cashflow data for {month}"
- Populated: Property cards with booking count and gross revenue per property
- Loading: Standard spinner
- Error: Graceful fallback message

---

### S02 — Bookings [BUILT]
**URL:** `/bookings` (filtered to owner's properties)

**[INFERRED from code — not in owner screenshots]**

Shared bookings page filtered by owner's property_ids. Shows:
- Booking list with status badges (in_stay, checkout_today, upcoming, completed, cancelled)
- OTA source color coding (Airbnb red, Booking.com blue, etc.)
- Date range, guest name, property, nights
- Status-based sections

---

### S03 — Calendar [BUILT]
**URL:** `/calendar` (filtered to owner's properties)

**[INFERRED from code — not in owner screenshots]**

Month-view calendar showing booking blocks per property. Color-coded by source. Cancelled bookings visually distinct.

---

### S04 — Financial Dashboard [BUILT]
**URL:** `/financial`

**[INFERRED from code]**

- Portfolio-level financial view
- Provider breakdown table (Airbnb, Booking.com, etc. with booking count, gross, commission, net, ratio)
- Property breakdown
- Lifecycle distribution (7 payment states chart)
- Reconciliation inbox

---

### S05 — Monthly Statement [BUILT]
**URL:** `/financial/statements`

**[INFERRED from code]**

- Month selector + property selector
- Per-booking line items: check-in/out dates, OTA source, gross, commission, net
- Epistemic tier badges per figure (✅ A / 🔵 B / ⚠️ C)
- Management fee deduction row
- Summary totals
- [Export PDF] [Export CSV] buttons

---

## Open Questions

### Q1: Mobile Owner Experience
Current owner portal uses standard sidebar shell (desktop-first). Should V1 include a mobile-optimized owner view? Owners may check revenue on their phone.

### Q2: Property Operational Status
Visibility settings allow showing cleaning_status, maintenance_reports to owners. Should V1 include an operational section showing "your properties are being taken care of" — without operational jargon?

### Q3: Occupancy Rate Visualization
Calendar data supports occupancy calculation. Should the owner portal show occupancy rates as a KPI tile or chart?

### Q4: Notification System
No owner alerts exist. Should V1 include "new booking at Villa Emuna" or "payment received" notifications?

### Q5: Guest Review Access
Guest feedback data exists in admin. Should owners see aggregated reviews for their properties?
