# iHouse Core — Next 30 Phases (141–170)

**Written:** 2026-03-10
**System state at writing:** Phase 140 closed, 3589 tests passing.
**Branch:** `checkpoint/supabase-single-write-20260305-1747`

> These phases are a forward planning document, not a binding contract.
> They are ordered logically — each phase depends on the previous ones.
> The new chat that runs this should re-read and adjust if needed.

---

## Outbound Stabilisation (141–144)

### Phase 141 — Rate-Limit Enforcement
**Goal:** Honour `rate_limit` (calls/minute) from SyncAction in all 5 outbound adapters.
Add a `_throttle(rate_limit)` helper (token bucket or simple sleep) in `adapters/outbound/__init__.py`.
Each adapter calls throttle before the HTTP/PUT call.
Tests: call-timing assertions; monkeypatched `time.sleep` capture; zero throttle in dry-run.
No DB changes.

### Phase 142 — Retry + Exponential Backoff in Adapters
**Goal:** On API failure (5xx or network error), each adapter retries up to N times with exponential
backoff before returning `failed`. Cap: 3 retries, max delay 30 s. Backoff is injected in tests (no real sleep).
Tests: mock 2× 5xx then 200 → status=ok; 3× 5xx → status=failed; network errors included.

### Phase 143 — Idempotency Key on Outbound Requests
**Goal:** Each adapter attaches an `X-Idempotency-Key: {booking_id}:{external_id}:{timestamp_day}`
header to prevent duplicate blocks being pushed to OTA APIs on retry.
Tests: header captured in mock; key format documented; key stable within same calendar day.

### Phase 144 — Outbound Sync Result Persistence
**Goal:** Persist every `ExecutionResult` to a new `outbound_sync_log` Supabase table so operators
can audit what was sent to each OTA, when, and with what status.
Schema: `booking_id, provider, external_id, strategy, status, http_status, message, synced_at`.
No read API yet (Phase 145). append-only, never updates existing rows.
Migrations: Supabase DDL applied via MCP.

---

## Outbound Operational Visibility (145–148)

### Phase 145 — Outbound Sync Log Inspector API
**Goal:** `GET /admin/outbound-log?booking_id=&provider=&status=&limit=` — read from `outbound_sync_log`.
Filters: booking_id, provider, status (ok/failed/dry_run/skipped). Default limit 50, max 200.
Complement to DLQ Inspector (Phase 131). JWT required. Read-only.

### Phase 146 — Sync Health Dashboard
**Goal:** `GET /admin/outbound-health` — aggregate counts from `outbound_sync_log` per provider:
{ provider, ok_count, failed_count, dry_run_count, last_sync_at, failure_rate_7d }.
Operators see at a glance which OTA channels are failing. No DB schema changes beyond Phase 144.

### Phase 147 — Failed Sync Replay
**Goal:** `POST /admin/outbound-replay` — re-execute a failed sync for a specific `booking_id + provider`.
Loads the current sync plan (Phase 137) and runs only the failed provider through the executor.
Write-safe: same fail-isolated, dry-run-on-missing-creds rules as Phase 138+.

### Phase 148 — Sync Result Webhook Callback (Optional External Notification)
**Goal:** After a successful push to any OTA, optionally call a user-configured webhook URL
(`IHOUSE_SYNC_CALLBACK_URL`) with a JSON summary of the sync result.
Useful for external dashboards. No callback → noop. Never retried if callback fails.

---

## iCal Calendar Strengthening (149–151)

### Phase 149 — Full RFC 5545 VCALENDAR Compliance Audit
**Goal:** Audit the iCal payload emitted in Phase 140 against RFC 5545.
Add missing required fields: `DTSTAMP` (now UTC), `SEQUENCE:0`.
Update VCALENDAR `CALSCALE:GREGORIAN`, `METHOD:PUBLISH`.
Tests: validate RFC 5545 REQUIRED fields present; DTSTAMP format YYYYMMDDTHHMMSSZ.

### Phase 150 — iCal VTIMEZONE Support
**Goal:** Infer timezone from `booking_state.property_id` → `property_channel_map.timezone` (new column).
Emit `VTIMEZONE` component when timezone is known; default to UTC when absent.
Schema change: `property_channel_map` gets optional `timezone TEXT` column.
DTSTART / DTEND become `TZID=Region/City:YYYYMMDDTHHMMSS` format.

