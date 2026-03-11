# iHouse Core — Next 10 Phases (255–264)

**Generated:** Phase 255 (Documentation Audit + Brand Canonical Placement)
**System state:** 254 phases closed, ~5,900 tests, 15 OTA adapters (14 + ctrip alias), 72 API routers, 182 test files, 5 escalation channels, 6 AI copilots.
**External brand:** Domaniqo (domaniqo.com) — see `docs/core/brand-handoff.md`

---

## Phase 255 — Documentation Audit + Brand Canonical Placement *(current — closing)*

**Type:** Documentation audit — no new code.

**Actions:**
- Fixed `current-snapshot.md` header (Phase 253 → 254)
- Added missing Phase 251 to `phase-timeline.md` and `construction-log.md`
- Updated `live-system.md` to Phase 255 — 18 missing endpoints across 7 new sections
- Updated `roadmap.md` — System Numbers, Completed Phases, Active Direction, Where We're Headed
- Created `docs/core/brand-handoff.md` — Domaniqo brand canonical document (Layer C)
- Updated `BOOT.md` — added brand-handoff.md to Layer C list
- Run full test suite → Exit 0

---

## Phase 256 — Codebase Brand Migration (Customer-Facing Surfaces)

**Why now:** The Domaniqo brand is now canonical. All customer-facing surfaces must reflect it. Internal codename (iHouse Core), file names, module names, and env vars stay unchanged.

**Scope:**
- `src/main.py` — FastAPI app title: "iHouse Core API" → "Domaniqo Core API"; description updated
- OpenAPI `/docs` server metadata — brand updated
- User-facing health response strings
- Any API response body strings visible to end users
- ~5 contract tests verifying customer-facing strings

---

## Phase 257 — UI Rebrand (Domaniqo Design System)

**Why now:** The UI folder `ihouse-ui/` currently shows "iHouse" in every page title, nav, and login. With the brand doc defining colors, typography, and tone, the UI must reflect Domaniqo.

**Scope:**
- `ihouse-ui/styles/tokens.css` — replace color tokens:
  - Midnight Graphite `#171A1F`, Stone Mist `#EAE5DE`, Cloud White `#F8F6F2`
  - Deep Moss `#334036`, Quiet Olive `#66715F`, Signal Copper `#B56E45`, Muted Sky `#9FB7C9`
- Typography: Manrope (headlines, weight 600) + Inter (body) via Google Fonts
- All page titles: "iHouse" → "Domaniqo"
- Login page: Domaniqo branding, "See every stay." tagline, "Calm command for modern hospitality."
- App navigation: Domaniqo wordmark
- `ihouse-ui/app/layout.tsx` — metadata title, description
- `ihouse-ui/package.json` — name field update

---

## Phase 258 — Multi-Language Support Foundation (i18n)

**Why now:** AI copilots support 5 languages. API error messages and notification templates are English-only. Required for real multi-market deployment (Thailand, Japan, Latin America).

**Scope:**
- `src/i18n/` module — language pack loader, template resolver
- Supported: en, th, ja, zh, es, ko, he
- Error message i18n (`error_models.py`)
- Notification template i18n (escalation messages across all 5 channels)
- ~15 contract tests

---

## Phase 259 — Bulk Operations API

**Why now:** Multi-property managers need batch capabilities. All individual endpoints exist — this adds batch wrappers.

**Scope:**
- `POST /admin/bulk/cancel` — batch cancel bookings (max 50, per-item error reporting)
- `POST /admin/bulk/tasks/assign` — batch assign tasks to workers
- `POST /admin/bulk/sync/trigger` — trigger outbound sync for multiple properties
- All-or-nothing validation with per-item outcome reporting
- ~18 contract tests

---

## Phase 260 — Webhook Event Log & Replay

**Why now:** DLQ handles failures, but there is no way to trace which webhooks arrived, from which provider, at what time. Event traceability for debugging and compliance.

**Scope:**
- `GET /admin/events` — paginated event log (provider, property, date, event_kind filters)
- `POST /admin/events/{event_id}/replay` — replay specific event
- Pure read from `event_log` — no new tables needed
- ~12 contract tests

---

## Phase 261 — Guest Self-Service Portal API

**Why now:** Guest messaging (Phases 227/236) and feedback (Phase 247) exist. Guests have no self-serve access to view booking, submit requests, or retrieve pre-arrival info. Reduces support load.

**Scope:**
- `GET /guest/booking/{token}` — guest booking view (token-gated, no JWT)
- `GET /guest/pre-arrival/{token}` — pre-arrival info (WiFi, access code, check-in/out times)
- `POST /guest/request/{token}` — service request (late checkout, extra beds, etc.)
- Token generation from booking events (deterministic, short-lived)
- ~15 contract tests

---

## Phase 262 — Production Monitoring & Alerting

**Why now:** Staging environment (Phase 237), CI (Phase 220), and health checks (Phase 64/172) exist. No structured alerting for production incidents: sync failure spikes, DLQ overflow, SLA breach rate.

**Scope:**
- `alert_rules` Supabase table (metric, threshold, channel, cooldown_minutes)
- `GET /admin/alerts` — list active triggered alerts
- `POST /admin/alerts/rules` — create/update alert rule
- Built-in rules: DLQ > threshold, sync failure rate > 20%, SLA ACK breach rate > 10%
- Alert delivery via existing notification channels (dispatcher)
- ~15 contract tests

---

## Phase 263 — Advanced Booking Analytics & Forecasting

**Why now:** Revenue forecast (Phase 233) covers single-property 30/60/90 projection. Portfolio-level analytics are missing: booking lead-time patterns, cancellation patterns, OTA conversion rates, seasonality detection.

**Scope:**
- `GET /analytics/portfolio/trends` — booking velocity, cancellation rate, avg lead-time per property
- `GET /analytics/portfolio/seasonality` — monthly/weekly pattern detection from event_log
- `GET /analytics/ota/conversion` — per-OTA booking creation vs cancellation rates
- Pure heuristic — no ML dependency
- ~18 contract tests

---

## Phase 264 — Platform Checkpoint XI: Full Audit, Doc Rewrite & Handoff

**Why mandatory last:** Full cleanup, all tests green, all docs precisely synchronized, handoff prepared.

**Scope:**
- Full test suite → must be Exit 0
- Audit ALL canonical docs against code reality (Phase 255–263 changes)
- Verify Domaniqo brand is consistent across all customer-facing surfaces
- Update Layer C docs (current-snapshot, live-system, roadmap, work-context)
- Append to phase-timeline.md and construction-log.md (all phases 255–264)
- Create phase specs + ZIP archives for all phases (255–264)
  - ZIP naming: `iHouse-Core-Docs-Phase-N.zip` (new naming convention)
- Write handoff document: `releases/handoffs/handoff_to_new_chat Phase-264.md`

---

## Priority Rationale

| Phase | Domain | Rationale |
|-------|--------|-----------|
| **255** | Audit | Fix doc debt — must come first, non-negotiable |
| **256** | Brand | Customer-facing API strings → Domaniqo, minimal scope |
| **257** | Brand/UI | UI rebrand — makes product look like Domaniqo externally |
| **258** | i18n | Multi-market enabler — blocks real international deployment |
| **259** | Operations | Batch operations — highest-requested multi-property feature |
| **260** | Observability | Event traceability — completes the debugging toolkit |
| **261** | Guest UX | Self-service portal — high product value, low risk |
| **262** | Production | Monitoring — closes the production-readiness gap |
| **263** | Analytics | Portfolio insights — builds on all existing data layers |
| **264** | Audit | Full cleanup + handoff — mandatory last, non-negotiable |
