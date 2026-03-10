# iHouse Core — Revised Roadmap: Phases 150–175

**Written:** 2026-03-10  
**System state at writing:** Phase 149 closed, 3836 tests passing.  
**Supersedes:** `phases-141-190.md` Phases 150–175 section  
**Author:** Antigravity

---

## Why This Revision Exists

The original Phase 150–190 plan was all API/backend, including what it labelled "UI Layer" phases
(181–185), which were really just more API endpoints.

After Phase 149, the system has 3836 passing tests and covers:
- Full inbound pipeline across 11 OTAs
- Full outbound sync to 5 channels with resilience (rate-limit, retry, idempotency)
- Operations APIs: tasks, financial aggregation, sync health, reconciliation, owner statements
- Worker and LINE escalation channels

**The power is real. But nothing is visible without Postman.**

The revised plan introduces **four UI blocks** interleaved with the remaining critical backend work.

---

## Rhythm

```
Backend Block A (150–151) — close iCal lifecycle
UI Block 1     (152–153) — Operations Dashboard
Backend Block B (154–156) — outbound lifecycle + property metadata
UI Block 2     (157–158) — Worker Mobile + Booking View
Backend Block C (159–162) — guest data + financial hardening
UI Block 3     (163–164) — Financial Dashboard + Owner Statement
Backend Block D (165–168) — permissions + notifications
UI Block 4     (169–170) — Admin Settings + Owner Portal
Backend Block E (171–174) — hardening + IPI
Milestone      (175)     — Platform Checkpoint
```

---

## Tech Stack (UI Blocks)

| Decision | Choice |
|----------|--------|
| Framework | Next.js 14 App Router |
| Styling | Tailwind CSS |
| API client | Fetch with JWT (from existing auth) |
| Auth | Existing Phase 61 JWT — no new auth layer |
| Data source | FastAPI only — never direct Supabase from UI |
| Deployment | Alongside FastAPI, same domain |

> **Invariant:** The UI never reads Supabase directly. All data flows through FastAPI.
> This preserves tenant isolation (Phase 61) and rate limiting (Phase 62).

---

## Backend Block A — Close iCal Lifecycle (150–151)

### Phase 150 — iCal VTIMEZONE Support

**Goal:** RFC 5545 compliance continuation.  
Infer timezone from `property_channel_map.timezone` (new column, nullable).  
When timezone is known: emit `VTIMEZONE` component + `TZID=Region/City:YYYYMMDDTHHMMSS` for DTSTART/DTEND.  
When absent: default UTC behaviour unchanged (safe regression-free path).

**Schema change:** `ALTER TABLE property_channel_map ADD COLUMN timezone TEXT;`

Files:
| File | Change |
|------|--------|
| `migrations/phase_150_property_channel_map_timezone.sql` | NEW — ADD COLUMN |
| `src/adapters/outbound/ical_push_adapter.py` | VTIMEZONE block + TZID-qualified dates |
| `tests/test_ical_timezone_contract.py` | NEW — ~20 contract tests |

Tests: ~20. DB: 1 column added.

---

### Phase 151 — iCal Cancellation Push

**Goal:** When `BOOKING_CANCELED` is processed, push cancellation `.ics` to iCal providers.  
VEVENT with `STATUS:CANCELLED` (RFC 5545 §3.8.1.11). Wired into `service.py` best-effort block after BOOKING_CANCELED APPLIED — identical pattern to `task_writer.py`.

Files:
| File | Change |
|------|--------|
| `src/services/cancel_sync_trigger.py` | NEW — BOOKING_CANCELED → iCal push |
| `src/adapters/outbound/ical_push_adapter.py` | `cancel(booking_id, external_id)` method |
| `src/services/service.py` | Wire cancel_sync_trigger after BOOKING_CANCELED APPLIED |
| `tests/test_ical_cancel_push_contract.py` | NEW — ~22 contract tests |

Tests: ~22. DB: none.

---

## UI Block 1 — Operations Dashboard (152–153)

### Phase 152 — Next.js Scaffold + Design System

**Goal:** One-time infrastructure phase. Creates the web app shell — every subsequent UI phase builds on this without re-doing setup.

