# Admin UI — System Reality (Read Before Design)

**Read from:** ihouse-core real codebase + Team_Inbox screenshots (80+ across 5 folders)
**Date:** 2026-04-03

> **Grounding key:** [BUILT] = confirmed in screenshots. [INFERRED] = from codebase. [V1 PROPOSAL] = new design.

---

## What Already Exists [BUILT]

### Architecture
- **Shell:** Standard Sidebar layout (desktop-first, collapsible sidebar on mobile)
- **Auth:** JWT with `role: "admin"` — full system access
- **Theme:** Dark theme throughout (dark backgrounds, light text, green/amber accents)
- **Navigation:** Left sidebar with 11 main sections + admin tools at bottom

### Sidebar Navigation [BUILT — confirmed in screenshots]

**Main sections:**
1. Dashboard
2. Tasks (expandable)
3. Bookings
4. Calendar
5. Financial (expandable)
6. Owners
7. Manager
8. Guests
9. Properties
10. Manage Staff
11. Admin (expandable)
12. More

**Admin Tools (bottom of sidebar):**
- Preview UI As... (role preview)
- Act As... (QA only)
- Theme toggle (dark/light)
- Language selector (EN / TH / HE flags)

### Admin Sub-Navigation [BUILT]
Within `/admin`, a horizontal pill-row nav bar organizes 4 groups:
1. **Operations** — Overview, Intake, Owners, Templates, Feedback, Conflicts, Bulk
2. **Finance** — Pricing, Currencies, Portfolio
3. **Integrations** — OTA Channels, Webhooks, Notifications
4. **System** — Jobs, Health, Audit, Settings, Profile

---

## Screens Confirmed from Screenshots

### Operations Dashboard [BUILT — Screenshot 22.42.43]
- Greeting: "Good evening · 2026-03-25"
- Title: "Operations Dashboard"
- Last updated timestamp
- 3 KPI tiles: CHECK-INS TODAY (0), VILLAS AT RISK (0, "All clear"), OCCUPANCY (100%, "1 of 1 properties occupied")
- REVENUE THIS MONTH bar chart (across N properties)
- URGENT TASKS section (red task cards with SLA countdowns: "ACK SLA: 15min · KPG-500")
- TODAY section: ARRIVALS / DEPARTURES / CLEANINGS counts

### My Tasks [BUILT — Screenshot 22.43.12]
- Title: "My Tasks" with date
- 4 filter tabs: All | Pending | In Progress | Done
- Task cards grouped by property and date
- Each property row shows: property name, date, then task chips (CHECKOUT_VERIFY, Cleaning, Check-in Prep) with status badges (PENDING, ACKNOWLEDGED) and countdown timers
- Task chips are color-coded: checkout brown/copper, cleaning green, check-in teal

### Guests [BUILT — Screenshot 22.48.11]
- Title: "Guests" with search bar + "New Guest" button
- PII warning banner: "This page contains personally identifiable information (PII). Handle with care."
- Table: NAME, EMAIL, PHONE, NATIONALITY, CREATED, DETAIL
- Guest records shown in table rows

### Property Detail — Edit Details [BUILT — Screenshot 22.55.22]
- Breadcrumb: Home > Admin > Properties > KPG 500
- Property header: photo thumbnail, "Emuna Villa" with Approved badge, KPG-598 code
- Action buttons: Open in Maps, Add Booking, Admin...
- Tab bar: Overview | Reference Photos | House Info | Tasks | Issues | Audit | Edit Details* | Gallery | OTA Settings
- Edit form fields: Display Name, Property Type, City, Country, Address, GPS Coordinates, Bedrooms, Beds, Bathrooms, Max Guests, Check-in Time, Check-out Time, Description
- Light theme on edit form (white background, unlike dark dashboard)

---

## Full Page Inventory (from codebase)

### Top-Level Pages (34 page.tsx files found)

**Core Operations:**
- `/dashboard` — Operations Dashboard [BUILT]
- `/tasks` — Task management [BUILT]
- `/bookings` — Booking list + detail + intake [BUILT]
- `/bookings/[id]` — Individual booking detail [BUILT]
- `/bookings/[id]/early-checkout` — Early checkout management [BUILT]
- `/calendar` — Month-view booking calendar [BUILT]

**People:**
- `/guests` — Guest master list [BUILT]
- `/guests/[id]` — Guest dossier (Phase 979) [BUILT]
- `/guests/messages` — Guest message threads [BUILT]
- `/admin/owners` — Owner management CRUD [BUILT]
- `/admin/staff` — Staff list [BUILT]
- `/admin/staff/new` — Add staff [BUILT]
- `/admin/staff/[userId]` — Staff detail [BUILT]
- `/manager` — Manager section [BUILT]

**Properties:**
- `/properties` — Property list [BUILT]
- `/properties/new` — Create property [BUILT]
- `/properties/archived` — Archived properties [BUILT]
- `/properties/[propertyId]` — Property detail (9-tab view) [BUILT]

**Financial:**
- `/financial` — Financial dashboard [BUILT]
- `/financial/statements` — Monthly statements [BUILT]
- `/owner` — Owner portal view [BUILT]
- `/admin/pricing` — Rate cards [BUILT]
- `/admin/currencies` — Exchange rates [BUILT]
- `/admin/portfolio` — Portfolio analytics [BUILT]

**Admin:**
- `/admin` — Admin overview [BUILT]
- `/admin/intake` — Intake queue [BUILT]
- `/admin/templates` — Task templates [BUILT]
- `/admin/feedback` — Guest feedback + NPS [BUILT]
- `/admin/conflicts` — Booking conflicts [BUILT]
- `/admin/bulk` — Bulk operations [BUILT]
- `/admin/integrations` — OTA channel config [BUILT]
- `/admin/webhooks` — Webhook monitoring [BUILT]
- `/admin/notifications` — Notification management [BUILT]
- `/admin/jobs` — Scheduled jobs [BUILT]
- `/admin/health` — System health [BUILT]
- `/admin/audit` — Audit trail [BUILT]
- `/admin/settings` — General settings [BUILT]
- `/admin/profile` — Admin profile [BUILT]
- `/admin/more` — Grid view of all sections [BUILT]
- `/admin/dlq` — Dead letter queue [BUILT]
- `/admin/sync` — Data sync [BUILT]

---

## What Is Missing or Incomplete

1. **No unified search** — No global search across bookings, guests, properties
2. **No notification center** — No bell icon with unread alerts
3. **No mobile-optimized admin** — Sidebar collapses but content isn't mobile-first
4. **No analytics/reporting dashboard** — Individual metrics exist but no unified reporting view
5. **Mixed theme** — Dashboard is dark, property edit form is light. Theme is inconsistent across sections.

---

## What Is Already Strong

1. **Comprehensive coverage** — 34+ pages covering every operational aspect
2. **Property detail depth** — 9-tab property view (Overview, Photos, House Info, Tasks, Issues, Audit, Edit, Gallery, OTA)
3. **Financial transparency** — Epistemic tiers on all financial figures
4. **Role preview system** — "Preview UI As..." and "Act As..." tools in sidebar
5. **Multi-language** — EN, TH, HE language support with flag selectors
6. **Real-time updates** — SSE live indicators on multiple dashboards
7. **PII awareness** — Warning banners on guest data pages
8. **Task management** — Cross-role task view with status, SLA, and property grouping
