# iHouse Core — Enhanced UI Architecture
## Product Vision: A Role-Based Property Operations Platform

**Status:** Forward Planning — Enhanced Vision
**Date:** 2026-03-09
**Builds on:** `docs/core/planning/ui-architecture.md`
**Mindset:** Premium SaaS. Think Stripe, Linear, Notion, Vercel — not generic property management dashboards.

---

## What the Market Is Missing

Before designing the UI, understand what every existing tool gets wrong.

**Hostaway, Lodgify, Guesty, Hostfully, Beds24, Tokeet:**
- All are channel managers with bolt-on task features
- None of them have a real exception-first dashboard
- None separate Admin from Manager properly
- None have a real delegated permission model
- Their financial views are backwards-looking accounting screens, not operational intelligence
- Their worker interfaces are desktop-designed, not mobile-first
- They have no real-time reconciliation visibility for hotel managers
- They have no provider health monitoring
- Their owner portals are afterthoughts
- Most require an onboarding call just to understand the dashboard
- **None of them feel like a product designed in 2025**

**The opportunity for iHouse Core:**
Be the first short-term rental management platform that feels like it was designed by a software product company, not a booking tool with screens added later.

---

## Product Identity

iHouse Core UI should feel like **Linear for property operations**.

- Immediate clarity on load
- Role-specific surfaces that feel purpose-built
- Speed: everything is instant, no loading spinners everywhere
- Intelligence: the system tells you what to do, you don't go hunting
- Mobile: workers actually want to open the app
- Owners: trust is built through financial transparency, not marketing copy

---

## The 7 AM Dashboard Rule — Deep Definition

Not just "show the right data." Show it in a way that requires **zero mental load**.

The goal: open the app, no coffee yet, still half asleep. Within 90 seconds you know:
1. What is on fire
2. What is at risk
3. What arrived or departed today
4. What workers confirmed they're on it
5. What is worth money today

**Design principles for the 7 AM Rule:**
- Status = color. CRITICAL = red. WARNING = amber. OK = no color (silence = good).
- Counts only. Numbers, not tables, on the first view.
- Tap/click to drill — never show everything inline.
- Zero unnecessary chrome. No sidebar icons nobody recognizes.
- The dashboard should load in under 1 second.

---

## Role Architecture — Expanded Model

### System Roles (enum, stored in DB)

```
SYSTEM_ADMIN        Full control. Owner of tenant.
MANAGER             Operational control. Admin-bounded.
OPERATIONS_STAFF    Read-heavy. Operational visibility. No writes to settings.
WORKER_CLEANER      Task-only mobile view.
WORKER_CHECKIN      Check-in/out tasks + guest info.
WORKER_MAINTENANCE  Maintenance tasks + issue reporting.
OWNER               Read-only financial + reservation view.
GUEST               Pre-arrival + stay info. (Long-term)
```

### Permission Manifest Model

Do not rely on role alone for UI rendering. Every authenticated session returns a `permission_manifest`:

```json
{
  "role": "MANAGER",
  "tenant_id": "t_xyz",
  "delegated": {
    "can_edit_integrations": false,
    "can_approve_owner_statements": true,
    "can_override_task_assignment": true,
    "can_view_full_financial": true,
    "can_edit_escalation_rules": false,
    "can_manage_staff_channels": false
  }
}
```

This manifest is returned from the `/auth/session` endpoint. The UI renders based on this — never on role string alone.

### Why This Matters

Two managers can be very different in trust. One has been with the company 3 years. One started last week. The system should **express this trust difference** without needing a second role name.

---

## Surface Architecture — Deep Design

### Surface A: Admin Web App

**Philosophy:** The power user surface. Clean but complete. Not a settings dump.

**Navigation model:** Top-level icons only. Secondary nav inside each section.

**Sidebar sections:**
```
Dashboard            ← exception summary + system health
Bookings             ← read-only unless Admin also manages
Financial            ← global financial view, owner statements, statements queue
Integrations         ← providers, webhooks, credential status, sync health
Staff & Roles        ← user management, role assignment, delegation matrix
Escalation           ← SLA rules, notification channels, escalation chains
Reconciliation       ← drift detection, conflict center, findings log
Audit Trail          ← immutable event log viewer, filtered by entity
System Health        ← provider uptime, webhook latency, error rates
Settings             ← global settings, time zones, naming conventions
Reports              ← portfolio-level metrics, owner summaries, export center
```

