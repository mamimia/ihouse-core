# iHouse Core — Phase 175 Handoff

**Date:** 2026-03-10  
**Closed phase:** 174 (Outbound Sync Stress Harness)  
**Tests passing:** 4,577  
**Pre-existing known failures:** 2 (SQLite guard invariant tests — unrelated to any active work)

---

## What Was Built in This Wave (Phases 165–174)

| Phase | Title | What It Delivered |
|-------|-------|------------------|
| 165 | Properties Metadata API | `GET /properties`, `POST /properties`, property table + RLS |
| 166 | Role-Based Scoping | Worker, owner, manager isolation enforced in routers |
| 167 | Permissions Routing | `PATCH /permissions/{user_id}/grant`, revoke, list |
| 168 | Push Notification Foundation | notification_channels table, dispatcher: LINE > FCM > email |
| 169 | Admin Settings UI | Admin Next.js page + `PATCH /admin/registry/providers/{provider}` |
| 170 | Owner Portal UI | Owner portfolio + statement drawer + payout timeline UI |
| 171 | Admin Audit Log | append-only `admin_audit_log`, `write_audit_event()`, `GET /admin/audit-log` |
| 172 | Health Check Enrichment | Outbound sync probes in `GET /health` |
| 173 | IPI — Proactive Availability Broadcasting | `broadcast_availability()`, `POST /admin/broadcast/availability`, audit debt closed |
| 174 | Outbound Sync Stress Harness | Groups I–O appended to E2E harness (449 tests in harness file) |

---

## System State As Of Phase 174

### Architecture (short form)

```
OTA webhooks → ingest → apply_envelope → booking_state (write authority)
                                       ↓
                         event_log (append-only audit)
                                       ↓
                    read models: booking_financial_facts,
                                 outbound_sync_log,
                                 tasks, admin_audit_log
                                       ↓
                    outbound: property_channel_map → build_sync_plan → execute_sync_plan
                                       ↓
                    adapters: airbnb, bookingcom, expedia (api_first)
                              hotelbeds, tripadvisor, despegar (ical_fallback)
```

### Locked Invariants (must never be violated)

1. `apply_envelope` is the ONLY write authority to `booking_state`
2. `booking_id = {provider}_{normalized_ref}` — stable across all phases
3. `booking_state` must NEVER contain financial calculations
4. `occurred_at` from OTA payload; `recorded_at` from server ingestion time
5. Reconciliation layer is READ-ONLY — corrections go through the canonical pipeline
6. UI never reads Supabase directly — all data through FastAPI
7. Admin audit log is append-only — no UPDATE or DELETE permitted
8. CRITICAL ACK SLA = 5 minutes (locked in `task_model.py:CRITICAL_ACK_SLA_MINUTES`)

---

## UI Surfaces Deployed

| Route | Screen | Phase |
|-------|--------|-------|
| `/dashboard` | Operations Dashboard (7AM rule — arrivals, sync health, tasks, reconciliation) | 153 |
| `/tasks` | Task Center + Task Detail | 157 |
| `/bookings` | Bookings List (by property/status/date) | 158 |
| `/financial` | Financial Dashboard (summary, cashflow, OTA comparison) | 163 |
| `/owner` | Owner Portal (portfolio, statements, payout timeline) | 170 |
| `/admin` | Admin Settings (provider registry, permissions, DLQ) | 169 |

---

## Key Files Reference

### Backend Sources

| File | Role |
|------|------|
| `src/main.py` | FastAPI app + all router registrations |
| `src/core/apply_envelope.py` | Canonical write authority |
| `src/services/outbound_sync_trigger.py` | `build_sync_plan()` — Phase 137 |
| `src/services/outbound_executor.py` | `execute_sync_plan()` — Phase 138 |
| `src/services/outbound_availability_broadcaster.py` | Phase 173 IPI broadcaster |
| `src/adapters/outbound/__init__.py` | `_throttle`, `_retry_with_backoff`, `_build_idempotency_key` |
| `src/adapters/outbound/airbnb_adapter.py` | Airbnb: send/cancel/amend |
| `src/adapters/outbound/bookingcom_adapter.py` | Booking.com: send/cancel/amend |
| `src/adapters/outbound/expedia_vrbo_adapter.py` | Expedia/VRBO: send/cancel/amend |
| `src/adapters/outbound/ical_push_adapter.py` | iCal: push/cancel (hotelbeds, tripadvisor, despegar) |
| `src/api/admin_router.py` | `write_audit_event()` + audit log endpoint |
| `src/channels/notification_dispatcher.py` | Multi-channel dispatcher (LINE > FCM > email) |
| `src/tasks/task_model.py` | TaskKind, TaskStatus, CRITICAL_ACK_SLA_MINUTES |
| `src/services/sla_engine.py` | SLA escalation: ACK_SLA_BREACH + COMPLETION_SLA_BREACH |

