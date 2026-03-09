# iHouse Core — UI Product Screens Reference

**Status:** Forward Planning — Canonical Screen Map  
**Date recorded:** 2026-03-09  
**Builds on:** `ui-architecture.md` + `ui-architecture-enhanced.md`  
**Purpose:** Complete route tree, entry surface design, signature feature definitions, and delivery philosophy. Do not duplicate role model or wireframes — those live in the sibling documents.

---

## What This Document Adds

The two existing UI architecture documents cover:
- Role model, delegation, permission manifest model
- Dashboard wireframes (7AM rule, exception-first layout)
- Competitive analysis
- UI state language and design system
- Technology stack recommendations
- API → UI alignment table

This document adds:
- **Complete page tree** with all routes per surface
- **Entry surface design** (shared login, invite-based model)
- **Signature feature definitions** (the 5 things that make iHouse Core different)
- **Worker-initiated issue flow** (a key product differentiator)
- **Delivery philosophy and phasing** (in the right order)

---

## The Entry Surface — Shared Login

One login page for all users. Role is resolved after authentication.

### Design Intent

- Company logo + company name at top
- Email or username field
- Password field
- Primary **Sign In** button — large, single action
- Small secondary link: **Forgot password**
- Workspace or company selection only if the user belongs to more than one tenant
- Role surface selection only if the user has multiple roles (e.g., Manager + Owner)

### Critical Design Decision: No Open Signup

This is **invite-based by design**. New accounts come from Admin invitation or Admin user creation — not from a public signup form. The login page should feel controlled and professional, not like a SaaS trial flow.

> This is intentional. iHouse Core is not a consumer product. It is a B2B operational platform for property businesses. Open signup creates trust problems, support overhead, and tenant pollution.

### Entry Routes

```
/login
/forgot-password
/workspace-select        ← only when multi-tenant user
/role-select             ← only when user has multiple surfaces
```

---

## Complete Page Tree

### 0. Shared Entry

```
/login
/forgot-password
/workspace-select
```

---

### 1. Admin Surface (`/admin`)

```
/admin/dashboard

/admin/bookings
/admin/bookings/:booking_id
/admin/bookings/:booking_id/timeline
/admin/bookings/:booking_id/amendments
/admin/bookings/:booking_id/payment

/admin/financial
/admin/financial/dashboard
/admin/owner-statements

/admin/properties
/admin/properties/:property_id

/admin/operations

/admin/team

/admin/reconciliation
/admin/conflicts
/admin/provider-health
/admin/audit

/admin/integrations
/admin/permissions
/admin/escalations
/admin/notifications
/admin/settings
```

**Admin-only routes (never visible to Manager):**
- `/admin/integrations` — live credentials, provider connections, webhook secrets
- `/admin/permissions` — delegation matrix, role assignment
- `/admin/escalations` — SLA rules, auto-escalation chains
- `/admin/notifications` — channel routing (LINE/WhatsApp/Telegram/email)
- `/admin/settings` — global system config (timezone, naming, financial rules)
- `/admin/audit` — immutable event log viewer

---

### 2. Manager Surface (`/manager`)

```
/manager/dashboard

/manager/bookings
/manager/bookings/:booking_id
/manager/bookings/:booking_id/timeline
/manager/bookings/:booking_id/amendments
/manager/bookings/:booking_id/payment

/manager/operations

/manager/tasks

/manager/properties
/manager/properties/:property_id

/manager/team

/manager/financial

/manager/conflicts
/manager/reconciliation
/manager/provider-health

/manager/issues
```

**Delegation-conditional routes** (shown only if `permission_manifest` grants it):
- Financial routes beyond property snapshot → requires `can_view_full_financial`
- Owner statement review → requires `can_approve_owner_statements`
- Staff channel management → requires `can_manage_staff_channels`

---

### 3. Worker Mobile Surface (`/worker`)

```
/worker/home
/worker/tasks
/worker/tasks/:task_id
/worker/tasks/:task_id/acknowledge
/worker/tasks/:task_id/start
/worker/tasks/:task_id/done
/worker/tasks/:task_id/issue       ← worker-initiated issue report
/worker/issues/new
/worker/history
/worker/profile
```

**Worker role tabs (rendered based on `worker_role` in manifest):**

| Role | Tab label | Default view |
|------|-----------|-------------|
| `WORKER_CLEANER` | My Cleanings | Cleaning task list |
| `WORKER_CHECKIN` | Arrivals / Check-outs | Today arrivals + departures |
| `WORKER_MAINTENANCE` | My Jobs | Open maintenance tasks |

Workers only ever see their own tasks. No cross-property visibility. No financial data. No admin chrome.

---

### 4. Owner Surface (`/owner`)

```
/owner/dashboard

/owner/statements
/owner/statements/:month

/owner/properties
/owner/properties/:property_id

/owner/payouts
/owner/payouts/:payout_id

/owner/stays

/owner/documents
```

**Owner isolation rules (enforced at API level — not just UI):**
- All queries filtered by `owner_id` → `property_id` index in `booking_financial_facts`
- No access to task data, staff data, or other tenants' owners
- Statement PDF generated on demand — not stored publicly
- Monthly view: YYYY-MM granularity, matching `owner_statement` API

---

### 5. Guest Surface (`/guest`) — Long-Term

Not first priority. Plan early, build late.

```
/guest/reservation
/guest/pre-arrival
/guest/check-in
/guest/guide
/guest/check-out
```

> Build only after: worker mobile is stable + communication channels (LINE/WhatsApp) are operational + owner portal is in production. Guest portal without a notification channel is just a static page.

---

## Signature Features — The 5 That Make iHouse Core Different

These are not just ideas. They are product differentiators. They must not be lost in backlog churn.