Deliverables:
- `ihouse-ui/` Next.js 14 App Router project (alongside `src/`)
- JWT auth flow: login page → token stored → all API calls use `Authorization: Bearer`
- API client module (`lib/api.ts`) — typed fetch wrapper
- Design tokens: colour palette, typography, spacing, status chip colours
- Layout shell: sidebar nav, header, main content area
- Placeholder routes for: `/dashboard`, `/tasks`, `/bookings`, `/financial`, `/owner`, `/admin`
- Deployed in dev mode alongside FastAPI

Files:
| File | Notes |
|------|-------|
| `ihouse-ui/` | NEW Next.js project |
| `ihouse-ui/lib/api.ts` | Typed fetch client |
| `ihouse-ui/app/layout.tsx` | Root layout + nav |
| `ihouse-ui/styles/tokens.css` | Design system tokens |

Tests: internal Next.js build check. No contract tests (UI phase).

---

### Phase 153 — Operations Dashboard UI

**Goal:** The 7AM screen. Exception-first view of the operational day.

**Route:** `/dashboard`

Sections:
1. **Urgent** — unacked CRITICAL tasks (red), ACK SLA time remaining
2. **Today** — arrivals count, departures count, cleanings due
3. **Sync Health** — per-provider: ok/failed/dry_run icons, last sync timestamp
4. **Reconciliation Alerts** — count of pending reconciliation items (links to details)
5. **Integration Alerts** — DLQ pending count, provider health warnings

API calls (all existing):
- `GET /tasks?status=pending&priority=critical` — Phase 113 ✅
- `GET /operations/today` — simple in-memory aggregation of booking_state (new endpoint, built in this phase)
- `GET /admin/outbound-health` — Phase 146 ✅
- `GET /admin/reconciliation` — Phase 110 ✅
- `GET /admin/dlq?status=pending` — Phase 131 ✅

Files:
| File | Notes |
|------|-------|
| `ihouse-ui/app/dashboard/page.tsx` | Dashboard screen |
| `src/api/operations_router.py` | NEW — `GET /operations/today` (arrivals/departures/cleanings_due) |
| `tests/test_operations_today_contract.py` | NEW — ~15 contract tests for the new endpoint |

Tests: ~15 (the new backend endpoint). No UI contract tests.

---

## Backend Block B — Outbound Lifecycle + Property Foundation (154–156)

### Phase 154 — API-first Cancellation Push

**Goal:** Airbnb, Booking.com, Expedia/VRBO send cancellation via API on BOOKING_CANCELED.  
Each adapter gains `cancel(external_id, booking_id)` method. Wired via `cancel_sync_trigger.py` (Phase 151).

Files:
| File | Change |
|------|--------|
| `src/adapters/outbound/airbnb_adapter.py` | `cancel()` method |
| `src/adapters/outbound/bookingcom_adapter.py` | `cancel()` method |
| `src/adapters/outbound/expedia_vrbo_adapter.py` | `cancel()` method |
| `src/services/cancel_sync_trigger.py` | Extend to call API adapters |
| `tests/test_sync_cancel_contract.py` | NEW — ~25 contract tests |

Tests: ~25. DB: none.

---

### Phase 155 — API-first Amendment Push

**Goal:** Airbnb, Booking.com, Expedia/VRBO send amendment notification on BOOKING_AMENDED.  
Each adapter gains `amend(external_id, booking_id, check_in, check_out)`. New `amend_sync_trigger.py` wired into `service.py` after BOOKING_AMENDED APPLIED.

Files:
| File | Change |
|------|--------|
| `src/adapters/outbound/airbnb_adapter.py` | `amend()` method |
| `src/adapters/outbound/bookingcom_adapter.py` | `amend()` method |
| `src/adapters/outbound/expedia_vrbo_adapter.py` | `amend()` method |
| `src/services/amend_sync_trigger.py` | NEW |
| `src/services/service.py` | Wire amend_sync_trigger |
| `tests/test_sync_amend_contract.py` | NEW — ~25 contract tests |

Tests: ~25. DB: none.

---

### Phase 156 — Property Metadata Table

**Goal:** Canonical store for property display info. Needed by all UI surfaces.

Schema:
```sql
CREATE TABLE properties (
  id             BIGSERIAL PRIMARY KEY,
  property_id    TEXT NOT NULL,
  tenant_id      TEXT NOT NULL,
  display_name   TEXT,
  timezone       TEXT DEFAULT 'UTC',
  base_currency  CHAR(3) DEFAULT 'USD',
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, property_id)
);
```
RLS: tenant isolation required.

