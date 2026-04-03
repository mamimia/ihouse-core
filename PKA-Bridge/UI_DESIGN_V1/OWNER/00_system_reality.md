# Owner Portal — System Reality (Read Before Design)

**Read from:** ihouse-core real codebase + Team_Inbox screenshots
**Date:** 2026-04-03

> **Grounding key:** [BUILT] = confirmed in product/screenshots. [INFERRED] = from codebase. [V1 PROPOSAL] = new design.

---

## What Already Exists [BUILT]

### Portal Architecture
- **Route:** `/owner` — authenticated page within the app shell
- **Auth:** JWT with `role: "owner"` — owner must have a linked `owner_user_id` for login
- **Shell:** Standard Sidebar layout (same as admin, NOT the worker MobileStaffShell)
- **Navigation:** Sidebar with: Dashboard, Bookings, Calendar, Financial

### Owner Portal Page (`/owner/page.tsx`, 793 lines)
**Evidence:** Screenshots 22.35.45 and 22.41.10

**Layout confirmed from screenshots:**
- Header: "Revenue & payouts" breadcrumb
- Title: "Owner Portal" (Owner in white, Portal in green)
- Month selector: "2026-03" with refresh button
- 4 metric tiles in a row:
  - PROPERTIES (count, "in portfolio")
  - TOTAL BOOKINGS (count, month label)
  - GROSS REVENUE ("before commission")
  - OWNER NET ("after mgmt fee", green text)
- Section: "PROPERTIES · CLICK TO VIEW STATEMENT" — property cards (empty state: "No property data for 2026-03")
- Section: "CASHFLOW TIMELINE — EXPECTED WEEKLY INFLOWS" — cashflow chart (empty state: "No cashflow data for 2026-03", link to "View Financial Dashboard →")
- Footer: "Domaniqo — Owner Portal · Phase 309" with auto-refresh indicator ("Auto-refresh: 60s · SSE live")

### Owner Sidebar Navigation [BUILT]
| Section | URL | Purpose |
|---------|-----|---------|
| Dashboard | `/dashboard` | Main operational dashboard |
| Bookings | `/bookings` | Booking list (filtered to owner's properties) |
| Calendar | `/calendar` | Month-view booking calendar |
| Financial | `/financial` | Financial dashboard + statements |

### Financial Views [BUILT]

**Statements page (`/financial/statements`):**
- Monthly statement per property
- Per-booking line items with: check-in/out dates, OTA source, gross, commission, net
- Epistemic tier badges: ✅ A=Measured / 🔵 B=Calculated / ⚠️ C=Incomplete
- Export to PDF and CSV

**Financial dashboard (`/financial`):**
- Portfolio-level financial view
- Provider breakdown (bookings, gross, commission, net, ratio)
- Property breakdown
- Lifecycle distribution (7 payment states)
- Reconciliation inbox

### Owner Visibility Controls [BUILT — Phases 604, 721]
Configurable per property per owner:
- **Default visible:** bookings, financial_summary, occupancy_rates, guest_details, guest_reviews, cleaning_status, maintenance_reports
- **Default hidden:** price_per_night, revenue, operational_costs, worker_details, cleaning_photos, task_details
- Stored in `owner_visibility_settings` table

### PDF Statement Generation [BUILT]
- Endpoint: `/owner-statement/{property_id}?format=pdf&lang={lang}`
- Plain-text PDF (no external library)
- Includes management fee deduction details
- Translatable (language parameter)

### Real-Time Updates [BUILT — Phase 309]
- SSE via `/events/stream?channels=financial`
- Auto-refresh every 60 seconds
- Live financial data updates

### Backend API Routes
| Route | Purpose |
|-------|---------|
| `/owner-statement/{property_id}?month=YYYY-MM` | Monthly statement with line items |
| `/owner/financial-report?date_from&date_to` | Custom date range report |
| `/owner-portal/{owner_id}/properties/{property_id}/summary` | Filtered property summary |
| `/owner/visibility/{property_id}` | Get/set visibility settings |

---

## What Is Visible in Screenshots

**Screenshot 1 (mobile view):**
- Dark theme, sidebar collapsed
- PREVIEW MODE banner (viewing as Owner)
- 4 metric tiles: Properties 0, Total Bookings 0, Gross Revenue —0, Owner Net —0
- Property section empty: "No property data for 2026-03"
- Cashflow section empty: "No cashflow data for 2026-03"
- Footer shows Phase 309, auto-refresh 60s, SSE live

**Screenshot 2 (desktop view):**
- Same content at wider viewport
- 4 metric tiles in horizontal row
- Multiple browser tabs open (many Domaniqo tabs)
- Slightly wider layout but same structure

**Both screenshots show empty state** — no properties assigned to this owner for the selected month.

---

## What Is Missing

1. **No property detail drill-down from owner portal** — clicking a property goes to statements, but there's no owner-specific property summary page
2. **No occupancy visualization** — calendar exists but no occupancy rate chart for owners
3. **No maintenance/cleaning visibility on owner portal** — visibility settings allow it, but no dedicated owner-facing section shows operational status
4. **No guest review aggregation on owner portal** — feedback data exists in admin, not surfaced to owner
5. **No notification/alert system for owners** — no "your property was booked" alerts
6. **No mobile-optimized owner view** — uses standard sidebar shell which is desktop-first

---

## What Is Already Strong

1. **Financial transparency** — Epistemic tiers on every figure (A/B/C confidence). Owners see data quality.
2. **Visibility controls** — Per-property, per-owner configurable field visibility. Granular privacy.
3. **Real-time updates** — SSE + auto-refresh. Owners see live financial state.
4. **PDF export** — Monthly statements downloadable as PDF.
5. **Property scoping** — All data filtered to owner's assigned properties at DB level.
