# iHouse Core — Next 10 Phases (229–238)

> **Written:** Phase 228 Platform Checkpoint V — 2026-03-11
> **Based on:** Full system audit of 227 completed phases, 5,382 tests, 55 API files, 122 test files, 14 OTA adapters, 5 escalation channels, 6 AI copilot endpoints.

---

## Strategic Context

The AI assistive layer (Phases 221–227) is complete. The system now has:
- ✅ Morning briefing, financial explainer, task recommendations, anomaly alerts, guest messaging
- ✅ All 5 communication channels live (LINE, WhatsApp, Telegram, SMS, Email)
- ✅ Full financial ring (extraction → owner statements)
- ✅ Production deployment foundation (Dockerfile, CI/CD)

**What's missing:**
1. **AI accountability** — no log of what AI suggested and what the operator decided
2. **Worker-side AI** — copilot only serves managers; workers have no contextual assists
3. **Operational automation** — shift/schedule management is manual
4. **Guest lifecycle** — pre-arrival exists but the full check-in → stay → check-out chain is not automated
5. **Revenue intelligence** — historical data exists but no forecasting or trends
6. **Platform hardening** — no staging env, no integration tests against real Supabase

---

## Phase 229 — AI Audit Trail

**Why now:** Every AI copilot endpoint (223–227) produces recommendations and drafts. Without a log, there's no accountability. This is the #1 governance gap.

**Scope:**
- `ai_audit_log` table (Supabase migration): `tenant_id`, `request_type`, `endpoint`, `input_summary`, `output_summary`, `generated_by`, `approved_by`, `approved_at`, `action_taken`
- Write helper: `log_ai_interaction()` — called at the end of each copilot endpoint
- `GET /admin/ai-audit-log` — paginated, filterable by endpoint/date/approved_by
- Retroactive wiring into existing copilot endpoints (223–227)
- ~25 contract tests

---

## Phase 230 — Worker Task Copilot

**Why now:** Workers currently see a flat task list. This phase adds contextual intelligence on the worker's mobile surface.

**Scope:**
- `POST /ai/copilot/worker-assist` — given a task_id, returns:
  - Property-specific instructions (access code, Wi-Fi, house rules)
  - Previous task history for this property (last 5 completions)
  - Guest context (name, language, arrival time)
  - Priority justification (why this task is urgent)
- Heuristic fallback (structured bullet list) + LLM overlay (natural language)
- ~20 contract tests

---

## Phase 231 — Guest Pre-Arrival Automation Chain

**Why now:** Phase 206 created pre-arrival tasks. Phase 227 drafts guest messages. This phase chains them: when a booking approaches check-in, auto-generate tasks + auto-draft a check-in message.

**Scope:**
- Scheduled job: `pre_arrival_scanner` — runs daily, finds bookings with check-in in 1-3 days
- Auto-creates pre-arrival tasks (via task_automator)
- Auto-drafts check-in message (via guest_messaging_copilot, draft only — not sent)
- `GET /admin/pre-arrival-queue` — shows upcoming arrivals + draft status
- ~20 contract tests

---

## Phase 232 — Revenue Forecast Engine

**Why now:** Revenue reports (Phase 215) show historical data. This phase adds forward-looking projections using confirmed + pending bookings.

**Scope:**
- `GET /ai/copilot/revenue-forecast` — 30/60/90-day forward revenue projection
- Sources: `booking_state` (confirmed future bookings) + `booking_financial_facts` (historical averages)
- Per-property and portfolio-wide
- Occupancy rate projection (% of available nights booked)
- LLM narrative overlay ("Your March revenue is tracking 15% above February")
- ~20 contract tests

---

## Phase 233 — Shift & Availability Scheduler

**Why now:** Workers exist, tasks exist, SLAs exist — but there's no concept of who is available when. This creates an availability layer.