Files:
| File | Change |
|------|--------|
| `migrations/phase_156_properties_table.sql` | NEW DDL |
| `src/api/properties_router.py` | NEW — GET /properties, POST /properties, GET /properties/{id}, PATCH /properties/{id} |
| `tests/test_properties_router_contract.py` | NEW — ~25 contract tests |

Tests: ~25. DB: new table.

---

## UI Block 2 — Worker Mobile + Booking View (157–158)

### Phase 157 — Worker Task Mobile View UI

**Goal:** Mobile-optimised task surface for cleaners, check-in staff, maintenance.

**Route:** `/tasks` (mobile-first layout, works on phone browser)

Sections:
1. **My Tasks Today** — sorted by due_time, filtered by worker_role (from JWT)
2. Task card: property address, kind (CLEANING/CHECKIN_PREP), priority chip, due time, status
3. **Actions:** Acknowledge → Start → Complete (single-tap flow)
4. Notes field on completion
5. Overdue indicator (red) + SLA countdown for CRITICAL

API calls (all existing):
- `GET /worker/tasks` — Phase 123 ✅
- `PATCH /worker/tasks/{id}/acknowledge` — Phase 123 ✅
- `PATCH /worker/tasks/{id}/complete` — Phase 123 ✅

Files:
| File | Notes |
|------|-------|
| `ihouse-ui/app/tasks/page.tsx` | Mobile task list |
| `ihouse-ui/app/tasks/[id]/page.tsx` | Task detail + action buttons |

Tests: none (UI phase — backend already tested).

---

### Phase 158 — Manager Booking View UI

**Goal:** Booking list with filters + booking detail screen for managers.

**Routes:** `/bookings` (list) + `/bookings/[id]` (detail)

List screen:
- Filters: property, status (active/canceled), check-in date range, OTA provider
- Booking row: booking_id, guest OTA, check-in/out, property, status chip
- Pagination: cursor-based or page offset

Detail screen (tabs):
- **Overview** — booking_state fields, guest info
- **Outbound Sync** — sync log per provider from `GET /admin/outbound-log?booking_id=`
- **Tasks** — tasks linked to this booking
- **Financial** — lifecycle status + facts card from Phase 93/118
- **History** — amendment history (lightweight endpoint built here)

New backend endpoint added in this phase:
- `GET /bookings/{booking_id}/amendments` — reads `event_log` for BOOKING_AMENDED events for this booking (lightweight, ~15 tests)

API calls:
- `GET /bookings` — Phase 106 ✅
- `GET /bookings/{id}` — Phase 71 ✅
- `GET /admin/outbound-log?booking_id=` — Phase 145 ✅
- `GET /tasks?booking_id=` — extend Phase 113 filter (1 line)
- `GET /financial/{booking_id}` — Phase 67 ✅
- `GET /payment-status/{booking_id}` — Phase 103 ✅

Files:
| File | Notes |
|------|-------|
| `ihouse-ui/app/bookings/page.tsx` | Booking list |
| `ihouse-ui/app/bookings/[id]/page.tsx` | Booking detail |
| `src/api/bookings_router.py` | Add `/{booking_id}/amendments` sub-route |
| `tests/test_booking_amendment_history_contract.py` | NEW — ~15 tests |

Tests: ~15 (new endpoint).

---

## Backend Block C — Guest Data + Financial Hardening (159–162)

### Phase 159 — Guest Profile Normalisation

Extract canonical guest fields from OTA payloads. PII stored separately, never in event_log.

Schema:
```sql
CREATE TABLE guest_profile (
  id          BIGSERIAL PRIMARY KEY,
  booking_id  TEXT NOT NULL,
  tenant_id   TEXT NOT NULL,
  guest_name  TEXT,
  guest_email TEXT,
  guest_phone TEXT,
  source      TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (booking_id, tenant_id)
);
```

Files:
| File | Change |
|------|--------|
| `migrations/phase_159_guest_profile.sql` | NEW DDL |
| `src/adapters/ota/guest_profile_extractor.py` | NEW — per-provider extraction |
| `src/services/service.py` | Best-effort guest profile write after BOOKING_CREATED |
| `src/api/guest_profile_router.py` | `GET /bookings/{id}/guest-profile` |
| `tests/test_guest_profile_contract.py` | NEW — ~35 tests |

Tests: ~35.

---

### Phase 160 — Booking Flag API

Operator annotations on bookings. Surfaced in booking detail view.