### Phase 151 — iCal Cancellation Push
**Goal:** When `BOOKING_CANCELED` event is processed, push a cancellation to iCal providers:
Delete the VEVENT from the external calendar (PUT updated .ics with CANCELLED status or empty VCALENDAR).
Trigger: new `cancel_sync_trigger.py` service, wired into the existing outbound executor.

---

## API-first OTA Cancel/Amend Push (152–154)

### Phase 152 — API-first Cancellation Notification
**Goal:** For Airbnb, Booking.com, Expedia/VRBO — send cancellation notification via API on BOOKING_CANCELED.
Each adapter gains a `cancel(external_id, booking_id)` method.
Endpoint: `POST /internal/sync/cancel` — mirrors `/execute` but uses the cancel path.

### Phase 153 — API-first Amendment Notification
**Goal:** For API-first OTAs — send amendment notification on BOOKING_AMENDED.
Each adapter gains `amend(external_id, booking_id, check_in, check_out)`.
New endpoint: `POST /internal/sync/amend`.

### Phase 154 — Unified Sync Dispatcher
**Goal:** Consolidate `/execute` (create), `/cancel`, and `/amend` into a single
`POST /internal/sync/dispatch` endpoint that routes based on event_kind in the request body.
Backward-compatible: existing endpoints remain until Phase 160.

---

## Property + Channel Management (155–157)

### Phase 155 — Property Channel Map Read API
**Goal:** `GET /properties/{property_id}/channels` — list all channel mappings for a property.
`POST /properties/{property_id}/channels` — add a mapping.
`DELETE /properties/{property_id}/channels/{provider}` — remove a mapping.
JWT + tenant-scoped. Foundation for a channel management UI.

### Phase 156 — Provider Capability Registry Read/Write API
**Goal:** `GET /admin/provider-registry` — list all provider entries.
`PATCH /admin/provider-registry/{provider}` — update `is_active`, `rate_limit`, `sync_strategy`.
Admin-only (requires admin claim in JWT). Enables runtime capability configuration without code deploys.

### Phase 157 — Property Metadata (Timezone, Currency, Display Name)
**Goal:** New `properties` table (property_id, tenant_id, display_name, timezone, base_currency, created_at).
Pre-populated from `property_channel_map.property_id` set.
Used by Phase 150 (timezone), owner statements, and RevPAR calculations.
Supabase DDL via MCP + RLS enforced.

---

## Booking State Enrichment (158–161)

### Phase 158 — Booking State Amendment History Read Model
**Goal:** `GET /bookings/{booking_id}/amendments` — list all BOOKING_AMENDED events for a booking
from `event_log`. Returns: version, check_in, check_out, room_count, reason, occurred_at.
Read-only — no write path changes. Complement to Booking Audit Trail (Phase 132).

### Phase 159 — Guest Profile Normalisation
**Goal:** Extract `canonical_guest_name`, `canonical_guest_email`, `canonical_guest_phone`
from OTA payloads (where available) into a new `guest_profile` table (booking_id FK, tenant_id).
PII-aware: separate table, never appears in event_log payload. 10 OTA adapters need extraction logic.

### Phase 160 — Booking State Search and Filter Enhancements
**Goal:** `GET /bookings` extended filters: check_in_from, check_in_to, source, text search on
external_ref. Pagination: cursor-based (next_cursor token). Max 500 per page.

### Phase 161 — Booking Flag API
**Goal:** `PATCH /bookings/{booking_id}/flags` — operator can set structured flags:
`{vip: true, notes: "Pool facing preferred", follow_up: true}`.
Stored in a new `booking_flags` table (booking_id, tenant_id, flags JSONB, updated_at).
Read by `GET /bookings/{booking_id}` (flags field appended to response).

---

## Financial Layer Hardening (162–165)

### Phase 162 — Multi-Currency Conversion Layer
**Goal:** Add an exchange-rate table (`exchange_rates`: from_currency, to_currency, rate, valid_at).
`GET /financial/summary` gains optional `?base_currency=USD` param — converts all figures.
Rates loaded manually first (no live feed yet). Foundation for cross-currency RevPAR.

### Phase 163 — Financial Correction Event
**Goal:** New event kind `BOOKING_FINANCIAL_CORRECTED` in apply_envelope.
Allows operator to post a correction to `booking_financial_facts` (commission override, net_to_property fix).
All corrections audit-logged, never overwrite raw OTA data. Epistemic tier: OPERATOR_MANUAL.

### Phase 164 — Automated Reconciliation Suggestions
**Goal:** `GET /admin/reconciliation/suggestions` — system proposes auto-fixable corrections
(e.g., "commission_amount is 0 but rate is 15% — suggest setting to 450"). Suggestions only,
no auto-apply. Operator manually applies via Phase 163 endpoint.