### Test Files (Phase 174 additions)

| File | Tests | Scope |
|------|-------|-------|
| `tests/test_e2e_integration_harness.py` | 449 | Groups A–O (inbound + outbound) |
| `tests/test_availability_broadcaster_contract.py` | 35 | Phase 173 broadcaster |
| `tests/test_health_enriched_contract.py` | 20 | Phase 172 health probes |
| `tests/test_admin_audit_log_contract.py` | 28 | Phase 171 audit log |
| `tests/test_notification_dispatcher_contract.py` | 27 | Phase 168 dispatcher |

---

## Top 5 Priorities For The Next Session

### 1. Auto-wire outbound sync into inbound lifecycle (`service.py`)
**Why:** BOOKING_CREATED/CANCELED/AMENDED currently do not automatically fire `build_sync_plan` → `execute_sync_plan`. The trigger exists (Phase 137) and the broadcaster exists (Phase 173) but nothing calls them from `service.py` after a successful `apply_envelope`. This is the single biggest integration gap.

**How:** In `service.py`, after each successful BOOKING_CREATED/CANCELED/AMENDED APPLIED, call `broadcast_availability()` (or a lighter `_fire_outbound_sync()`) for the affecting property.

### 2. Bridge SLA engine → notification dispatcher
**Why:** `sla_engine.py` emits `EscalationResult` with `actions = ['notify_ops', 'notify_admin']`, but there is no code that takes those actions and routes them to `notification_dispatcher.dispatch_notification()`. The two systems are adjacent but disconnected.

**How:** Create `sla_escalation_bridge.py` that consumes `EscalationResult` and calls `dispatch_notification()` with the appropriate message built from task context.

### 3. Worker Mobile UI (`/worker` route)
**Why:** The task model (Phase 111), task persistence (Phase 114), worker task surface (Phase 123), and LINE channel (Phase 124) are all live. The worker role is the only one without a dedicated UI surface.

**How:** Add `ihouse-ui/app/worker/page.tsx` — role-filtered task list, acknowledge/complete buttons, per-task detail, property address. Mobile-first layout.

### 4. Real JWT auth flow in UI
**Why:** The current Next.js app assumes a token is externally provided — there is no login page or token collection. This is the blocker for any real user testing.

**How:** Add `ihouse-ui/app/login/page.tsx`, POST to a new `POST /auth/login` endpoint (or use Supabase auth), store JWT in `localStorage` / httpOnly cookie, redirect unauthorised routes.

### 5. Audit events on booking state mutations
**Why:** Admin actions (grant/revoke permission, patch provider) are now audited (Phase 173 debt closure). But BOOKING_CREATED / BOOKING_CANCELED / BOOKING_AMENDED state changes are not written to `admin_audit_log`. This is the most important operational audit gap.

**How:** In `apply_envelope.py` or `service.py`, after each successful state mutation, call `write_audit_event()` with `action="booking.state_changed"`, `target_type="booking"`, `target_id=booking_id`, `before_state` / `after_state`.

---

## Environment / Setup Notes

```bash
# Run tests (always set these env vars)
PYTHONPATH=src IHOUSE_THROTTLE_DISABLED=true IHOUSE_RETRY_DISABLED=true \
  .venv/bin/pytest --tb=short -q

# Run UI dev server
cd ihouse-ui && npm run dev

# Run FastAPI
PYTHONPATH=src .venv/bin/uvicorn main:app --reload --port 8000
```

Pre-existing SQLite failures (2) are invariant guard tests in `tests/invariants/test_invariant_suite.py`. They have been failing since before Phase 165 and are unrelated to any recent work.

---

## Documentation State

| Document | Last Updated | Reflects |
|----------|-------------|----------|
| `docs/core/current-snapshot.md` | Phase 174 | ✅ Current |
| `docs/core/construction-log.md` | Phase 174 | ✅ Current |
| `docs/core/system-audit-phase175.md` | Phase 175 | ✅ New — gap analysis |
| `docs/core/roadmap.md` | Phase 106 | ⚠️ Outdated — needs Phase 107–174 completion table |
| `docs/core/planning/phases-150-175.md` | Phase 175 planning | ✅ Current |
| `docs/core/planning/ui-architecture.md` | Phase 165 | ⚠️ Partially outdated — does not reflect 6 deployed screens |
| `docs/core/phase-timeline.md` | Phase 165 | ⚠️ Needs Phase 166–174 entries |

The most important documentation debt is `roadmap.md` — it reflects state as of Phase 106. A Phase 176 early step should be a roadmap refresh (similar to Phase 92 and Phase 107) to update the completion table for Phases 107–175 and extend the forward plan.