Files:
| File | Change |
|------|--------|
| `migrations/phase_160_booking_flags.sql` | NEW DDL |
| `src/api/bookings_router.py` | PATCH `/{booking_id}/flags` + GET enriched with flags |
| `tests/test_booking_flags_contract.py` | NEW — ~22 tests |

Tests: ~22.

---

### Phase 161 — Multi-Currency Conversion Layer

Exchange-rate table + optional `?base_currency=` on financial summary endpoints.

Files:
| File | Change |
|------|--------|
| `migrations/phase_161_exchange_rates.sql` | NEW DDL |
| `src/api/financial_aggregation_router.py` | Add `base_currency` param + conversion logic |
| `tests/test_multicurrency_conversion_contract.py` | NEW — ~30 tests |

Tests: ~30.

---

### Phase 162 — Financial Correction Event

Operator can post a correction to `booking_financial_facts`. Audit-logged. Confidence: `OPERATOR_MANUAL`.

Files:
| File | Change |
|------|--------|
| `src/api/financial_correction_router.py` | NEW — `POST /financial/corrections` |
| `src/adapters/ota/financial_writer.py` | Support OPERATOR_MANUAL confidence tier |
| `tests/test_financial_correction_contract.py` | NEW — ~25 tests |

Tests: ~25.

---

## UI Block 3 — Financial Dashboard + Owner Statement (163–164)

### Phase 163 — Financial Dashboard UI

**Goal:** Portfolio-level financial view for managers and admins.

**Route:** `/financial`

Sections:
1. **Summary bar** — gross revenue / OTA commission / net to portfolio / payout pending / payout released (period selector)
2. **Provider breakdown** — table per OTA: bookings, gross, commission, net, avg rate, net-to-gross ratio
3. **Property breakdown** — per property: RevPAR, gross, net, booking count
4. **Lifecycle distribution** — visual breakdown of 7 payment states
5. **Reconciliation inbox** — exception count chip + link to detail

API calls (all existing):
- `GET /financial/summary` — Phase 116 ✅
- `GET /financial/by-provider` — Phase 116 ✅
- `GET /financial/by-property` — Phase 116 ✅
- `GET /financial/revpar` — Phase 118 ✅
- `GET /financial/lifecycle-distribution` — Phase 116 ✅
- `GET /admin/reconciliation` — Phase 119 ✅

Files:
| File | Notes |
|------|-------|
| `ihouse-ui/app/financial/page.tsx` | Financial dashboard |

Tests: none (UI phase).

---

### Phase 164 — Owner Statement UI

**Goal:** Monthly statement per property, readable by managers and (later) owners.

**Route:** `/financial/statements`

Sections:
1. **Property + month selector**
2. **Per-booking line items** — check-in/out, OTA, gross, commission, net, epistemic tier badge (✅🔵⚠️)
3. **Totals** — gross / total commission / management fee (configurable %) / **owner net**
4. **Payout status per booking** — released / pending / reconciliation_pending chip
5. **Export** — PDF (existing Phase 121 plain-text) + link for CSV

API calls (all existing):
- `GET /owner-statement/{property_id}?month=&management_fee_pct=` — Phase 121 ✅
- `GET /owner-statement/{property_id}?format=csv` — Phase 165 original → build PDF/CSV export inline here

Files:
| File | Notes |
|------|-------|
| `ihouse-ui/app/financial/statements/page.tsx` | Owner statement |

Tests: none (UI phase).

---

## Backend Block D — Permissions + Notifications (165–168)

### Phase 165 — Permission Model Foundation

Schema + JWT enrichment. Foundation for role-scoped UI.

Schema:
```sql
CREATE TABLE tenant_permissions (
  id          BIGSERIAL PRIMARY KEY,
  tenant_id   TEXT NOT NULL,
  user_id     TEXT NOT NULL,
  role        TEXT NOT NULL,  -- 'admin' | 'manager' | 'worker' | 'owner'
  permissions JSONB NOT NULL DEFAULT '{}',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, user_id)
);
```

Files:
| File | Change |
|------|--------|
| `migrations/phase_165_tenant_permissions.sql` | NEW DDL |
| `src/api/auth.py` | Enrich JWT scope with permission lookup |
| `src/api/permissions_router.py` | NEW — CRUD for admin-managed permissions |
| `tests/test_permissions_contract.py` | NEW — ~30 tests |