**Admin Dashboard (first screen):**
```
┌─────────────────────────────────────────────────────────────┐
│ SYSTEM HEALTH          OK   1 provider degraded (Airbnb)    │
├─────────────────────────────────────────────────────────────┤
│ CRITICAL ITEMS         0 critical    3 warnings              │
├─────────────────────────────────────────────────────────────┤
│ TODAY                  8 arrivals    6 departures            │
│ TASKS                  14 pending    2 unacknowledged        │
│ CONFLICTS              1 open conflict (prop_017)            │
│ RECONCILIATION         4 findings (2 warnings, 2 info)       │
├─────────────────────────────────────────────────────────────┤
│ FINANCIAL STRIP        March gross: THB 482,000  ↑ 12%       │
│                        3 missing financial facts             │
│                        2 owner statements awaiting approval  │
└─────────────────────────────────────────────────────────────┘
```

Nothing below this needs to be on the first page. Everything drills.

---

### Surface B: Manager Web App

**Philosophy:** Run the business. See everything operationally. Change what you can change.

**Navigation:**
```
Dashboard            ← 7AM exception-first view
Bookings             ← list + filters + detail
Operations           ← today's arrivals/departures/tasks/readiness
Tasks                ← full task center
Financial            ← bookings-level + provider + property
Properties           ← per-property status + readiness
Staff                ← who is doing what, who is late, who is offline
Reconciliation       ← overview + findings (read only, no admin actions)
Providers            ← health overview, last sync, error counts
```

**Manager Dashboard (first screen) — exception-first layout:**
```
┌──────────────────────────────────────────────────────────────┐
│ TODAY  Monday 9 March 2026                       18:13 ICT   │
├──────────────────────────────────────────────────────────────┤
│ 🔴 NEEDS ACTION NOW                                          │
│   • 2 tasks unacknowledged > 30 min          [View Tasks]    │
│   • Property Villa Priya — cleaner not confirmed [View]      │
│   • Booking conflict: bookingcom_R441 ↔ airbnb_A220 [View]   │
├──────────────────────────────────────────────────────────────┤
│ TODAY'S SCHEDULE                                              │
│   Arrivals:   6          Check-in prep:   4 confirmed 2 open │
│   Departures: 5          Cleanings due:   5 confirmed 0 open │
├──────────────────────────────────────────────────────────────┤
│ PROPERTY READINESS                                            │
│   ✅  6 properties ready                                     │
│   ⚠   2 properties not confirmed                            │
│   🔴  1 property at risk (no cleaner)                        │
├──────────────────────────────────────────────────────────────┤
│ FINANCIAL PULSE        March gross: THB 482,000              │
│   3 payments pending confirmation                            │
│   2 bookings missing financial facts                         │
└──────────────────────────────────────────────────────────────┘
```

Everything is a tap. No tables on this screen. Just counts, status, and action links.

---

### Surface C: Operations Dashboard

**Philosophy:** Real-time command center. Think air traffic control, not Excel.

This screen should auto-refresh every 60 seconds. It should be the screen on a wall monitor in the operations office.

**Layout:**
```
┌──────────────────────┬───────────────────────┬──────────────────────┐
│  ARRIVALS TODAY      │  DEPARTURES TODAY     │  CLEANINGS TODAY     │
│  6 total             │  5 done               │  11 due              │
│  3 checked in ✅     │  0 pending            │  8 complete ✅       │
│  2 in progress 🔄    │                       │  2 in progress 🔄    │
│  1 not yet 🔴        │                       │  1 not started 🔴    │
├──────────────────────┴───────────────────────┴──────────────────────┤
│  TODAY'S TASK BOARD                                                  │
│                                                                      │
│  Villa Priya        CLEANING     [Malee]       ✅ Complete           │
│  Sunset Home        CHECKIN_PREP [Noi]         🔄 In Progress        │
│  Blue Lagoon        CLEANING     [UNASSIGNED]  🔴 Not Started        │
│  The Residence      CHECKOUT_VRF [Dang]        ⏳ Pending ACK 45m   │
│  Palm View          MAINTENANCE  [Somchai]     ✅ Complete           │
├──────────────────────────────────────────────────────────────────────┤
│  ACK SLA ALERTS                                                      │
│  ⚠ "The Residence CHECKOUT_VRF" — Dang hasn't confirmed (45 min)    │
│  🔴 "Sunset Home CHECKIN_PREP" — ACK SLA breached (HIGH = 15 min)   │
└──────────────────────────────────────────────────────────────────────┘
```

