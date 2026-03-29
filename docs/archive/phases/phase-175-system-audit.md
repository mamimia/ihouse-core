# iHouse Core — System Audit (Phase 175 Checkpoint)

> **Date:** 2026-03-10
> **Closed phase:** 174
> **Tests passing:** 4,577 (2 pre-existing SQLite guard failures, unrelated)
> **UI screens deployed:** 6 (dashboard, tasks, bookings, financial, owner, admin)

---

## Layer 1 — Inbound OTA Pipeline

### ✅ Complete

| Module | Status | Notes |
|--------|--------|-------|
| OTA webhook ingestion (`POST /webhooks/{provider}`) | ✅ | Phase 58 |
| JWT auth middleware | ✅ | Phase 61 |
| Per-tenant rate limiting | ✅ | Phase 62 |
| Payload validation + semantics classification | ✅ | Phases 22–35 |
| `apply_envelope` canonical write authority | ✅ | Phase 35, permanently locked |
| Dead Letter Queue + controlled replay | ✅ | Phases 38–39, 131 |
| Ordering buffer + auto-route | ✅ | Phase 73 |
| 11 OTA adapters: bookingcom, expedia, airbnb, agoda, tripcom, vrbo, gvr, traveloka, makemytrip, klook, despegar | ✅ | Phases 27, 83–85, 88, 94, 96, 98 |
| Schema normalization (dates, prices, canonical fields) | ✅ | Phases 77–78 |
| Idempotency key tracking | ✅ | Phase 79 |
| Replay fixture contract (22 YAML fixtures, 11 providers) | ✅ | Phases 91, 95, 97, 99 |

### ⚠️ Known Gaps

| Gap | Priority | Suggested Phase |
|-----|----------|----------------|
| No Rakuten (Japan) adapter — Northeast Asia market uncovered | Medium | 176+ |
| No Hostelworld adapter — hostel/budget segment uncovered | Low | 180+ |
| `guest_intake` is an in-memory side-table, not wired into booking events | Low | 180+ |
| No webhook signature verification on LINE inbound (dev bypass only) | Medium | Next notification phase |

---

## Layer 2 — Canonical State + Financial Layer

### ✅ Complete

| Module | Status | Notes |
|--------|--------|-------|
| `booking_state` table (Supabase) | ✅ | Core write model |
| `event_log` append-only audit | ✅ | All mutations logged |
| `booking_financial_facts` projection | ✅ | Phase 66 |
| Financial extraction (5 core + hotelbeds) | ✅ | Phase 65, 125 |
| Payment lifecycle projection (7 states) | ✅ | Phase 93 |
| Reconciliation detection (7 FindingKinds) | ✅ | Phases 89, 110 |
| `booking_id = {provider}_{normalized_ref}` stable across platforms | ✅ | Phase 68, locked |
| `occurred_at` vs `recorded_at` separation | ✅ | Phase 76, locked |
| Availability projection (`GET /availability/{property_id}`) | ✅ | Phase 126 |

### ⚠️ Known Gaps

| Gap | Priority | Suggested Phase |
|-----|----------|----------------|
| Financial extraction for Expedia uses commission_percent — still ESTIMATED, no FULL confidence possible | Low | OTA API upgrade |
| No multi-currency conversion — all aggregations stay per-currency | By design | — |
| Guest profile data (Phase 159+) not integrated into `booking_state` queries | Medium | 176+ |
| `booking_financial_facts` has no TTL / archival strategy | Low | 190+ |

---

## Layer 3 — Outbound Sync Stack

### ✅ Complete

| Module | Status | Notes |
|--------|--------|-------|
| Property-channel map (`property_channel_map`) | ✅ | Phase 135 |
| Provider capability registry (`provider_capability_registry`) | ✅ | Phase 136 |
| Sync trigger (`build_sync_plan`) | ✅ | Phase 137 |
| Sync executor (`execute_sync_plan`) | ✅ | Phase 138 |
| 5 outbound adapters: airbnb, bookingcom, expedia (api_first); hotelbeds, tripadvisor, despegar (ical_fallback) | ✅ | Phases 139–140 |
| Rate-limit enforcement (`_throttle`) | ✅ | Phase 141 |
| Retry + exponential backoff (`_retry_with_backoff`) | ✅ | Phase 142 |
| Idempotency key per adapter call | ✅ | Phase 143 |
| Sync result persistence (`outbound_sync_log`) | ✅ | Phase 144 |
| Outbound sync log inspector (`GET /admin/outbound-log`) | ✅ | Phase 145 |
| Sync health dashboard (`GET /admin/outbound-health`) | ✅ | Phase 146 |
| Failed sync replay (`POST /admin/outbound-replay`) | ✅ | Phase 147 |
| Sync result webhook callback | ✅ | Phase 148 |
| iCal VTIMEZONE support (RFC 5545) | ✅ | Phase 150 |
| iCal cancellation push (STATUS:CANCELLED) | ✅ | Phase 151 |
| iCal amendment push | ✅ | Phase 152 |
| API-first cancellation push (Airbnb, Booking.com, Expedia/VRBO) | ✅ | Phase 154 |
| API-first amendment push | ✅ | Phase 155 |
| Proactive availability broadcaster (Phase 173 IPI) | ✅ | Phase 173 |
| E2E outbound stress harness (Groups I–O, 449 tests in harness file) | ✅ | Phase 174 |