Tests: ~30.

---

### Phase 166 — Worker + Owner Role Scoping

Enforce role visibility in existing endpoints. Workers see only their tasks. Owners see only their properties.

Files:
| File | Change |
|------|--------|
| `src/api/worker_router.py` | Scope to `worker_role` from permission manifest |
| `src/api/owner_statement_router.py` | Property filter from permission |
| `src/api/financial_aggregation_router.py` | Property filter from permission |
| `tests/test_worker_role_scoping_contract.py` | NEW — ~22 tests |
| `tests/test_owner_role_scoping_contract.py` | NEW — ~20 tests |

Tests: ~42.

---

### Phase 167 — Manager Delegated Permissions

Admin can grant specific capabilities to managers (`can_approve_owner_statements`, `can_manage_integrations`, etc.).

Files:
| File | Change |
|------|--------|
| `src/api/permissions_router.py` | Add grant/revoke endpoints |
| `src/api/auth.py` | Expose permission flags in request context |
| `tests/test_delegated_permissions_contract.py` | NEW — ~25 tests |

Tests: ~25.

---

### Phase 168 — Push Notification Foundation (LINE + FCM)

Infrastructure for push notifications. Registers channels per user. LINE already wired (Phase 124).

Schema:
```sql
CREATE TABLE notification_channels (
  id           BIGSERIAL PRIMARY KEY,
  tenant_id    TEXT NOT NULL,
  user_id      TEXT NOT NULL,
  channel_type TEXT NOT NULL,  -- 'line' | 'fcm' | 'email'
  channel_id   TEXT NOT NULL,
  active       BOOLEAN NOT NULL DEFAULT true,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, user_id, channel_type)
);
```

Files:
| File | Change |
|------|--------|
| `migrations/phase_168_notification_channels.sql` | NEW DDL |
| `src/channels/notification_dispatcher.py` | NEW — route to LINE or FCM |
| `tests/test_notification_dispatcher_contract.py` | NEW — ~25 tests |

Tests: ~25.

---

## UI Block 4 — Admin Settings + Owner Portal (169–170)

### Phase 169 — Admin Settings UI

**Goal:** Channel configuration, provider registry, permission management.

**Route:** `/admin`

Sections:
1. **Channel Map** — list/add/remove property↔provider mappings
2. **Provider Registry** — per provider: is_active toggle, rate_limit, sync_strategy
3. **Permissions** — list users, assign roles, grant/revoke capabilities
4. **DLQ** — pending + applied DLQ entries with replay button

API calls:
- `GET /properties/{id}/channels` + `POST` + `DELETE` (Phase 156 builds)
- `GET /admin/provider-registry` — Phase 136 ✅
- `PATCH /admin/provider-registry/{provider}` — add this inline here
- `GET /admin/dlq` + replay — Phase 131, 147 ✅
- Permissions CRUD — Phase 165 ✅

Tests: ~15 (PATCH provider-registry endpoint added inline).

---

### Phase 170 — Owner Portal UI

**Goal:** Owner-facing monthly revenue and payout view. Role-scoped.

**Route:** `/owner`

Sections:
1. **Portfolio summary** — total revenue this month, payout pending, payout released
2. **Property cards** — per property: month gross, commission, owner net, upcoming stays count
3. **Statement viewer** — link to Phase 164 statement view, scoped to owner's properties
4. **Payout timeline** — upcoming expected inflows per week

API calls (all existing, now role-scoped via Phase 165):
- `GET /financial/summary` — Phase 116 ✅
- `GET /financial/by-property` — Phase 116 ✅
- `GET /financial/cashflow` — Phase 120 ✅
- `GET /owner-statement/{property_id}` — Phase 121 ✅

Files:
| File | Notes |
|------|-------|
| `ihouse-ui/app/owner/page.tsx` | Owner portal dashboard |

Tests: none (UI phase).

---

## Backend Block E — Hardening + IPI (171–174)

### Phase 171 — Admin Audit Log

Every admin action permanently recorded. Compliance trail.

Files:
| File | Change |
|------|--------|
| `migrations/phase_171_admin_audit_log.sql` | NEW DDL |
| `src/api/admin_router.py` | Wire audit writes + `GET /admin/audit-log` |
| `tests/test_admin_audit_log_contract.py` | NEW — ~28 tests |

Tests: ~28.

---

### Phase 172 — Health Check Enrichment