Key interaction: clicking any row opens property detail or task detail. Compact. Dense but readable.

---

### Surface D: Worker Mobile App

**Philosophy:** Workers should never be confused. The app should require zero training.

**Design constraints:**
- No sidebar. No settings. No admin chrome.
- Maximum 3 taps to complete any action.
- Works on low-end Android phones.
- Works with bad wifi / offline (task queue cached locally).
- Push notifications are the primary communication channel.

**Worker home screen:**
```
┌──────────────────────┐
│ Hi Malee 👋           │
│ Monday, 9 March      │
├──────────────────────┤
│ YOUR TASKS TODAY     │
│                      │
│ 🔴 URGENT            │
│ Villa Priya          │
│ CLEANING             │
│ Due: 2:00 PM         │
│ [ACKNOWLEDGE]        │
│                      │
│ 🟡 NEXT              │
│ Sunset Home          │
│ CLEANING             │
│ Due: 4:00 PM         │
│                      │
│ ✅ DONE              │
│ Blue Lagoon          │
│ CLEANING — Completed │
│ 11:30 AM today       │
└──────────────────────┘
```

**Task action flow:**
```
PENDING → [ACKNOWLEDGE] → ACKNOWLEDGED → [START] → IN_PROGRESS → [DONE] → COMPLETED
                                                               → [ISSUE] → Issue Report
```

Each step: full screen. One big button. No accidental taps.

**Issue report (new — not in original spec):**
When worker presses [ISSUE]:
- Pre-filled with task + property
- Issue type: damage / missing item / access problem / other
- Severity: minor / moderate / urgent
- Photo attachment (camera opens immediately)
- Short note (70 char limit — forces clarity)
- Submits → creates MAINTENANCE task automatically

This is a key feature competitors don't have: **worker-initiated task creation from the field**.

---

### Surface E: Owner Portal

**Philosophy:** White-glove confidence. Show only what an owner cares about.

**What owners actually want to know:**
1. How much money came in this month?
2. What is in my account / when do I get paid?
3. How many nights was my property occupied?
4. Are there any problems with my property?
5. Can I download my statement?

**Owner home screen:**
```
┌────────────────────────────────────┐
│ Welcome back, Khun Somchai         │
│ Your Properties · March 2026       │
├────────────────────────────────────┤
│ TOTAL REVENUE THIS MONTH           │
│ THB 182,000                        │
│ ↑ 18% vs February                 │
├────────────────────────────────────┤
│ UPCOMING STAYS                     │
│ 14 Mar — 18 Mar  (4 nights)        │
│ 22 Mar — 25 Mar  (3 nights)        │
├────────────────────────────────────┤
│ OCCUPANCY THIS MONTH               │
│ ██████████░░░░░  14/31 nights (45%)│
├────────────────────────────────────┤
│ PAYOUT STATUS                      │
│ Feb statement: ✅ Paid (THB 92,400)│
│ Mar statement: ⏳ Pending           │
├────────────────────────────────────┤
│ [Download March Statement PDF]     │
└────────────────────────────────────┘
```

**What is NOT shown to owners:**
- Task details (operational noise)
- Provider webhook errors (their problem)
- Internal booking IDs (confusing)
- Staff assignments
- Reconciliation findings

---

## New Surfaces — What Competitors Don't Have

### G. Conflict Center

A dedicated screen for **real-time booking conflicts**. Nobody builds this properly.

```
┌──────────────────────────────────────────────────────────┐
│ CONFLICT CENTER                    2 active conflicts    │
├──────────────────────────────────────────────────────────┤
│ 🔴 CRITICAL — Requires resolution                        │
│ bookingcom_R441 ↔ airbnb_A220                            │
│ Villa Priya · 14 Mar — 18 Mar                            │
│ Detected: 2h ago · Assigned: None                        │
│ [RESOLVE] [OVERRIDE BOOKING_COM] [OVERRIDE AIRBNB]       │
├──────────────────────────────────────────────────────────┤
│ ⚠ PENDING RESOLUTION                                     │
│ expedia_E109 ↔ direct_D022                               │
│ Blue Lagoon · 22 Mar — 25 Mar                            │
│ Detected: 5m ago · Auto-expires in 4h                    │
│ [RESOLVE] [VIEW TIMELINE]                                │
└──────────────────────────────────────────────────────────┘
```

