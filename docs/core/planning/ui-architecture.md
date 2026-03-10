# iHouse Core — UI Architecture and Role-Based Product Surfaces

**Status:** 12+ screens deployed. All target surfaces built. Auth flow live.
**Date recorded:** 2026-03-09 | **Last updated:** 2026-03-11 (Phase 210 documentation audit)
**Intent:** Keep this document as a standing architectural reference for all future
UI phases, API design, and permission modeling decisions.

---

## Core Principle

iHouse Core should not become one giant dashboard with everything inside it.

It should become a **set of role-based product surfaces** built on top of the same
canonical system. Each surface should feel like a dedicated tool for a specific person
with a specific job — not a one-size-fits-all console.

---

## The 7 AM Rule — Dashboard Philosophy

> Someone wakes up at 7:00 AM, tired, opens the dashboard, and within two minutes
> understands the state of the business.

The primary operational surfaces must be **exception-first**. They should answer:

- What needs attention **now**?
- What is **blocked** or **delayed**?
- What is **financially important** today?
- What is **operationally urgent**?
- Which **properties** need action?
- Which **workers** did not acknowledge?
- Which **integrations** look unhealthy?

The first screen **must not** try to show everything. Drill-downs exist for everything else.

---

## Role Model

### 1. Admin / System Owner

Full system control. No limitations.

- System settings, integrations, provider connections
- Notification channels, escalation rules
- Permission and role management
- Global financial and reporting settings
- Owner statement controls
- System-level audit surfaces
- Reconciliation governance

### 2. Manager / Operations Manager

Broad operational visibility (~80% of day-to-day product). Can run the business.
**Does not automatically have system-owner powers.**

Manager can:
- Manage bookings, tasks, properties, staff
- View financial data (at the level Admin allows)
- Manage operational exceptions
- See reconciliation overview and provider health

Manager cannot (by default):
- Connect or replace providers and APIs
- Change system-level financial rules
- Change escalation architecture
- Edit core permission models
- Change global owner statement behavior

### 3. Delegated Authority Model

Permissions are not binary (Admin or not Admin).
The model is:

```
Admin
Manager
Manager + delegated capabilities
```

Admin may optionally grant a specific manager:
- Certain integration settings
- Approval of owner-facing outputs
- Expanded financial visibility
- Override of operational assignments
- Management of staff channels or escalation rules

**This should be permission-based, not hardcoded in the UI.**

> ⚠️ This delegation model should be designed into the data model early,
> even before the UI is built. A permission structure added retroactively
> will always be messier than one designed in from the start.

---

## UI Surfaces (Target Architecture)

### A. Admin Web App

**Purpose:** System-level control surface. Full visibility, governance, settings.

**Key screens:**
- Admin Dashboard (exception summary, system health strip)
- Integrations and Provider Settings
- Global Financial Settings
- Owner Statement Controls
- Permission / Role Management
- Escalation and Notification Rules
- System Health Monitor
- Reconciliation and Drift View
- Audit / Event Timeline
- Conflict Center
- Portfolio Reports

---

### B. Manager Web App

**Purpose:** Primary business-running surface. Daily operational command center.

**Key screens:**
- Manager Dashboard (exception-first, 7AM-rule compliant)
- Bookings List + Filters
- Booking Detail (financial + status + task view)
- Reservation Timeline
- Payment Status / Financial Visibility
- Operations Board
- Task Center (with status, assignment, SLA)
- Property Readiness View
- Staff Status View
- Conflict / Exceptions
- Reconciliation Overview
- Provider Health Overview
- Property Financial Snapshot

---

### C. Operations Dashboard

**Purpose:** Live command center — what is happening today and what needs action.

**Must show:**
- Arrivals today / departures today
- Cleanings due (status: unstarted, in progress, overdue)
- Maintenance due
- Unacknowledged tasks (with time since dispatch)
- Delayed acknowledgements (ACK SLA breach alerts)
- Same-day operational risks
- Property readiness state (ready / not ready / at risk)
- Urgent issues by property

> This should feel like a live command center, not a reporting page.
> It should refresh frequently. It should never require explanation to use.

