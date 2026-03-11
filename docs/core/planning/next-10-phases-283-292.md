# iHouse Core — Next 10 Phases (283–292)

> Written Phase 282, based on full system read.

## System Context at Phase 282

- **243 Python files**, 199 test files, 69 routers, ~6,250 tests
- **14 OTA adapters** (inbound), 4 outbound adapters (Airbnb, Booking.com, Expedia/Vrbo, iCal)
- **5 escalation channels** (LINE, WhatsApp, Telegram, SMS, Email)
- **8 AI copilot endpoints** + audit trail
- **Supabase:** 28 tables, 12 RPCs, apply_envelope as sole write gate
- **CI:** Python 3.14, blocking lint, migrations validation, security gate
- **Production config:** Dockerfile, docker-compose.production.yml, .env.production.example
- **Live staging runner:** scripts/e2e_live_ota_staging.py (Phase 281)

## Gaps Identified

1. **`properties` table** — in migration file but NOT applied to live Supabase
2. **`artifacts/supabase/schema.sql`** — stale (Phase 50 export). Missing BOOKING_AMENDED enum, guest_id, rebuild_booking_state RPC
3. **Test isolation** — 5 p280 tests fail in full-suite ordering (env pollution)
4. **`roadmap.md`** — System Numbers stuck at Phase 272
5. **No `conftest.py`** — per-session env cleanup for webhook secrets not centralized
6. **No real frontend** — all UI routers return JSON, no Next.js/Vite frontend exists
7. **`live-system.md`** — stuck at Phase 273 header
8. **No health/liveness probes in production compose** — docker-compose.production.yml missing HEALTHCHECK

---

## Phase 283 — Test Suite Isolation Fix + conftest.py

**Goal:** Eliminate all test ordering failures.
- Create `tests/conftest.py` with session-scoped autouse fixture clearing all `IHOUSE_WEBHOOK_SECRET_*`, `IHOUSE_JWT_SECRET`, `IHOUSE_DEV_MODE`
- Fix 5 p280 full-suite ordering failures
- Fix 10 pre-existing `test_worker_copilot_contract.py` failures
- Target: 0 failures in full suite, exit 0

---

## Phase 284 — Supabase Schema Truth Sync

**Goal:** Align live Supabase schema with documented migrations.
- Apply `properties` table to live Supabase (from `phase_156_properties_table.sql`)
- Re-export `artifacts/supabase/schema.sql` from live DB (capture BOOKING_AMENDED, guest_id, rebuild_booking_state)
- Verify all migrations in `supabase/migrations/` match live state
- Update `supabase/BOOTSTRAP.md` if needed

---

## Phase 285 — Documentation Integrity Sync XIV

**Goal:** Bring all canonical docs to Phase 284 state.
- Update `roadmap.md` System Numbers (test count → ~6,250, phase count → 284)
- Update `live-system.md` header to Phase 284
- Update `roadmap.md` Active Direction for 283–292
- Append 283–284 to phase-timeline.md and construction-log.md
- Verify all ZIPs include full `docs/core/` tree

---

## Phase 286 — Production Docker Hardening

**Goal:** Make production compose deployment-ready.
- Add HEALTHCHECK to `docker-compose.production.yml`
- Add `depends_on` health conditions
- Create `scripts/deploy_checklist.sh` — pre-deploy validation (env vars, DB connectivity, port check)
- Write `docs/core/planning/deployment-guide.md`

---

## Phase 287 — Frontend Foundation (Next.js/Vite)

**Goal:** Create the first real Domaniqo frontend shell.
- Initialize Next.js or Vite project in `ihouse-ui/`
- Supabase Auth integration (login/magic-link)
- Protected route structure
- API client connecting to iHouse Core backend
- Branded with Domaniqo identity (per BOOT.md branding rules)

---

## Phase 288 — Operations Dashboard UI (Live)

**Goal:** Build the first real operational dashboard.
- Connect to `/portfolio/dashboard`, `/ai/context/operations-day`, `/admin/summary`
- Exception-first design ("7 AM Rule" — show only what needs attention)
- Real-time booking card, sync health indicator, task queue
- Mobile responsive

---

## Phase 289 — Booking Management UI (Live)

**Goal:** Build booking list + detail view.
- Connect to `/bookings`, `/bookings/{id}`, `/booking-history/{id}`
- Filter by property, status, date range, OTA provider
- Booking detail: timeline, financial facts, tasks, guest profile
- Status badges, OTA provider icons

---

## Phase 290 — Worker Task View UI (Live)

**Goal:** Build mobile-first worker view.
- Connect to `/worker/tasks`, `/worker/acknowledge`, `/worker/complete`
- Task cards with priority colors, SLA countdown timer
- Pull-to-refresh, offline-friendly design
- Worker copilot integration (`/ai/copilot/worker-assist`)

---

## Phase 291 — Financial Dashboard UI (Live)

**Goal:** Build financial overview for managers.
- Connect to `/financial-aggregation/summary`, `/cashflow/projection`, `/owner-statement`
- Revenue chart, OTA mix donut, occupancy gauge
- Drill-down to per-booking financial facts
- Epistemic tier badges (A/B/C confidence)

---

## Phase 292 — Platform Checkpoint XIV (Audit)

**Goal:** Full system audit after 10 phases.
- Run full test suite
- Verify all phase specs + ZIPs (283–292)
- Update all canonical docs
- Create handoff document
- Git commit + push
