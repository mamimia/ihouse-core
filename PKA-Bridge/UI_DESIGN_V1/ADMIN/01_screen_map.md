# Admin UI — Screen Map (V1)

**Role:** admin
**Shell:** Standard Sidebar (desktop-first, collapsible)
**Theme:** Dark theme, green/amber accents
**Navigation:** 11-section sidebar + admin pill-row sub-nav
**Character:** Full operational control. The admin sees everything — bookings, properties, workers, guests, finances, system health. The UI must organize massive complexity without overwhelming.

> **Grounding key:** [BUILT] = confirmed in screenshots. [INFERRED] = from codebase. [V1 PROPOSAL] = new design.

---

## Screen Families (7 families, 34+ screens)

Admin is the largest surface in the product. Rather than defining every screen individually, this document maps the screen families and their structure.

### Family 1: Operations Hub [BUILT]
**Screens:** Dashboard, Tasks, Calendar
**Purpose:** "What's happening right now across all properties?"

| Screen | URL | Key Features |
|--------|-----|-------------|
| Operations Dashboard | `/dashboard` | 3 KPI tiles (check-ins, risk, occupancy), revenue chart, urgent tasks (SLA), today's activity (arrivals/departures/cleanings) |
| My Tasks | `/tasks` | 4-tab filter (All/Pending/InProgress/Done), property-grouped task cards with multi-type chips, countdown timers |
| Calendar | `/calendar` | Month view, booking blocks color-coded by OTA source, date range filtering |

### Family 2: Bookings [BUILT]
**Screens:** List, Detail, Intake, Early Checkout
**Purpose:** "Every booking across the system."

| Screen | URL | Key Features |
|--------|-----|-------------|
| Booking List | `/bookings` | Filterable list, operational status derivation, OTA source colors, manual booking creation, iCal management |
| Booking Detail | `/bookings/[id]` | Full booking record with guest, property, dates, financial, tasks, timeline |
| Booking Intake | `/bookings/intake` | New booking queue |
| Early Checkout | `/bookings/[id]/early-checkout` | Phase 1000 early checkout management |

### Family 3: People [BUILT]
**Screens:** Guests, Guest Dossier, Messages, Owners, Staff, Staff Detail
**Purpose:** "Everyone in the system — guests, owners, workers."

| Screen | URL | Key Features |
|--------|-----|-------------|
| Guest List | `/guests` | Search, PII warning, table view (name/email/phone/nationality), bulk create |
| Guest Dossier | `/guests/[id]` | Phase 979: identity, contact, current stay, history, activity, portal/QR, extras, checkout |
| Guest Messages | `/guests/messages` | Thread view of guest↔host messaging |
| Owners | `/admin/owners` | Owner CRUD, property assignment, linked accounts (Phase 1021) |
| Staff List | `/admin/staff` | Worker list, role badges, property assignments |
| Staff Detail | `/admin/staff/[userId]` | Worker profile, assigned properties, capabilities |

### Family 4: Properties [BUILT]
**Screens:** List, New, Archived, Detail (9-tab)
**Purpose:** "Every property and its configuration."

| Screen | URL | Key Features |
|--------|-----|-------------|
| Property List | `/properties` | All properties with status badges, search |
| New Property | `/properties/new` | Property creation form |
| Archived | `/properties/archived` | Deactivated properties |
| Property Detail | `/properties/[id]` | **9-tab mega-view:** Overview, Reference Photos, House Info, Tasks, Issues, Audit, Edit Details, Gallery, OTA Settings |

**Property Detail is the deepest screen in the admin UI.** Edit Details uses a light-theme form (confirmed in screenshot) with fields: Display Name, Property Type, City, Country, Address, GPS, Bedrooms, Beds, Bathrooms, Max Guests, Check-in/out Times, Description.

### Family 5: Financial [BUILT]
**Screens:** Dashboard, Statements, Owner Portal, Pricing, Currencies, Portfolio
**Purpose:** "Revenue, payouts, and financial health."

| Screen | URL | Key Features |
|--------|-----|-------------|
| Financial Dashboard | `/financial` | Portfolio-level view, provider breakdown, lifecycle distribution, reconciliation inbox |
| Statements | `/financial/statements` | Monthly per-property, per-booking line items, epistemic tiers, PDF/CSV export |
| Owner Portal | `/owner` | Owner-facing financial view (shared page, admin can access) |
| Pricing | `/admin/pricing` | Rate cards, dynamic pricing with AI suggestions |
| Currencies | `/admin/currencies` | Exchange rate management |
| Portfolio | `/admin/portfolio` | Portfolio analytics |

### Family 6: Integrations [BUILT]
**Screens:** Channels, Webhooks, Notifications
**Purpose:** "OTA connections, messaging, and event monitoring."

| Screen | URL | Key Features |
|--------|-----|-------------|
| Channels | `/admin/integrations` | LINE, WhatsApp, Telegram, SMS, Email identity configuration |
| Webhooks | `/admin/webhooks` | Webhook event log and monitoring |
| Notifications | `/admin/notifications` | Notification management and routing |

### Family 7: System [BUILT]
**Screens:** Jobs, Health, Audit, Settings, Profile, DLQ, Sync, More
**Purpose:** "System administration, monitoring, and configuration."

| Screen | URL | Key Features |
|--------|-----|-------------|
| Jobs | `/admin/jobs` | Scheduled jobs / cron management |
| Health | `/admin/health` | System health monitoring |
| Audit | `/admin/audit` | Audit trail / activity logs |
| Settings | `/admin/settings` | General system settings |
| Profile | `/admin/profile` | Admin user account |
| DLQ | `/admin/dlq` | Dead letter queue (error handling) |
| Sync | `/admin/sync` | Data synchronization |
| More | `/admin/more` | Grid view of all admin sections |

---

## Navigation Model

```
┌─────────────────────────────────────────┐
│ SIDEBAR                │ CONTENT AREA   │
│                        │                │
│ Dashboard ──────────────→ Ops Dashboard │
│ ▾ Tasks ────────────────→ My Tasks     │
│ Bookings ───────────────→ Booking List │
│ Calendar ───────────────→ Month View   │
│ ▾ Financial ────────────→ Fin. Dash    │
│ Owners ─────────────────→ Owner Mgmt   │
│ Manager ────────────────→ Manager View │
│ Guests ─────────────────→ Guest List   │
│ Properties ─────────────→ Property List│
│ Manage Staff ───────────→ Staff List   │
│ Admin ──────────────────→ Admin Hub    │
│   [Ops|Finance|Integ|Sys] (pill nav)   │
│ More ───────────────────→ All Sections │
│                        │                │
│ ── ADMIN TOOLS ──      │                │
│ Preview UI As...       │                │
│ Act As... (QA only)    │                │
│ Theme ● ───────────────│                │
│ Lang [EN][TH][HE]     │                │
└────────────────────────┴────────────────┘
```

---

## Open Questions

### Q1: Admin Mobile Strategy
Admin is desktop-first. Should V1 include any mobile optimization, or is admin strictly a desktop surface?

### Q2: Global Search
No unified search exists. Should V1 add a command-palette or search bar that crosses bookings, guests, properties?

### Q3: Notification Center
No admin notification center. Should a bell icon with unread count be added to the header?

### Q4: Theme Consistency
Property edit form uses light theme; dashboard uses dark. Should V1 unify to one theme, or keep the mixed approach?

### Q5: Admin Nav Simplification
11 sidebar items is dense. Should V1 consolidate (e.g., merge "Manager" into "Dashboard", merge "Manage Staff" into "Admin")?