Enhance `GET /health` with outbound sync probes (last sync per provider, 7d failure rate, log lag).

Files:
| File | Change |
|------|--------|
| `src/api/health.py` | Add outbound probes |
| `tests/test_health_enriched_contract.py` | NEW — ~20 tests |

Tests: ~20.

---

### Phase 173 — IPI — Proactive Availability Broadcasting

Flip from reactive-only to proactive. Push availability windows to all channels when property is created or channel map changes. Foundation: system of record for availability, not just bookings.

Files:
| File | Change |
|------|--------|
| `src/services/outbound_availability_broadcaster.py` | NEW |
| `src/api/outbound_executor_router.py` | Add `POST /internal/sync/broadcast-availability` |
| `tests/test_availability_broadcaster_contract.py` | NEW — ~30 tests |

Tests: ~30.

---

### Phase 174 — Outbound Sync Stress Harness

Extend Phase 90 E2E harness with outbound scenarios. All 5 adapters, cancel/amend paths, throttle/retry propagation.

Files:
| File | Change |
|------|--------|
| `tests/test_e2e_integration_harness.py` | EXTENDED — outbound group |

Tests: ~30 new tests added to harness.

---

## Phase 175 — Platform Checkpoint

**Goal:** System audit, docs refresh, handoff document before next wave.

Deliverables:
1. Update `docs/core/current-snapshot.md` — Phase 175 state
2. Update `docs/core/roadmap.md` — Phases 150–175 completion table
3. Create `docs/core/system-audit-phase175.md` — gap analysis
4. Write `releases/handoffs/handoff_to_new_chat Phase-175.md`
5. Update `docs/core/planning/ui-architecture.md` — reflect actual UI state

Expected: ~5500+ tests, 6 real UI screens deployed, full outbound lifecycle, role-based product surfaces.

---

## Summary Table

| Phase | Title | Type | Key Dependency |
|-------|-------|------|----------------|
| 150 | iCal VTIMEZONE | Backend | Phase 149 |
| 151 | iCal Cancel Push | Backend | Phase 149 |
| **152** | **Next.js Scaffold** | **UI** | — first build — |
| **153** | **Operations Dashboard** | **UI** | Ph 110,113,131,146 |
| 154 | API Cancel Push | Backend | Ph 139,151 |
| 155 | API Amendment Push | Backend | Ph 139 |
| 156 | Property Metadata Table | Backend | Foundation for UI |
| **157** | **Worker Mobile UI** | **UI** | Ph 123 |
| **158** | **Manager Booking View UI** | **UI** | Ph 71,106,109,145 |
| 159 | Guest Profile Normalisation | Backend | Product data |
| 160 | Booking Flag API | Backend | Ph 71 |
| 161 | Multi-Currency Conversion | Backend | Ph 116 |
| 162 | Financial Correction Event | Backend | Ph 119 |
| **163** | **Financial Dashboard UI** | **UI** | Ph 116,118,119,120 |
| **164** | **Owner Statement UI** | **UI** | Ph 121,122 |
| 165 | Permission Model Foundation | Backend | Role layer |
| 166 | Worker + Owner Role Scoping | Backend | Ph 165 |
| 167 | Manager Delegated Permissions | Backend | Ph 165 |
| 168 | Push Notification Foundation | Backend | Ph 124 |
| **169** | **Admin Settings UI** | **UI** | Ph 156,165 |
| **170** | **Owner Portal UI** | **UI** | Ph 121,165,168 |
| 171 | Admin Audit Log | Backend | Compliance |
| 172 | Health Check Enrichment | Backend | Monitoring |
| 173 | IPI Proactive Broadcasting | Backend | Strategic |
| 174 | Outbound Stress Harness | Backend | Testing |
| 175 | **Platform Checkpoint** | Milestone | All |

**8 UI phases out of 26 total. 6 distinct product surfaces built.**

---

## Architectural Invariants — Unchanged

All invariants from `phases-141-190.md` remain in force.  
Additionally:

| Invariant | Source |
|-----------|--------|
| UI never reads Supabase directly — all data through FastAPI | This revision |
| UI respects tenant isolation via JWT — same token as API | Phase 61 |
| Role scoping enforced at API layer, not UI layer | Phase 165 |

---

*Document created: 2026-03-10 by Antigravity (Phase 149 closure)*  
*Supersedes: phases-141-190.md Phases 150–175 section*