Resolution actions create canonical override events through `POST /webhooks/{provider}` — they never bypass the event pipeline.

---

### H. Provider Health Monitor

A live dashboard of all connected OTAs — nobody builds this either.

```
┌──────────────────────────────────────────────────────────────────┐
│ PROVIDER HEALTH                              Updated 2 min ago   │
├──────────────────────────────────────────────────────────────────┤
│ Provider          Status    Last Sync    Errors 24h    Webhooks  │
│ Booking.com       ✅ OK      2 min ago    0             Live      │
│ Airbnb            ⚠ SLOW    15 min ago   2 (minor)     Live      │
│ Expedia           ✅ OK      3 min ago    0             Live      │
│ Agoda             ✅ OK      1 min ago    0             Live      │
│ Vrbo              🔴 ERROR   2h ago       14            Dead      │
│ Despegar          ✅ OK      5 min ago    0             Live      │
│ Direct            ✅ OK      —            0             N/A       │
├──────────────────────────────────────────────────────────────────┤
│ Vrbo issue: last 14 webhooks returned 401. Check API credentials │
│ [View Error Log] [Test Connection] [Contact Support]             │
└──────────────────────────────────────────────────────────────────┘
```

---

### I. Financial Timeline (per booking)

A visual, chronological financial view per booking. Nothing like this exists in competitors.

```
Booking bookingcom_R441 · Villa Priya · 14–18 Mar 2026

Timeline:
 Mar 5  ── BOOKING_CREATED          Base: THB 12,000  Commission: 15%
 Mar 5  ── FINANCIAL_FACTS_WRITTEN  Net: THB 10,200   Status: CONFIRMED
 Mar 7  ── BOOKING_AMENDED          +1 night           Net: THB 12,240
 Mar 9  ── RECONCILIATION_CHECK     ✅ No drift found
 Mar 14 ── CHECK_IN (expected)
 Mar 18 ── CHECK_OUT (expected)
 Mar 19 ── PAYOUT_PENDING (expected)
```

This is what a premium product looks like. Audit trail + financial state in one chronological view.

---

### J. Occupancy Intelligence Strip

A compact, highly-readable property-level occupancy view.

```
MARCH 2026                     Property: Villa Priya

Mo Tu We Th Fr Sa Su
                  1  2
 3  4  5  6  7  8  9
[10 11 12 13][14 15 16 17 18][19 20 21]22 23
[24 25][26 27 28 29 30 31]

Legend: [booking] ·occupied ·pending ·available

Occupancy rate: 74%  ·  Avg nightly: THB 3,060  ·  Projected March: THB 87,000
```

Color-coded. One glance. No clicking through multiple screens to see property availability.

---

### K. Reconciliation Report Screen

Operators can never see OTA drift in existing tools — it's hidden in logs somewhere.

```
┌────────────────────────────────────────────────────────┐
│ RECONCILIATION REPORT                March 2026        │
│ Tenant: Priya Property Group                           │
├────────────────────────────────────────────────────────┤
│ Checked:  42 bookings                                  │
│ Clean:    39   ·   Warnings: 2   ·   Info: 1           │
│ Last run: 5 min ago   ·   Partial: No                  │
├────────────────────────────────────────────────────────┤
│ ⚠ FINANCIAL_FACTS_MISSING                              │
│   bookingcom_R440 · Villa Priya                        │
│   Detected 2h ago · Hint: Re-ingest webhook            │
├────────────────────────────────────────────────────────┤
│ ⚠ FINANCIAL_FACTS_MISSING                              │
│   airbnb_A219 · Blue Lagoon                            │
│   Detected 1h ago · Hint: Re-ingest webhook            │
├────────────────────────────────────────────────────────┤
│ ℹ STALE_BOOKING                                        │
│   expedia_E098 · The Residence · Last updated 35 days  │
│   Hint: Verify booking is still active in Expedia      │
└────────────────────────────────────────────────────────┘
```

---

## What iHouse Core Can Sell That Competitors Can't