---

### D. Worker Mobile Surfaces

**Purpose:** Role-specific, lightweight, action-first.

**Worker roles (distinct UI per role):**
- Cleaner
- Check-in / Check-out Worker
- Maintenance / Pool / Garden / Repair Worker

**Each worker UI must show:**
- My tasks (today, priority order)
- What is next
- Where to go (property address)
- Due time
- Acknowledge button
- Start button
- Done button
- Report issue
- Add note / photo
- Short history (last 3–5 tasks)

> Worker UI: action-first, not data-heavy.
> No admin noise. No financial data. No cross-property visibility.

---

### E. Owner Portal

**Purpose:** Trust-based, financially clear, confidence-inspiring. Not operational.

**Key screens:**
- Owner Dashboard (revenue summary, payout status, upcoming stays)
- Monthly Statement
- Revenue by Property
- Payout Status + History
- Upcoming Stays (lightweight — guest names optional depending on privacy setting)
- Reservation View (read-only, high-level)
- Documents / Exports

> The owner portal should show confidence and clarity.
> It should never expose internal system complexity.

---

### F. Guest Portal *(Long-term)*

**Purpose:** Pre-arrival and stay-support surface for guests.

**Key screens:**
- Reservation Details
- Pre-arrival Info
- Check-in Instructions
- House Guide
- Support Links
- Check-out Instructions

Priority: lower than operational surfaces. Should be planned but not rushed.

---

## Main Dashboard — What to Show

The main dashboard (Admin and Manager) should have a **deliberately small and sharp** first screen.

**Should include:**
- Urgent operational alerts (ACK SLA breaches, conflicts, critical tasks)
- Arrivals / departures today (count + drill-down)
- Pending or delayed cleanings
- Unacknowledged tasks (count + oldest)
- Properties needing attention (list or count)
- Financial attention items (overdue, missing facts, drift)
- Integration / provider health summary (OK / warning / error)
- Reconciliation or conflict count (with drill-down)
- One compact performance strip (monthly revenue vs. last month)

**Should not include on first screen:**
- Detailed booking lists
- Financial breakdowns
- Staff rosters
- Charts for chart's sake
- Historical data overviews

---

## Financial UI Direction

As the financial layer matures, a dedicated financial area should emerge in layers.
**Do not rush this. Only build when supporting APIs and reconciliation confidence are stable.**

Target financial UI sections (phased, not immediate):
- Financial Dashboard (headline KPIs)
- Financial List View (all transactions with filters)
- Payment Lifecycle View (per booking)
- Revenue by Property
- Payout Breakdown
- Cashflow View
- Reconciliation Screen
- Owner Statements
- Booking-level Financial Timeline

---

## Permission-Aware UI Principle

The UI should not only be **role-based** (what role are you?) but also **permission-aware**
(what has Admin allowed you to do?).

Two managers on the same system may see different controls.
This should be a first-class design constraint — not an afterthought.

Implications:
- The API layer must expose permission metadata with every session/token
- The UI should consume a permission manifest, not hardcode role checks
- Screens should have graceful "not permitted" states (hidden, grayed, or explained)

---

## What Must Not Happen

| Anti-pattern | Why it is dangerous |
|---|---|
| One giant dashboard showing everything | Overload — operators miss critical signals |
| Managers with accidental system-owner powers | Trust boundary violation |
| Workers seeing admin complexity | Confusion + security risk |
| Owners seeing operational noise | Destroys trust and confidence |
| Impressive dashboards that are slow to read | Defeats the 7AM rule |
| Early UI decisions that block future delegation | Technical debt + permission regret |
| Bloated first screens | Operators skip them, act on guesses |

---

## Actual Deployment State — Phase 175 Checkpoint

The `ihouse-ui/` Next.js 14 App Router project was scaffolded in Phase 152 and has since grown to **6 deployed screens**:

| Route | Screen | Deployed | Backend APIs |
|-------|--------|----------|--------------|
| `/dashboard` | Operations Dashboard | ✅ Phase 153 | /operations/today, /tasks, /admin/outbound-health, /admin/reconciliation, /admin/dlq |
| `/tasks` | Task Center + Detail | ✅ Phase 157 | /tasks, /tasks/{id}, /worker/tasks |
| `/bookings` | Bookings List | ✅ Phase 158 | /bookings, /bookings/{id}, /amendments/{id} |
| `/calendar` | Booking Calendar | ✅ Phase 200 | /bookings (date-range filtered) |
| `/financial` | Financial Dashboard | ✅ Phase 163 | /financial/summary, /financial/cashflow, /financial/ota-comparison |
| `/financial/statements` | Owner Statement | ✅ Phase 164 | /owner-statement/{property_id} |
| `/owner` | Owner Portal | ✅ Phase 170 | /owner-statement/{property_id}, /financial/cashflow |
| `/admin` | Admin Settings | ✅ Phase 169 | /admin/registry/providers, /admin/permissions, /admin/dlq |
| `/admin/dlq` | DLQ Replay UI | ✅ Phase 205 | /admin/dlq, /admin/dlq/{id}/replay |
| `/worker` | Worker Mobile | ✅ Phase 157 | /worker/tasks, /worker/tasks/{id}/acknowledge |
| `/login` | Auth Flow | ✅ Phase 178 | JWT collection + redirect |
| `/guests` | Guest Profile | ✅ Phase 193 | /bookings/{id}/guest-profile |

### Status: All Critical Gaps Closed

Both the auth flow and Worker Mobile screen have been built. The system has 12+ deployed screens covering all target role surfaces.

### Invariant: UI never reads Supabase directly

All data flows through FastAPI. This is enforced by architecture — the `ihouse-ui/lib/api.ts` client wraps fetch with `Authorization: Bearer` and targets the FastAPI base URL. No Supabase client is imported in any Next.js component.

---

## When to Build

This is not an instruction to build everything now.

**Suggested entry strategy (for roadmap consideration):**

1. Build API layer first (Phase 113+ — Task Query, Financial Aggregation, etc.)
2. Only build UI when at least 3–4 supporting APIs are stable
3. Start with the **Operations Dashboard** — highest daily value, clearest contract
4. Then **Manager Booking + Task views**
5. Then **Admin settings surfaces**
6. Then **Owner Portal**
7. Worker mobile last (needs stable task + notification stack)

**Rough indicator for "ready to start UI":**
- Task API (Phase 113) is stable
- Financial List + Summary API (Phase 116) is stable
- Reconciliation API (Phase 110) is stable
- At least one worker communication channel is connected

---

## API Alignment Notes (for future phases)

When designing APIs from Phase 113 onward, keep in mind which surface they feed:

| API | Primary UI consumer |
|-----|---------------------|
| `GET /tasks` | Manager Dashboard, Operations Dashboard, Worker |
| `GET /tasks/{id}` | Task Detail, Worker task view |
| `PATCH /tasks/{id}/status` | Worker UI (ack/start/done) |
| `GET /bookings` | Manager Bookings List, Operations Dashboard |
| `GET /financial` | Manager Financial, Admin Financial |
| `GET /financial/summary` | Dashboard strip, Financial Dashboard |
| `GET /admin/reconciliation` | Admin Reconciliation, Manager overview |
| `GET /admin/health` | Admin System Health, Manager summary |

Design all `GET` list endpoints with:
- Filtering (property_id, status, date, provider)
- Pagination or limit
- Tenant isolation always

Design all write endpoints with:
- Permission checks
- Audit events where appropriate

---

## Summary

iHouse Core should become a **role-based operational platform**:

- **Admin** — full system control, governance, settings, integrations
- **Manager** — powerful but bounded operational authority, exception-first daily use
- **Manager + delegated permissions** — Admin-controlled trust extension per manager
- **Worker** — action-first, no noise, mobile-first surfaces per role
- **Owner** — trust-based, financial clarity, no operational complexity
- **Guest** — pre-arrival and stay support *(long-term)*

The philosophy of every UI surface: **fast to read, action-first, no overload.**
The dashboard is not a report. The dashboard is a decision-enabling tool.