**Scope:**
- `worker_availability` table: `worker_id`, `tenant_id`, `date`, `start_time`, `end_time`, `status` (AVAILABLE/UNAVAILABLE/ON_LEAVE)
- `POST /worker/availability` — set availability for a date range
- `GET /worker/availability?from=&to=` — query own availability
- `GET /admin/schedule/overview?date=` — manager view: all workers + their slots
- Task-to-worker matching hint in task recommendations (Phase 225)
- ~25 contract tests

---

## Phase 234 — Multi-Property Conflict Dashboard

**Why now:** Conflict detection exists (Phase 86/128/207) but only per-booking. Managers with 10+ properties need a cross-property view.

**Scope:**
- `GET /admin/conflicts/dashboard` — all active conflicts across all properties
- Grouped by property, severity, age
- Includes auto-resolution status from Phase 207
- Timeline view: conflicts per week (last 30 days)
- LLM summary: "3 unresolved conflicts this week, 2 in Sunset Villa"
- ~20 contract tests

---

## Phase 235 — Guest Communication History

**Why now:** Phase 227 drafts messages. This phase stores what was actually sent and tracks the guest communication timeline.

**Scope:**
- `guest_messages` table: `tenant_id`, `booking_id`, `guest_id`, `direction` (INBOUND/OUTBOUND), `channel`, `content_preview`, `sent_at`, `draft_id`
- `POST /guest-messages/{booking_id}` — log a sent message
- `GET /guest-messages/{booking_id}` — timeline of all guest comms
- Link to Phase 227 drafts: when a draft is "approved", it gets logged here
- ~20 contract tests

---

## Phase 236 — Staging Environment & Integration Tests

**Why now:** 236 phases of development with 0 integration tests against a real database. Time to add a staging layer.

**Scope:**
- `docker-compose.staging.yml` — Supabase local + app + test runner
- Integration test suite: `tests/integration/` — 10 smoke tests against real Supabase
  - Create booking → verify in booking_state
  - Financial extraction → verify in booking_financial_facts
  - Task automation → verify in tasks table
  - Copilot endpoints → verify response shapes with real DB
- CI pipeline update: run integration tests on PR (optional, secrets-gated)
- ~10 integration tests

---

## Phase 237 — Platform Checkpoint VI

**Why now:** Every 10 phases we audit. Phases 228–236 introduce AI audit trail, worker copilot, pre-arrival automation, revenue forecasting, scheduling, conflict dashboard, guest comms, and staging.

**Scope:**
- Full documentation sync (roadmap, current-snapshot, phase-timeline, work-context)
- Test count verification
- Handoff document for next AI session
- 0 new code files

---

## Phase 238 — Ctrip / Trip.com Enhanced Adapter

**Why now:** Trip.com adapter exists (Phase 1.5 tier) but uses the generic `tripcom.py` adapter. The Chinese market (Ctrip) has unique requirements: Chinese guest names, CNY pricing, specific cancellation policies. This phase upgrades the adapter.

**Scope:**
- Enhanced `tripcom.py` — Chinese-locale field normalization
- Guest name romanization fallback
- CNY-first pricing with multi-currency display
- Ctrip-specific cancellation reason codes
- ~15 contract tests

---

## Priority Rationale

| Phase | Domain | Why this order |
|-------|--------|----------------|
| 229 | AI Governance | Must come first — every AI endpoint needs accountability |
| 230 | Worker AI | Extends copilot to the other user persona (workers) |
| 231 | Automation | Chains existing capabilities (tasks + messaging) |
| 232 | Revenue | High business value — forward-looking intelligence |
| 233 | Scheduling | Fills the biggest operational gap (worker availability) |
| 234 | Conflicts | Cross-property view for multi-property managers |
| 235 | Guest Comms | Completes the messaging lifecycle (draft → send → log) |
| 236 | Infrastructure | Overdue — staging + integration tests for quality confidence |
| 237 | Checkpoint | Regular audit cadence |
| 238 | Adapters | Market expansion (China) with concrete business justification |