### ⚠️ Known Gaps

| Gap | Priority | Suggested Phase |
|-----|----------|----------------|
| `cancel_sync_trigger.py` / `amend_sync_trigger.py` not wired into `service.py` lifecycle events (still manual-trigger only via broadcaster) | High | 176 |
| No automatic sync on BOOKING_CREATED (trigger fires per booking event — requires broadcaster integration into inbound pipeline) | High | 176 |
| Despegar iCal amend not implemented (only push + cancel) | Medium | 177 |
| VRBO uses Expedia API key — no way to distinguish VRBO-specific rate limits | Low | — |
| `outbound_sync_log` has no retention / cleanup job | Low | 190+ |

---

## Layer 4 — Task + Operational Layer

### ✅ Complete

| Module | Status | Notes |
|--------|--------|-------|
| Task model (TaskKind, TaskStatus, TaskPriority, WorkerRole) | ✅ | Phase 111 |
| Task automation from booking events | ✅ | Phase 112 |
| Task query API + status transitions | ✅ | Phase 113 |
| Task persistence (`tasks` table, Supabase) | ✅ | Phase 114 |
| Task writer (upsert + cancel + reschedule) | ✅ | Phase 115 |
| SLA escalation engine (ACK_SLA_BREACH + COMPLETION_SLA_BREACH) | ✅ | Phase 117 |
| Worker task surface (GET + PATCH /worker/tasks) | ✅ | Phase 123 |
| LINE escalation channel (HMAC-SHA256 verified webhook) | ✅ | Phase 124 |
| Multi-channel notification dispatcher (LINE > FCM > email priority) | ✅ | Phase 168 |
| Operations today API (`GET /operations/today`) | ✅ | Phase 153 |

### ⚠️ Known Gaps

| Gap | Priority | Suggested Phase |
|-----|----------|----------------|
| FCM adapter is a stub — no real Firebase integration | Medium | 180+ |
| Email adapter is a stub — no real SMTP/SES integration | Medium | 180+ |
| SLA escalation engine does not feed notification dispatcher (escalation emits actions; dispatcher is separate — no auto-bridge) | High | 176 |
| No push notification for task assignment (workers receive tasks via LINE only) | Medium | 180+ |
| `ack_sla_minutes` not surfaced in worker UI | Low | UI pass |
| No supervisor override / reassignment endpoint | Medium | 178+ |

---

## Layer 5 — Financial API Layer

### ✅ Complete

| Module | Status | Notes |
|--------|--------|-------|
| Financial facts query (`GET /financial/{booking_id}`) | ✅ | Phase 67 |
| Financial list query (`GET /financial?property_id=&month=`) | ✅ | Phase 108 |
| Financial aggregation (summary/by-provider/by-property/lifecycle-distribution) | ✅ | Phase 116 |
| Financial dashboard (lifecycle card, RevPAR, lifecycle-by-property) | ✅ | Phase 118 |
| Reconciliation inbox (`GET /admin/reconciliation`) | ✅ | Phase 119 |
| Cashflow / payout timeline (`GET /financial/cashflow`) | ✅ | Phase 120 |
| Owner statement generator (management fee, PDF export) | ✅ | Phase 121 |
| OTA financial health comparison | ✅ | Phase 122 |
| Financial correction API | ✅ | Phase 162 |

### ⚠️ Known Gaps

| Gap | Priority | Suggested Phase |
|-----|----------|----------------|
| No automated reconciliation correction — inbox shows findings, but no one-click apply | Medium | 179+ |
| RevPAR requires `available_room_nights` to be manually seeded — no property calendar | Medium | 178+ |
| PDF export is plain-text (`text/plain`) — not true PDF | Medium | 179+ |
| Owner statement does not handle multi-property owners automatically | Low | 179+ |

---

## Layer 6 — Permissions + Admin + Audit

### ✅ Complete

| Module | Status | Notes |
|--------|--------|-------|
| Permissions router (grant/revoke/list for users) | ✅ | Phase 167 |
| Role scoping (worker, owner, manager isolation) | ✅ | Phase 166 |
| Admin audit log (`GET /admin/audit-log`, append-only) | ✅ | Phase 171 |
| Audit events wired into grant/revoke/patch_provider | ✅ | Phase 173 (debt closed) |
| Provider capability registry PATCH endpoint | ✅ | Phase 169 |
| Health check enrichment (outbound probes in `GET /health`) | ✅ | Phase 172 |
| DLQ inspector | ✅ | Phase 131 |
| Booking audit trail | ✅ | Phase 132 |
| OTA ordering buffer inspector | ✅ | Phase 133 |
| Properties summary dashboard | ✅ | Phase 130 |
| Conflict center API | ✅ | Phase 128 |