### 1. Conflict Center

A dedicated real-time screen for booking conflicts — overlapping dates, duplicate refs, missing property links, resolution actions. Competitors hide conflicts in logs. We surface them as first-class actionable events.

**API already exists:** `conflict_detector.py` (Phase 86), `GET /admin/conflicts` (planned)  
**Resolution flow:** Creates override events through the canonical event pipeline — never bypasses `apply_envelope`.

---

### 2. Provider Health Monitor

A live operational screen showing all 11 OTA providers with: last sync time, error count (24h), webhook status (Live/Dead/Slow), and diagnostic hints for degraded providers.

**API already exists:** `GET /admin/health/providers` (Phase 82)  
Built on `event_log` — no additional infrastructure needed.

---

### 3. Booking-Level Financial Timeline

One chronological screen per booking that combines the reservation timeline (BOOKING_CREATED → BOOKING_AMENDED → CHECK_IN) with financial state progression (facts written, net calculated, payout expected).

**APIs already exist:**  
- `GET /admin/bookings/:id/timeline` (Phase 82)  
- `GET /financial/:booking_id` (Phase 67)  
- `GET /amendments/:booking_id` (Phase 104)  
Combining them in the UI is a frontend composition problem — no new backend needed.

---

### 4. Occupancy Intelligence Strip

A compact, color-coded monthly calendar view per property showing: booked nights, pending nights, and available nights. Shows occupancy rate, average nightly rate, and projected revenue inline.

**Data sources:** `booking_state` (dates + status) + `booking_financial_facts` (nightly rate).  
No dedicated API needed at Phase 114 — can be built on existing `GET /bookings` with date range filtering.

---

### 5. Reconciliation Report Screen

A clear, actionable UI for OTA reconciliation findings: what is mismatched, how severe, what action to take. Competitors have reconciliation nowhere. We have it as a first-class screen.

**API already exists:** `GET /admin/reconciliation?include_findings=true` (Phase 110)  
`ReconciliationFindingKind` (7 types), `ReconciliationSeverity` (3 levels) — all defined in Phase 89.

---

## Worker-Initiated Issue Flow — A Product Signature

This should be one of iHouse Core's most noticeable features. No competitor implements this cleanly.

### The Flow

```
Worker sees physical issue (damage, access problem, missing item)
  → Worker opens task in mobile app
    → Worker taps [REPORT ISSUE]
      → Quick form: issue_type + severity + photo + 70-char note
        → System creates ISSUE record (linked to property + current task)
          → System auto-creates MAINTENANCE task
            → System updates property operational_risk
              → System triggers escalation if severity is URGENT
                → Manager sees it in Conflict Queue / Issue Queue within seconds
```

### Why It Matters

- Workers file issues in seconds, not emails that get lost
- Every issue is linked to a property, booking, and task automatically
- Maintenance tasks appear in the task board before the manager even knows
- Photo evidence is attached — no "he said / she said"
- Escalation fires automatically on URGENT issues via the SLA engine

**Backend dependency:** Requires Phase 118 (Worker Communication Channel) to be complete before push notifications fire. The event creation and task automation work today via `task_automator.py`.

---

## Delivery Philosophy — Build in the Right Order

Do not build the UI before the APIs are stable. Do not build the Owner Portal before the financial confidence model is production-grade.

### Correct Build Order

**First (Phases 114–122 — API completion + Operations Dashboard):**
- Complete the task persistence and task writer (Phases 114–115)
- Financial Aggregation API (Phase 116)
- Property Readiness API (Phase 117)
- Worker Communication Channel (Phase 118–119)
- Operations Dashboard API (Phase 120)
- → Build Operations Dashboard UI (Phases 121–122)

**Second (Phases 123–125 — Manager Web App core):**
- Bookings list + booking detail
- Task center
- Property readiness view
- Financial strip + financial list
- Conflict center + reconciliation overview

**Third (Phases 126–128 — Admin Web App):**
- System settings, integrations, provider health
- User management, delegation matrix
- Escalation and notification settings
- Audit log viewer

**Fourth (Phases 129–130 — Owner Portal):**
- Only after `owner_statement` API (Phase 101) + financial confidence is stable
- Revenue view, payout status, statement PDF

**Fifth (Phase 131+ — Worker Mobile):**
- After task persistence (Phase 115) + notification channel (Phase 118–119) are live
- iOS + Android via React Native / Expo

**Last (Phase 135+ — Guest Portal):**
- Lowest operational urgency
- Requires worker mobile + communication channel to be meaningful

---

## What Must Never Happen

| Anti-pattern | Why it breaks the product |
|---|---|
| Open public signup as main entry | Destroys the invite-based trust model |
| Manager === Admin by default | Permission model is the product — not an afterthought |
| One giant dashboard showing all data | Violates the 7AM rule — operators miss critical signals |
| Worker app showing financial or admin data | Violates worker security model + confuses workers |
| Owner portal before financial confidence model is stable | Publishing untrustworthy numbers destroys owner trust permanently |
| Guest portal before communication channels are live | A guest portal with no push notifications is useless |
| UI built around hardcoded role strings | Blocks the delegation model — must be permission-manifest-driven |

---

## Relationship to Existing Documents

| Document | What it covers |
|----------|----------------|
| `ui-architecture.md` | Core role model, delegation design, surface intent |
| `ui-architecture-enhanced.md` | Detailed wireframes, competitive analysis, design system, tech stack |
| `worker-communication-layer.md` | Channel infrastructure (LINE/WhatsApp/Telegram) |
| **This document** | Complete page tree, entry surface, signature features, delivery philosophy |

All four are canonical. None supersedes the others.

---

*Recorded 2026-03-09. Do not rewrite — append updates as new sections if needed.*