| Feature | iHouse Core | Competitors |
|---------|-------------|-------------|
| Exception-first dashboard (7AM rule) | ✅ Core principle | ❌ Data overload |
| Real delegated permission model | ✅ Permission manifest | ❌ Binary Admin/Staff |
| Role-specific worker mobile (per role) | ✅ Planned | ❌ Generic task app |
| Worker-initiated issue → MAINTENANCE task | ✅ Planned | ❌ Not built |
| Live provider health monitor | ✅ Planned | ❌ Buried in logs |
| Conflict center with canonical resolution | ✅ Built (conflict resolver skill) | ❌ Manual email |
| Booking-level financial timeline | ✅ Planned | ❌ Not built |
| OTA reconciliation UI (drift detection) | ✅ Built (Phase 110 API) | ❌ Non-existent |
| Immutable audit trail UI | ✅ Planned (event_log exists) | ❌ Non-existent |
| Occupancy intelligence strip | ✅ Planned | ⚠ Calendar-only |
| Owner portal with payout confidence | ✅ Planned | ⚠ Basic PDF only |
| Escalation SLA transparency (CRITICAL=5m) | ✅ Locked (skills layer) | ❌ No SLA model |

---

## Technology Recommendations for UI

When the time comes to build:

**Admin + Manager Web App:**
- Next.js 14+ (App Router) — SSR for fast initial load
- Tailwind CSS + shadcn/ui — fast, consistent, customizable
- Zustand or Jotai — lightweight state management
- React Query (TanStack) — server state sync, background refresh
- Recharts or Tremor — charts for financial strip

**Worker Mobile:**
- React Native (Expo) — single codebase, iOS + Android
- Offline-first with local SQLite task cache
- Push via FCM / APNs
- Camera integration for issue photos

**Owner Portal:**
- Can share codebase with Manager Web App, restricted routes only
- PDF generation: puppeteer or react-pdf for owner statements

**Real-time / Operations Dashboard:**
- Supabase Realtime (Postgres change subscriptions) — already in stack
- Auto-refresh every 60s as fallback

---

## UI State Language (Design System)

All surfaces should use a consistent visual language:

| State | Color | Treatment |
|-------|-------|-----------|
| CRITICAL | Red (#EF4444) | Bold text + icon + card red border |
| WARNING | Amber (#F59E0B) | Amber icon + subtle amber background |
| INFO | Blue (#3B82F6) | Icon only, no background fill |
| OK / Healthy | No color | Silence is success |
| PENDING | Gray (#6B7280) | Muted, no emphasis |
| IN_PROGRESS | Blue-purple (#6366F1) | Animated dot |
| COMPLETED | Green (#10B981) | Check icon only |
| CANCELED | Strikethrough + gray | De-emphasized |

**The rule:** only bad states get color. Good is colorless. This is how Stripe, Linear, and Vercel work.

---

## API → UI Alignment (Expanded)

| Planned API | Powers UI Surface |
|-------------|------------------|
| `GET /tasks?status=PENDING&property_id=` | Operations Dashboard task board |
| `GET /tasks/{id}` | Worker task detail |
| `PATCH /tasks/{id}/status` | Worker ack/start/done buttons |
| `GET /bookings?check_in_from=&check_in_to=` | Operations Dashboard arrivals/departures |
| `GET /bookings?status=active&limit=50` | Manager bookings list |
| `GET /financial?property_id=&month=` | Property financial snapshot |
| `GET /financial/summary?period=` | Manager dashboard strip |
| `GET /financial/by-property?period=` | Owner portal + manager financial |
| `GET /admin/reconciliation?include_findings=true` | Reconciliation screen |
| `GET /admin/health` | Provider health monitor *(future)* |
| `POST /intake/{booking_id}` | Guest portal pre-arrival *(future)* |

---

## Phased UI Delivery Plan

**Phase ~120–122 — Operations Dashboard (web):**
Arrivals, departures, today's task board, ACK alerts. API-complete at Phase 113.
Highest value. Clearest contract. Start here.

**Phase ~123–125 — Manager Web App core:**
Bookings list, booking detail, task center, property readiness, financial strip.

**Phase ~126–128 — Admin Web App:**
System settings, integrations, user management, delegation matrix, escalation rules.

**Phase ~129–130 — Owner Portal:**
Revenue, occupancy, payout status, statement PDF.

**Phase 131+ — Worker Mobile:**
Needs Phase 113 (tasks) + LINE/WhatsApp channel (Phase ~118) stable first.

**Phase 135+ — Guest Portal:**
Lowest operational urgency. Highest guest-facing value. Build last.

---

*This document supersedes and extends `ui-architecture.md`. Both remain canonical.
Last thought: every screen should make someone's job easier. That is the only measure that matters.*