### ⚠️ Known Gaps

| Gap | Priority | Suggested Phase |
|-----|----------|----------------|
| No audit event on booking status mutations (only admin actions audited) | Medium | 176 |
| Permissions model is user-level only — no group/role-level delegation | Low | 181+ |
| No session management / token revocation (relies purely on JWT expiry) | Low | 181+ |
| Health check does not probe inbound adapter connectivity | Low | 177 |

---

## Layer 7 — UI Surfaces

### ✅ Deployed (Next.js 14 App Router, `ihouse-ui/`)

| Screen | Route | Status | Backend APIs Used |
|--------|-------|--------|------------------|
| Operations Dashboard | `/dashboard` | ✅ Phase 153 | /operations/today, /tasks, /admin/outbound-health, /admin/reconciliation, /admin/dlq |
| Task Center | `/tasks` | ✅ Phase 157 | /tasks, /tasks/{id}, /worker/tasks |
| Bookings List | `/bookings` | ✅ Phase 158 | /bookings, /bookings/{id}, /amendments/{id} |
| Financial Dashboard | `/financial` | ✅ Phase 163 | /financial/summary, /financial/cashflow, /financial/ota-comparison |
| Owner Portal | `/owner` | ✅ Phase 170 | /owner-statement/{property_id}, /financial/cashflow |
| Admin Settings | `/admin` | ✅ Phase 169 | /admin/registry/providers, /admin/permissions, /admin/dlq |

### ⚠️ Known Gaps

| Gap | Priority | Suggested Phase |
|-----|----------|----------------|
| No Worker Mobile surface (route `/worker`) — task acknowledgement is API-only | High | 176 |
| No Booking Detail page for `/bookings/{id}` — list exists, drill-down missing | Medium | 177 |
| No real auth flow in UI (JWT not collected via login page — assumes externally set token) | High | 176 |
| No real-time refresh (all pages are static fetch on load — no polling/websocket) | Medium | 179+ |
| Admin page PATCH does not surface the audit trail written by Phase 171 | Low | 177 |
| Financial statements page exists but not linked from financial dashboard nav | Low | Next UI pass |
| Owner portal month picker does not deep-link | Low | Next UI pass |

---

## Architecture Invariants — All Still Holding

| Invariant | Phase Locked | Status |
|-----------|-------------|--------|
| `apply_envelope` is the ONLY write authority to `booking_state` | Phase 35 | ✅ Intact |
| `booking_id = {provider}_{normalized_ref}` | Phase 36 | ✅ Intact |
| `booking_state` must NEVER contain financial calculations | Phase 62+ | ✅ Intact |
| `occurred_at` from OTA; `recorded_at` from server | Phase 76 | ✅ Intact |
| Reconciliation layer is READ-ONLY | Phase 89 | ✅ Intact |
| UI never reads Supabase directly — all data through FastAPI | Phase 152 | ✅ Intact |
| Audit log is append-only — no UPDATE/DELETE permitted | Phase 171 | ✅ Intact |
| CRITICAL ACK SLA = 5 minutes (locked in `task_model.py`) | Phase 111 | ✅ Intact |

---

## Test Coverage Summary

| Category | Tests |
|----------|-------|
| Inbound pipeline (adapter, validation, DLQ, replay) | ~900 |
| Financial layer (extraction, projection, APIs) | ~480 |
| Task + SLA + notifications | ~220 |
| Outbound sync stack (adapters, executor, resilience) | ~380 |
| Admin / audit / health / permissions | ~260 |
| UI contract tests (backend endpoints for UI screens) | ~210 |
| E2E / cross-layer harness (inbound + outbound) | ~449 |
| Replay fixture contract | ~375 |
| Reconciliation | ~110 |
| Other / utilities | ~190 |
| **Total** | **~4,577** |

---

## Top Priority Gaps for Phase 176+

1. **Auto-trigger outbound on inbound events** — BOOKING_CREATED/CANCELED/AMENDED should fire sync trigger automatically via service.py, not just via broadcaster endpoint.
2. **SLA engine → notification dispatcher bridge** — escalation actions are emitted but not routed to dispatcher. These two systems are currently disconnected.
3. **Worker Mobile UI** — the task model is complete; the worker surface is the only role-facing UI not yet built.
4. **Real UI auth flow** — login page with JWT collection must be built before any production deployment.
5. **Audit events on booking mutations** — admin actions are audited; booking state mutations are not.
