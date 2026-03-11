# iHouse Core — Next 15 Phases (240–254)

**Generated:** Phase 239 (Platform Checkpoint VII)
**System state:** 238 phases closed, ~5,559 tests, 15 OTA adapters (14 + ctrip alias), 61 API routers, 9 Supabase migrations, staging infra live.

---

## Phase 240 — Booking Financial Reconciliation Dashboard API

**Why now:** We have `reconciliation_detector.py` and `reconciliation_model.py` (Phase 89+110), but no unified dashboard endpoint that a manager can query to see the full reconciliation picture across properties.

**Scope:**
- `GET /admin/reconciliation/dashboard` — grouped by property, shows stale/missing/mismatched counts
- Timeline: reconciliation alerts over the last 4 weeks
- Narrative summary (heuristic, no LLM)
- ~12 contract tests

---

## Phase 241 — Booking Lifecycle State Machine Visualization API

**Why now:** `booking_state` tracks events but provides no lifecycle view. Managers need to understand a booking's journey (created → amended → canceled → resolved).

**Scope:**
- `GET /bookings/{booking_id}/lifecycle` — returns ordered event chain with state transitions
- Includes: semantic kind, timestamp, actor (OTA), delta highlights
- ~10 contract tests

---

## Phase 242 — Property Performance Analytics API

**Why now:** We have occupancy, revenue, and tasks per property. Time to synthesize them into a single performance metric per property.

**Scope:**
- `GET /analytics/property/{property_id}` — occupancy rate, ADR (avg daily rate), RevPAR, task SLA compliance, sync success rate
- Configurable date range
- ~12 contract tests

---

## Phase 243 — Bulk Operations API

**Why now:** Managers with 10+ properties need batch capabilities — batch cancel, batch task assignment, batch sync trigger.

**Scope:**
- `POST /admin/bulk/cancel` — cancel multiple bookings (max 50)
- `POST /admin/bulk/tasks/assign` — batch assign tasks to workers
- `POST /admin/bulk/sync/trigger` — trigger sync for multiple properties
- Validation: all-or-nothing with per-item error reporting
- ~15 contract tests

---

## Phase 244 — Webhook Event Log & Replay UI API

**Why now:** DLQ exists but managers can't trace exactly what webhooks arrived and when. Need an event log with search and replay.

**Scope:**
- `GET /admin/events` — paginated event log with filters (provider, property, date range, event_kind)
- `POST /admin/events/{event_id}/replay` — replay a specific event
- ~10 contract tests

---

## Phase 245 — Rate Card & Pricing Rules Engine

**Why now:** Financial layer assumes OTA-provided pricing. Real operators need to set base rates and validate incoming prices against their rate cards.

**Scope:**
- `rate_cards` table (property_id, room_type, season, base_rate, currency)
- `GET /properties/{id}/rate-cards` + `POST /properties/{id}/rate-cards`
- Price deviation alert when incoming booking price differs from rate card by >15%
- Migration + ~12 contract tests

---

## Phase 246 — Multi-Language Support Foundation

**Why now:** AI copilots support 5 languages. API responses are English-only. Need i18n foundation for error messages and notification templates.

**Scope:**
- `src/i18n/` module — language pack loader, template resolver
- Supported: en, th, ja, zh, he
- Error messages i18n (error_models.py upgrade)
- Notification templates i18n (escalation messages)
- ~10 contract tests

---

## Phase 247 — Guest Feedback Collection API

**Why now:** Guest messaging (Phase 236) handles outbound messages. Need to close the loop with structured feedback collection.

**Scope:**
- `guest_feedback` table (booking_id, rating 1-5, category, comment, submitted_at)
- `POST /guest-feedback/{booking_id}` — submit feedback (no auth, verification-token-gated)
- `GET /admin/guest-feedback` — aggregated view with property/date filters
- NPS score calculation per property
- Migration + ~12 contract tests

---

## Phase 248 — Maintenance & Housekeeping Task Templates

**Why now:** Task system (Phases 111-117) handles booking-driven tasks. Need maintenance task templates that aren't tied to bookings.

**Scope:**
- `task_templates` table (name, kind, frequency, property_id, worker_role, priority)
- `GET /admin/task-templates` + `POST /admin/task-templates`
- `POST /admin/task-templates/{id}/instantiate` — create task from template
- ~10 contract tests

---

## Phase 249 — Platform Checkpoint VIII

**Why now:** After 10 feature phases (240-248), audit and stabilize.

**Scope:**
- Read → Audit → Fix → Test → Exit 0
- Update current-snapshot, construction-log, phase-timeline
- No handoff (continue in same chat)

---

## Phase 250 — Booking.com Content API Adapter (Outbound)

**Why now:** Outbound sync framework exists (Phases 135-148) but only handles availability/calendar. Need to push content updates (room descriptions, photos, amenities) to Booking.com.

**Scope:**
- `src/adapters/outbound/bookingcom_content.py` — content push adapter
- `POST /admin/content/push/{property_id}` — trigger content sync to Booking.com
- ~8 contract tests

---

## Phase 251 — Dynamic Pricing Suggestion Engine

**Why now:** Rate cards (Phase 245) provide base rates. Dynamic pricing adds demand-based suggestions.

**Scope:**
- `src/services/pricing_engine.py` — pure function: occupancy + seasonality + competitor rates → suggested price
- `GET /pricing/suggestion/{property_id}` — returns suggested rates for next 30 days
- Heuristic-based (no ML yet)
- ~10 contract tests

---

## Phase 252 — Owner Financial Report API v2

**Why now:** Owner statements (Phase 121+188) are per-period snapshots. Need a self-serve API that owners can query for custom date ranges with drill-down.

**Scope:**
- `GET /owner/financial-report` — custom date range, drill-down by property, booking, OTA
- Exportable format (JSON → CSV helper)
- ~10 contract tests

---

## Phase 253 — Staff Performance Dashboard API

**Why now:** Workers have tasks, SLAs, shifts. Managers need a performance view: response times, SLA compliance, task completion rates per worker.

**Scope:**
- `GET /admin/staff/performance` — aggregated worker metrics
- `GET /admin/staff/performance/{worker_id}` — individual drill-down
- Metrics: avg ACK time, SLA compliance %, tasks completed/day, channel preference
- ~12 contract tests

---

## Phase 254 — Platform Checkpoint IX + Roadmap 255-270

**Why now:** After 253 phases, deep stabilization needed. This is also a handoff checkpoint.

**Scope:**
- Full audit + fix protocol
- next-15-phases-255-270.md
- Handoff document
- Chat close

---

## Priority Rationale

| Phase | Domain | Why this order |
|-------|--------|----------------|
| 240 | Financial | Unifies existing reconciliation into actionable dashboard |
| 241 | Bookings | Gives visibility into booking journey (no new data, new view) |
| 242 | Analytics | Synthesizes existing metrics into performance score |
| 243 | Operations | Multi-property managers need batch efficiency |
| 244 | Observability | Event traceability for debugging and compliance |
| 245 | Pricing | Foundation for revenue optimization |
| 246 | i18n | Required before real multi-market deployment |
| 247 | Guest Experience | Closes feedback loop after messaging |
| 248 | Operations | Non-booking task management for maintenance workflows |
| 249 | Checkpoint | Stabilization after 10 feature phases |
| 250 | Outbound | Content sync extends outbound beyond availability |
| 251 | Revenue | Dynamic pricing builds on rate cards |
| 252 | Owner | Self-serve financial access reduces support load |
| 253 | HR/Operations | Staff accountability and performance visibility |
| 254 | Checkpoint | Deep audit + next roadmap + handoff |