### Phase 165 — Owner Payout Summary Export
**Goal:** `GET /owner-statement/{property_id}?month=&format=csv` — CSV export of the owner statement.
Columns: booking_id, check_in, check_out, gross, commission, management_fee, owner_net, status.
No new DB schema — reads from existing financial tables.

---

## Operational Hardening + Monitoring (166–170)

### Phase 166 — Structured Log Adoption Pass
**Goal:** Sweep all Phase 130–165 modules and replace ad-hoc `logging.info(...)` calls with
`get_structured_logger(...)` from Phase 80. Adds trace_id propagation from request through
outbound adapters. No functional changes — pure observability improvement.

### Phase 167 — Outbound Sync Stress Test Harness
**Goal:** Extend the Phase 90 E2E harness with outbound scenarios:
- Verify each of the 7 adapters returns the correct AdapterResult shape.
- Verify executor fail-isolation (one adapter failure → others proceed).
- Verify date injection for all 3 iCal providers.
New test group H: outbound sync contract (adds ~30 tests to the harness).

### Phase 168 — Admin Audit Log
**Goal:** New `admin_audit_log` table: every admin action (DLQ replay, sync replay, flag update,
financial correction, channel map change) is appended with: actor_tenant_id, action, target, payload_summary, at.
`GET /admin/audit-log?limit=` read endpoint. Admin-only JWT claim required.

### Phase 169 — Health Check Enrichment
**Goal:** Enhance `GET /health` (Phase 64) with outbound sync health:
- `outbound_sync` probe: returns last successful sync per provider + failure rate.
- `provider_registry` probe: count of active providers.
- `outbound_log_lag` probe: seconds since last outbound_sync_log write.
No write path changes.

### Phase 170 — Handoff to IPI First Outbound Sync
**Goal:** Implement the **IPI (iHouse Property Intelligence) First** outbound strategy.
Instead of reacting to OTA webhook events, iHouse Core proactively pushes availability
windows (next 90/180/365 days) to all channels immediately when a property is created or
its channel map changes. This is the flip from reactive-only to proactive
availability broadcasting — the foundation for becoming the system of record for availability,
not just bookings.

New: `outbound_availability_broadcaster.py` — triggered by property_channel_map inserts/updates.
New endpoint: `POST /internal/sync/broadcast-availability`.
Reads `booking_state` for already-blocked dates, constructs a date-range exclusion list,
pushes the full available window to all channels.

---

## Summary Table

| Phase | Title | Effort | Impact |
|-------|-------|--------|--------|
| 141 | Rate-Limit Enforcement | S | Prevents OTA API bans |
| 142 | Retry + Backoff | S | Resilience |
| 143 | Idempotency Keys | S | Safety |
| 144 | Sync Result Persistence | M | Auditability |
| 145 | Sync Log Inspector API | S | Operational |
| 146 | Sync Health Dashboard | S | Operational |
| 147 | Failed Sync Replay | M | Operational |
| 148 | Sync Callback Webhook | S | Optional |
| 149 | RFC 5545 Compliance | S | Correctness |
| 150 | VTIMEZONE Support | M | Correctness |
| 151 | iCal Cancel Push | M | Lifecycle |
| 152 | API Cancel Push | M | Lifecycle |
| 153 | API Amend Push | M | Lifecycle |
| 154 | Unified Sync Dispatcher | M | Architecture |
| 155 | Channel Map CRUD API | M | Self-serve |
| 156 | Provider Registry API | S | Ops |
| 157 | Property Metadata | M | Foundation |
| 158 | Amendment History API | S | Product |
| 159 | Guest Profile Normalisation | M | Product |
| 160 | Booking Search/Filter | M | Product |
| 161 | Booking Flag API | S | Ops |
| 162 | Multi-Currency Conversion | M | Financial |
| 163 | Financial Correction Event | M | Financial |
| 164 | Reconciliation Suggestions | M | Ops |
| 165 | Owner Payout CSV Export | S | Product |
| 166 | Structured Log Adoption | M | Observability |
| 167 | Outbound Stress Harness | M | Testing |
| 168 | Admin Audit Log | M | Compliance |
| 169 | Health Check Enrichment | S | Monitoring |
| 170 | IPI First Outbound Sync | L | **Strategic** |

**Effort key:** S = 1 session, M = 1-2 sessions, L = 2-3 sessions
