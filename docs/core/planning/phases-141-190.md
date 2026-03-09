# iHouse Core — Next 50 Phases (141–190)

**Written:** 2026-03-10  
**System state at writing:** Phase 140 closed, 3589 tests passing.  
**Branch:** `checkpoint/supabase-single-write-20260305-1747`  
**Author:** Antigravity (new chat boot — post Phase-140 handoff)

> These phases are a forward planning document, not a binding contract.
> They are ordered logically — each phase depends on prior ones.
> Sources: handoff_to_new_chat Phase-140.md, phases-141-170.md, outbound-sync-layer.md,
>          future-improvements.md, ui-architecture.md, system-audit.md
> The executing chat should re-read and adjust if any phase reveals new constraints.

---

## Tier Summary

| Phases | Theme | Strategic Value |
|--------|-------|----------------|
| 141–144 | Outbound Adapter Stabilisation | Prevent OTA API bans, resilience |
| 145–148 | Outbound Operational Visibility | Operators can see sync health |
| 149–151 | iCal RFC Compliance + Lifecycle | Calendar correctness |
| 152–154 | API-first Cancel/Amend Push | Full lifecycle outbound | 
| 155–157 | Property + Channel Management | Self-serve channel config |
| 158–161 | Booking State Enrichment | Richer data model |
| 162–165 | Financial Layer Hardening | Multi-currency, corrections |
| 166–170 | Operational Hardening + IPI | Observability + proactive sync |
| 171–175 | Guest Profile + Pre-Arrival | Guest-facing product layer |
| 176–180 | Permission + Role System | Multi-role product readiness |
| 181–185 | UI Operations Dashboard (API) | Operations command center |
| 186–190 | Owner Portal + Worker Mobile (API) | Owner + worker surfaces |

---

## Outbound Adapter Stabilisation (141–144)

### Phase 141 — Rate-Limit Enforcement
**Goal:** Honour `rate_limit` (calls/minute) from `SyncAction` in all 5 outbound adapters.  
Add `_throttle(rate_limit)` helper in `adapters/outbound/__init__.py` (token-bucket or simple sleep).  
Each adapter calls throttle before the HTTP/PUT call.  
Must be **opt-out-able in tests** (monkeypatch `time.sleep`; no throttle in dry-run/test mode).  
Must NOT block forever if rate_limit is very low — warning log + best-effort.

**Files:**
| File | Change |
|------|--------|
| `src/adapters/outbound/__init__.py` | NEW `_throttle(rate_limit)` helper or `RateLimiter` class |
| `src/adapters/outbound/airbnb_adapter.py` | Call throttle before HTTP |
| `src/adapters/outbound/bookingcom_adapter.py` | Same |
| `src/adapters/outbound/expedia_vrbo_adapter.py` | Same |
| `src/adapters/outbound/ical_push_adapter.py` | Same |
| `tests/test_rate_limit_enforcement_contract.py` | NEW — timing assertions, monkeypatched sleep |

**Tests:** ~20 contract tests. No DB changes.

---

### Phase 142 — Retry + Exponential Backoff in Adapters
**Goal:** On 5xx or network error, each adapter retries up to 3 times with exponential backoff before returning `failed`.  
Cap: 3 retries, max delay 30s. Backoff is injected in tests (no real sleep).  
Backoff sequence: 1s → 4s → 16s (base 2 exponential, jitter optional).

**Files:**
| File | Change |
|------|--------|
| `src/adapters/outbound/__init__.py` | `_retry_with_backoff(fn, max_retries=3)` helper |
| All 4 adapter files | Wrap HTTP call with retry helper |
| `tests/test_adapter_retry_contract.py` | NEW — mock 2×5xx then 200 → ok; 3×5xx → failed |

**Tests:** ~25 contract tests. No DB changes.

---

### Phase 143 — Idempotency Key on Outbound Requests
**Goal:** Each adapter attaches `X-Idempotency-Key: {booking_id}:{external_id}:{date_day}` header to prevent duplicate blocks on retry.  
Key is stable within the same calendar day. Adapters that don't support this header skip gracefully.

**Files:**
| File | Change |
|------|--------|
| `src/adapters/outbound/__init__.py` | `_build_idempotency_key(booking_id, external_id)` helper |
| All 4 adapter files | Attach key in headers dict |
| `tests/test_outbound_idempotency_key_contract.py` | NEW — header captured in mock; key format; day-stable |

**Tests:** ~18 contract tests. No DB changes.

---

### Phase 144 — Outbound Sync Result Persistence
**Goal:** Persist every `ExecutionResult` to a new `outbound_sync_log` Supabase table.  
Append-only — never updates existing rows. No read API yet (Phase 145).

**Schema:**
```sql
CREATE TABLE outbound_sync_log (
  id          BIGSERIAL PRIMARY KEY,
  booking_id  TEXT        NOT NULL,
  tenant_id   TEXT        NOT NULL,
  provider    TEXT        NOT NULL,
  external_id TEXT,
  strategy    TEXT,   -- 'api_first' | 'ical_fallback' | 'dry_run'
  status      TEXT    NOT NULL,  -- 'ok' | 'failed' | 'dry_run' | 'skipped'
  http_status INT,
  message     TEXT,
  synced_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Files:**
| File | Change |
|------|--------|
| `migrations/phase_144_outbound_sync_log.sql` | NEW DDL |
| `src/services/outbound_executor.py` | Write row after each ExecutionResult |
| `tests/test_sync_result_persistence_contract.py` | NEW — verify rows written, append-only |

**Tests:** ~20 contract tests. Supabase DDL via MCP.

---

## Outbound Operational Visibility (145–148)

### Phase 145 — Outbound Sync Log Inspector API
**Goal:** Read-only API to inspect what was sent to each OTA, when, and with what status.

**Endpoint:** `GET /admin/outbound-log?booking_id=&provider=&status=&limit=`  
Filters: booking_id, provider, status (ok/failed/dry_run/skipped). Default limit 50, max 200.  
JWT required. Reads `outbound_sync_log` only. Complement to DLQ Inspector (Phase 131).

**Files:**
| File | Change |
|------|--------|
| `src/api/outbound_log_router.py` | NEW router |
| `src/main.py` | Register router + tag |
| `tests/test_outbound_log_router_contract.py` | NEW — filters, pagination, tenant isolation |

**Tests:** ~25 contract tests.

---

### Phase 146 — Sync Health Dashboard
**Goal:** Aggregate view of outbound sync health per provider.

**Endpoint:** `GET /admin/outbound-health`  
Returns per provider: `{provider, ok_count, failed_count, dry_run_count, last_sync_at, failure_rate_7d}`.  
No DB schema changes beyond Phase 144.

**Files:**
| File | Change |
|------|--------|
| `src/api/outbound_log_router.py` | Add `/admin/outbound-health` endpoint |
| `tests/test_outbound_health_contract.py` | NEW |

**Tests:** ~20 contract tests.

---

### Phase 147 — Failed Sync Replay
**Goal:** Re-execute a failed sync for a specific `booking_id + provider`.  
Loads current sync plan (Phase 137) and runs only the failed provider through the executor.  
Same fail-isolated, dry-run-on-missing-creds rules as Phase 138+.

**Endpoint:** `POST /admin/outbound-replay` body: `{booking_id, provider}`

**Files:**
| File | Change |
|------|--------|
| `src/api/outbound_log_router.py` | Add replay endpoint |
| `src/services/outbound_executor.py` | Single-provider execution path |
| `tests/test_outbound_replay_contract.py` | NEW |

**Tests:** ~22 contract tests.

---

### Phase 148 — Sync Result Webhook Callback
**Goal:** After a successful push to any OTA, optionally call a user-configured webhook URL (`IHOUSE_SYNC_CALLBACK_URL`) with a JSON summary.  
No callback configured → noop. Callback failure is never retried. Never blocks the sync path.

**Files:**
| File | Change |
|------|--------|
| `src/services/outbound_executor.py` | Best-effort callback after ExecutionResult |
| `tests/test_sync_callback_contract.py` | NEW — callback fired on ok; skipped when unconfigured |

**Tests:** ~15 contract tests.

---

## iCal RFC Compliance + Lifecycle (149–151)

### Phase 149 — Full RFC 5545 VCALENDAR Compliance Audit
**Goal:** Audit the iCal payload emitted in Phase 140 against RFC 5545.  
Add missing required fields: `DTSTAMP` (now UTC), `SEQUENCE:0`.  
Ensure `CALSCALE:GREGORIAN` and `METHOD:PUBLISH` are present in VCALENDAR header.

**Files:**
| File | Change |
|------|--------|
| `src/adapters/outbound/ical_push_adapter.py` | Add DTSTAMP, SEQUENCE, CALSCALE, METHOD |
| `tests/test_rfc5545_compliance_contract.py` | NEW — validate all RFC 5545 REQUIRED fields |

**Tests:** ~18 contract tests. No DB changes.

---

### Phase 150 — iCal VTIMEZONE Support
**Goal:** Infer timezone from `booking_state.property_id` → `property_channel_map.timezone` (new column).  
Emit `VTIMEZONE` component when timezone is known. Default to UTC when absent.  
`DTSTART`/`DTEND` become `TZID=Region/City:YYYYMMDDTHHMMSS` format when timezone known.

**Schema change:** `property_channel_map` gets optional `timezone TEXT` column.

**Files:**
| File | Change |
|------|--------|
| `migrations/phase_150_property_channel_map_timezone.sql` | ADD COLUMN timezone TEXT |
| `src/adapters/outbound/ical_push_adapter.py` | VTIMEZONE + TZID-qualified DTSTART/DTEND |
| `tests/test_ical_timezone_contract.py` | NEW |

**Tests:** ~20 contract tests.

---

### Phase 151 — iCal Cancellation Push
**Goal:** When `BOOKING_CANCELED` is processed, push cancellation to iCal providers.  
Push an updated `.ics` with `STATUS:CANCELLED` VEVENT (or empty VCALENDAR).  
Triggered via a new `cancel_sync_trigger.py` service, wired into the existing outbound executor pipeline.

**Files:**
| File | Change |
|------|--------|
| `src/services/cancel_sync_trigger.py` | NEW — BOOKING_CANCELED → outbound executor |
| `src/adapters/outbound/ical_push_adapter.py` | `cancel(booking_id)` method |
| `src/services/service.py` | Wire cancel_sync_trigger after BOOKING_CANCELED APPLIED |
| `tests/test_ical_cancel_push_contract.py` | NEW |

**Tests:** ~22 contract tests.

---

## API-first Cancel/Amend Push (152–154)

### Phase 152 — API-first Cancellation Notification
**Goal:** For Airbnb, Booking.com, Expedia/VRBO — send cancellation notification via API on BOOKING_CANCELED.  
Each adapter gains `cancel(external_id, booking_id)` method.

**Endpoint:** `POST /internal/sync/cancel` — mirrors `/execute` but uses the cancel path.

**Files:**
| File | Change |
|------|--------|
| `src/adapters/outbound/airbnb_adapter.py` | `cancel()` method |
| `src/adapters/outbound/bookingcom_adapter.py` | `cancel()` method |
| `src/adapters/outbound/expedia_vrbo_adapter.py` | `cancel()` method |
| `src/api/outbound_executor_router.py` | `POST /internal/sync/cancel` |
| `tests/test_sync_cancel_contract.py` | NEW |

**Tests:** ~25 contract tests.

---

### Phase 153 — API-first Amendment Notification
**Goal:** For API-first OTAs — send amendment notification on BOOKING_AMENDED.  
Each adapter gains `amend(external_id, booking_id, check_in, check_out)` method.

**Endpoint:** `POST /internal/sync/amend`

**Files:**
| File | Change |
|------|--------|
| `src/adapters/outbound/airbnb_adapter.py` | `amend()` method |
| `src/adapters/outbound/bookingcom_adapter.py` | `amend()` method |
| `src/adapters/outbound/expedia_vrbo_adapter.py` | `amend()` method |
| `src/api/outbound_executor_router.py` | `POST /internal/sync/amend` |
| `tests/test_sync_amend_contract.py` | NEW |

**Tests:** ~25 contract tests.

---

### Phase 154 — Unified Sync Dispatcher
**Goal:** Consolidate `/execute` (create), `/cancel`, and `/amend` into a single  
`POST /internal/sync/dispatch` endpoint that routes based on `event_kind` in the request body.  
Backward-compatible: existing endpoints remain active.

**Files:**
| File | Change |
|------|--------|
| `src/api/outbound_executor_router.py` | NEW `/internal/sync/dispatch` endpoint |
| `tests/test_sync_dispatcher_contract.py` | NEW — routes correctly per event_kind |

**Tests:** ~20 contract tests.

---

## Property + Channel Management (155–157)

### Phase 155 — Property Channel Map Read/Write API
**Goal:** Full CRUD API for channel mappings. Foundation for a channel management UI.

**Endpoints:**
- `GET /properties/{property_id}/channels` — list all mappings
- `POST /properties/{property_id}/channels` — add a mapping
- `DELETE /properties/{property_id}/channels/{provider}` — remove

JWT + tenant-scoped. Reads/writes `property_channel_map`.

**Files:**
| File | Change |
|------|--------|
| `src/api/channel_map_router.py` | MODIFIED — add POST + DELETE |
| `tests/test_channel_map_crud_contract.py` | NEW |

**Tests:** ~28 contract tests.

---

### Phase 156 — Provider Capability Registry Read/Write API
**Goal:** Operator-facing API to view and update provider sync strategies at runtime.

**Endpoints:**
- `GET /admin/provider-registry` — list all providers
- `PATCH /admin/provider-registry/{provider}` — update `is_active`, `rate_limit`, `sync_strategy`

Admin-only (requires `admin` claim in JWT). Enables runtime config without code deploys.

**Files:**
| File | Change |
|------|--------|
| `src/api/capability_registry_router.py` | MODIFIED — add PATCH |
| `tests/test_capability_registry_admin_contract.py` | NEW |

**Tests:** ~22 contract tests.

---

### Phase 157 — Property Metadata (Timezone, Currency, Display Name)
**Goal:** New `properties` table as the canonical property metadata store.  
Pre-populated from `property_channel_map.property_id` set.  
Used by Phase 150 (timezone), owner statements, RevPAR calculations.

**Schema:**
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

**Files:**
| File | Change |
|------|--------|
| `migrations/phase_157_properties_table.sql` | NEW DDL |
| `src/api/properties_router.py` | NEW — GET /properties, POST /properties, GET /properties/{id} |
| `tests/test_properties_router_contract.py` | NEW |

**Tests:** ~25 contract tests.

---

## Booking State Enrichment (158–161)

### Phase 158 — Booking Amendment History Read Model
**Goal:** Clean, dedicated endpoint for amendment history per booking.  
Returns per-amendment: version, check_in, check_out, room_count, reason, occurred_at.  
Read-only from `event_log`. Complements Booking Audit Trail (Phase 132).

**Endpoint:** `GET /bookings/{booking_id}/amendments`  
*(Note: Phase 104 has `GET /amendments/{booking_id}` from financial_facts — this is from event_log.)*

**Files:**
| File | Change |
|------|--------|
| `src/api/bookings_router.py` | Add `/{booking_id}/amendments` sub-route |
| `tests/test_booking_amendment_history_contract.py` | NEW |

**Tests:** ~22 contract tests.

---

### Phase 159 — Guest Profile Normalisation
**Goal:** Extract canonical guest fields from OTA payloads into a PII-aware `guest_profile` table.  
Fields: `canonical_guest_name`, `canonical_guest_email`, `canonical_guest_phone`.  
PII stored in a separate table — never appears in `event_log` payload.  
10 active OTA adapters need extraction logic added.

**Schema:**
```sql
CREATE TABLE guest_profile (
  id            BIGSERIAL PRIMARY KEY,
  booking_id    TEXT NOT NULL,
  tenant_id     TEXT NOT NULL,
  guest_name    TEXT,
  guest_email   TEXT,
  guest_phone   TEXT,
  source        TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (booking_id, tenant_id)
);
```

**Files:**
| File | Change |
|------|--------|
| `migrations/phase_159_guest_profile.sql` | NEW DDL |
| `src/adapters/ota/guest_profile_extractor.py` | NEW — per-provider extraction |
| `src/services/service.py` | Best-effort guest profile write after BOOKING_CREATED |
| `src/api/guest_profile_router.py` | `GET /bookings/{id}/guest-profile` |
| `tests/test_guest_profile_contract.py` | NEW |

**Tests:** ~35 contract tests.

---

### Phase 160 — Booking Search and Filter Enhancements
**Goal:** Extend `GET /bookings` with additional filters and cursor-based pagination.  
New filters: `check_out_from`, `check_out_to`, `text` (search on external_ref).  
Pagination: cursor-based (`next_cursor` token). Max 500 per page.

**Files:**
| File | Change |
|------|--------|
| `src/api/bookings_router.py` | Add filters + cursor pagination |
| `tests/test_booking_search_enhanced_contract.py` | NEW |

**Tests:** ~30 contract tests.

---

### Phase 161 — Booking Flag API
**Goal:** Operators can annotate bookings with structured flags.  
Stored in a new `booking_flags` table. Surfaced in `GET /bookings/{id}`.

**Endpoint:** `PATCH /bookings/{booking_id}/flags` — body: `{vip, notes, follow_up}`  
`GET /bookings/{booking_id}` — `flags` field appended to response.

**Schema:**
```sql
CREATE TABLE booking_flags (
  id          BIGSERIAL PRIMARY KEY,
  booking_id  TEXT NOT NULL,
  tenant_id   TEXT NOT NULL,
  flags       JSONB NOT NULL DEFAULT '{}',
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (booking_id, tenant_id)
);
```

**Files:**
| File | Change |
|------|--------|
| `migrations/phase_161_booking_flags.sql` | NEW DDL |
| `src/api/bookings_router.py` | PATCH flags endpoint, GET enriched with flags |
| `tests/test_booking_flags_contract.py` | NEW |

**Tests:** ~22 contract tests.

---

## Financial Layer Hardening (162–165)

### Phase 162 — Multi-Currency Conversion Layer
**Goal:** Exchange-rate table + optional cross-currency conversion in financial summary endpoints.

**Schema:**
```sql
CREATE TABLE exchange_rates (
  id            BIGSERIAL PRIMARY KEY,
  from_currency CHAR(3) NOT NULL,
  to_currency   CHAR(3) NOT NULL,
  rate          NUMERIC NOT NULL,
  valid_at      TIMESTAMPTZ NOT NULL,
  UNIQUE (from_currency, to_currency, valid_at)
);
```
`GET /financial/summary` gains optional `?base_currency=USD` — converts all figures.  
Rates loaded manually first (no live feed yet). Foundation for cross-currency RevPAR.

**Files:**
| File | Change |
|------|--------|
| `migrations/phase_162_exchange_rates.sql` | NEW DDL |
| `src/api/financial_aggregation_router.py` | Add `base_currency` param + conversion logic |
| `tests/test_multicurrency_conversion_contract.py` | NEW |

**Tests:** ~30 contract tests.

---

### Phase 163 — Financial Correction Event
**Goal:** New event kind `BOOKING_FINANCIAL_CORRECTED` — operator can post a correction  
to `booking_financial_facts` without overwriting raw OTA data.  
All corrections audit-logged. Epistemic tier: `OPERATOR_MANUAL`.

**Files:**
| File | Change |
|------|--------|
| `src/api/financial_correction_router.py` | NEW — `POST /financial/corrections` |
| `src/adapters/ota/financial_writer.py` | Support OPERATOR_MANUAL confidence |
| `tests/test_financial_correction_contract.py` | NEW |

**Tests:** ~25 contract tests.

---

### Phase 164 — Automated Reconciliation Suggestions
**Goal:** System proposes auto-fixable corrections without auto-applying them.  
Suggestions only — operator applies manually via Phase 163 endpoint.

**Endpoint:** `GET /admin/reconciliation/suggestions`  
Example: *"commission_amount is 0 but rate is 15% — suggest setting to 450"*

**Files:**
| File | Change |
|------|--------|
| `src/api/reconciliation_router.py` | Add `/suggestions` endpoint |
| `tests/test_reconciliation_suggestions_contract.py` | NEW |

**Tests:** ~22 contract tests.

---

### Phase 165 — Owner Payout Summary CSV Export
**Goal:** CSV export of owner statement. No new DB schema — reads existing tables.

**Endpoint:** `GET /owner-statement/{property_id}?month=&format=csv`  
Columns: `booking_id, check_in, check_out, gross, commission, management_fee, owner_net, status`

**Files:**
| File | Change |
|------|--------|
| `src/api/owner_statement_router.py` | Add `format=csv` branch |
| `tests/test_owner_statement_csv_contract.py` | NEW |

**Tests:** ~18 contract tests.

---

## Operational Hardening + IPI (166–170)

### Phase 166 — Structured Log Adoption Pass
**Goal:** Sweep all Phase 130–165 modules and replace ad-hoc `logging.info(...)` calls  
with `get_structured_logger(...)` from Phase 80.  
Adds `trace_id` propagation from request through outbound adapters.  
No functional changes — pure observability improvement.

**Files:** All Phase 130–165 modules — sweep and replace logging calls.  
**Tests:** ~15 tests verifying JSON log output format.

---

### Phase 167 — Outbound Sync Stress Test Harness
**Goal:** Extend the Phase 90 E2E harness with outbound scenarios.

New test group H — outbound sync contract (~30 tests):
- Each of the 7 adapters returns correct `AdapterResult` shape
- Executor fail-isolation (one adapter failure → others proceed)
- Date injection for all 3 iCal providers
- Throttle / retry / idempotency key propagation

**Files:**
| File | Change |
|------|--------|
| `tests/test_e2e_integration_harness.py` | EXTENDED — Group H |

**Tests:** ~30 new tests added to harness.

---

### Phase 168 — Admin Audit Log
**Goal:** Every admin action is permanently recorded for compliance and governance.

**Schema:**
```sql
CREATE TABLE admin_audit_log (
  id                BIGSERIAL PRIMARY KEY,
  actor_tenant_id   TEXT NOT NULL,
  action            TEXT NOT NULL,  -- 'DLQ_REPLAY', 'SYNC_REPLAY', 'FLAG_UPDATE', etc.
  target            TEXT,
  payload_summary   JSONB,
  at                TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Endpoint:** `GET /admin/audit-log?limit=` — admin-only JWT claim required.

**Files:**
| File | Change |
|------|--------|
| `migrations/phase_168_admin_audit_log.sql` | NEW DDL |
| `src/api/admin_router.py` | Wire audit writes in all admin actions + GET `/admin/audit-log` |
| `tests/test_admin_audit_log_contract.py` | NEW |

**Tests:** ~28 contract tests.

---

### Phase 169 — Health Check Enrichment
**Goal:** Enhance `GET /health` (Phase 64) with outbound sync health probes.

New probes added to health response:
- `outbound_sync`: last successful sync per provider + 7d failure rate
- `provider_registry`: count of active providers  
- `outbound_log_lag`: seconds since last outbound_sync_log write

No write path changes.

**Files:**
| File | Change |
|------|--------|
| `src/api/health.py` | Add outbound probes |
| `tests/test_health_enriched_contract.py` | NEW |

**Tests:** ~20 contract tests.

---

### Phase 170 — IPI First Outbound Sync (Proactive Availability Broadcasting)
**Goal:** Flip from reactive-only to proactive availability broadcasting.  
Instead of reacting to OTA events only, iHouse Core proactively pushes availability windows  
(next 90/180/365 days) to all channels when a property is created or channel map changes.  
Foundation for becoming the system of record for availability, not just bookings.

**New service:** `outbound_availability_broadcaster.py`  
Triggered by: `property_channel_map` inserts/updates.  
Reads `booking_state` for already-blocked dates → constructs date-range exclusion list  
→ pushes full available window to all channels.

**Endpoint:** `POST /internal/sync/broadcast-availability`

**Files:**
| File | Change |
|------|--------|
| `src/services/outbound_availability_broadcaster.py` | NEW |
| `src/api/outbound_executor_router.py` | Add broadcast endpoint |
| `tests/test_availability_broadcaster_contract.py` | NEW |

**Tests:** ~30 contract tests.

---

## Guest Profile + Pre-Arrival Flow (171–175)

### Phase 171 — Guest Pre-Arrival Intake Flow
**Goal:** Lightweight intake per reservation before arrival.  
`POST /intake/{booking_id}` — captures: guest contact, arrival time, special notes, ID verification status, pre-arrival readiness.  
`GET /intake/{booking_id}` — retrieves.  
Zero canonical state mutation — side-table read model only.

**Schema:**
```sql
CREATE TABLE guest_intake (
  id              BIGSERIAL PRIMARY KEY,
  booking_id      TEXT NOT NULL UNIQUE,
  tenant_id       TEXT NOT NULL,
  arrival_time    TEXT,
  special_notes   TEXT,
  id_verified     BOOLEAN DEFAULT false,
  contact_phone   TEXT,
  pre_arrival_ok  BOOLEAN DEFAULT false,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Files:**
| File | Change |
|------|--------|
| `migrations/phase_171_guest_intake.sql` | NEW DDL |
| `src/api/guest_intake_router.py` | NEW — POST + GET |
| `tests/test_guest_intake_contract.py` | NEW |

**Tests:** ~25 contract tests.

---

### Phase 172 — Property Readiness View
**Goal:** Per-property readiness status based on tasks, intake, and booking state.  
`GET /properties/{property_id}/readiness?date=YYYY-MM-DD`  
Returns: `{property_id, date, is_ready, pending_tasks_count, overdue_tasks_count, intake_complete, conflicts}`.  
Pure read — no writes.

**Files:**
| File | Change |
|------|--------|
| `src/api/properties_router.py` | Add `/readiness` endpoint |
| `tests/test_property_readiness_contract.py` | NEW |

**Tests:** ~22 contract tests.

---

### Phase 173 — Arrivals + Departures Daily Summary
**Goal:** `GET /operations/today` — snapshot of today's operational picture.  
Returns: `{date, arrivals: [...], departures: [...], cleanings_due: [...], unacked_tasks: int}`.  
The 7AM dashboard data contract. All data already exists — no new DB.

**Files:**
| File | Change |
|------|--------|
| `src/api/operations_router.py` | NEW — GET /operations/today |
| `tests/test_operations_today_contract.py` | NEW |

**Tests:** ~25 contract tests.

---

### Phase 174 — Operations Calendar View
**Goal:** Week-level operational calendar.  
`GET /operations/calendar?from=YYYY-MM-DD&to=YYYY-MM-DD`  
Returns per date: `{arrivals_count, departures_count, occupied_properties, free_properties, tasks_due}`.  
Zero DB writes. Reads `booking_state` + `tasks`.

**Files:**
| File | Change |
|------|--------|
| `src/api/operations_router.py` | Add `/calendar` endpoint |
| `tests/test_operations_calendar_contract.py` | NEW |

**Tests:** ~22 contract tests.

---

### Phase 175 — OTA Replay Fixture Extension (Phases 141–165 coverage)
**Goal:** Extend the existing YAML fixture system (Phases 91, 95, 97, 99) to cover  
outbound sync scenarios. New fixture groups for iCal / cancel / amend push paths.  
Ensures the outbound layer has the same deterministic replay guarantee as the inbound layer.

**Files:**
| File | Change |
|------|--------|
| `tests/fixtures/outbound_replay/` | NEW directory + YAML fixtures |
| `tests/test_outbound_replay_fixture_contract.py` | NEW |

**Tests:** ~35 tests.

---

## Permission + Role System (176–180)

### Phase 176 — Permission Model Foundation
**Goal:** Introduce a declarative permission system as the foundation for multi-role product surfaces.

**Schema:**
```sql
CREATE TABLE tenant_permissions (
  id          BIGSERIAL PRIMARY KEY,
  tenant_id   TEXT NOT NULL,
  user_id     TEXT NOT NULL,  -- from JWT sub
  role        TEXT NOT NULL,  -- 'admin' | 'manager' | 'worker' | 'owner'
  permissions JSONB NOT NULL DEFAULT '{}',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, user_id)
);
```

**Files:**
| File | Change |
|------|--------|
| `migrations/phase_176_tenant_permissions.sql` | NEW DDL |
| `src/api/auth.py` | Enrich JWT scope with permission lookup |
| `src/api/permissions_router.py` | NEW — CRUD for admin-managed permissions |
| `tests/test_permissions_contract.py` | NEW |

**Tests:** ~30 contract tests.

---

### Phase 177 — Role-Scoped Worker View
**Goal:** Worker-role JWT sees only their assigned tasks and their properties.  
`GET /worker/tasks` already exists (Phase 123) — enforce role-scoping fully via permission model.  
Workers cannot see financial data, other workers' tasks, or admin surfaces.

**Files:**
| File | Change |
|------|--------|
| `src/api/worker_router.py` | Scope queries to `worker_role` from permission manifest |
| `tests/test_worker_role_scoping_contract.py` | NEW |

**Tests:** ~22 contract tests.

---

### Phase 178 — Owner Role Scoping
**Goal:** Owner-role JWT sees only their properties and financial data.  
Enforced at query level: `property_id IN (owner's properties)`.  
Owner cannot see other properties, task details, or system health.

**Files:**
| File | Change |
|------|--------|
| `src/api/owner_statement_router.py` | Role-scope enforcement |
| `src/api/financial_aggregation_router.py` | Property filter from permission |
| `tests/test_owner_role_scoping_contract.py` | NEW |

**Tests:** ~20 contract tests.

---

### Phase 179 — Manager Delegated Permission Model
**Goal:** Admin can delegate specific capabilities to managers.  
Examples: `can_approve_owner_statements`, `can_edit_financial_rules`, `can_manage_integrations`.  
Implemented as JSONB flags in `tenant_permissions.permissions`.

**Files:**
| File | Change |
|------|--------|
| `src/api/permissions_router.py` | Add grant/revoke endpoints |
| `src/api/auth.py` | Expose permission flags in request context |
| `tests/test_delegated_permissions_contract.py` | NEW |

**Tests:** ~25 contract tests.

---

### Phase 180 — Permission Audit Trail
**Goal:** Every permission grant/revoke/change is appended to `admin_audit_log` (Phase 168).  
`GET /admin/audit-log?action_type=PERMISSION_CHANGE` filter.  
Full compliance trail for role changes.

**Files:**
| File | Change |
|------|--------|
| `src/api/permissions_router.py` | Write audit_log on every permission change |
| `tests/test_permission_audit_contract.py` | NEW |

**Tests:** ~18 contract tests.

---

## UI Operations Dashboard (API Layer) (181–185)

### Phase 181 — Operations Dashboard API
**Goal:** Aggregate API for the Manager/Admin Operations Dashboard (7AM rule).  
Single endpoint that collects exception-first operational state.

**Endpoint:** `GET /operations/dashboard`  
Returns:
- `urgent_tasks`: unacked CRITICAL/HIGH tasks + SLA breach count
- `todays_arrivals` + `todays_departures`
- `overdue_cleanings`
- `properties_at_risk` (conflict or no intake)
- `integration_alerts` (from Phase 127)
- `financial_attention` (reconciliation pending count)
- `sync_health` (from Phase 146)

**Files:**
| File | Change |
|------|--------|
| `src/api/operations_router.py` | Add `/operations/dashboard` |
| `tests/test_operations_dashboard_contract.py` | NEW |

**Tests:** ~28 contract tests.

---

### Phase 182 — Booking Detail Enriched API
**Goal:** Single enriched endpoint for full booking detail (replaces multiple calls in a UI).  
`GET /bookings/{booking_id}/detail` — returns:  
booking_state + financial_facts + amendment_history + tasks + guest_profile + flags + audit_trail_count

**Files:**
| File | Change |
|------|--------|
| `src/api/bookings_router.py` | Add `/detail` composite endpoint |
| `tests/test_booking_detail_enriched_contract.py` | NEW |

**Tests:** ~30 contract tests.

---

### Phase 183 — Task Center API (Manager View)
**Goal:** Full task management API for the Manager Task Center screen.  
`GET /tasks/center?status=&property_id=&worker_role=&due_from=&due_to=&limit=&sort_by=`  
Returns enriched task list: task + property display name + worker acknowledgement time + SLA status.

**Files:**
| File | Change |
|------|--------|
| `src/tasks/task_router.py` | Add `/tasks/center` enriched endpoint |
| `tests/test_task_center_contract.py` | NEW |

**Tests:** ~25 contract tests.

---

### Phase 184 — Provider Health Overview API
**Goal:** Comprehensive provider health endpoint for the Manager/Admin UI.  
Extends Phase 127 with outbound health + DLQ + buffer + sync failure rate per provider.

**Endpoint:** `GET /integration-health/full`  
Returns per provider: inbound health + outbound health + DLQ count + sync failure rate.

**Files:**
| File | Change |
|------|--------|
| `src/api/integration_health_router.py` | Add `/full` enriched endpoint |
| `tests/test_integration_health_full_contract.py` | NEW |

**Tests:** ~22 contract tests.

---

### Phase 185 — Staff Status View API
**Goal:** Manager can see all worker acknowledgement states in real-time.  
`GET /workers/status?date=YYYY-MM-DD`  
Returns per worker_role: assigned tasks, acked, in_progress, completed, overdue_ack count.

**Files:**
| File | Change |
|------|--------|
| `src/api/worker_router.py` | Add `/workers/status` manager-facing endpoint |
| `tests/test_worker_status_contract.py` | NEW |

**Tests:** ~22 contract tests.

---

## Owner Portal + Worker Mobile API (186–190)

### Phase 186 — Owner Portal Dashboard API
**Goal:** Single dashboard endpoint for the Owner Portal.  
`GET /owner/dashboard?property_id=`  
Returns: `{monthly_revenue, payout_pending, payout_released, upcoming_stays_count, last_statement_month, financial_attention_items}`.  
Fully role-scoped (owner sees only their properties). Reads financial_facts only.

**Files:**
| File | Change |
|------|--------|
| `src/api/owner_router.py` | NEW — GET /owner/dashboard |
| `tests/test_owner_dashboard_contract.py` | NEW |

**Tests:** ~25 contract tests.

---

### Phase 187 — Owner Revenue Timeline API
**Goal:** Month-by-month revenue timeline for an owner's portfolio.  
`GET /owner/revenue-timeline?property_id=&months=12`  
Returns per month: `{month, gross, commission, management_fee, owner_net, booking_count}`.  
Reads `booking_financial_facts` only.

**Files:**
| File | Change |
|------|--------|
| `src/api/owner_router.py` | Add `/owner/revenue-timeline` |
| `tests/test_owner_revenue_timeline_contract.py` | NEW |

**Tests:** ~22 contract tests.

---

### Phase 188 — Worker Mobile Task API  
**Goal:** Lightweight, action-optimised worker task API designed for mobile consumption.  
`GET /mobile/tasks` — today's tasks only, sorted by due_time, role-scoped.  
Each task includes: `{id, kind, property_address, due_time, priority, status, ack_by}`.  
`POST /mobile/tasks/{id}/photo` — attach photo note (stored as URL reference).  
Minimal payload sizes — mobile-first contract.

**Files:**
| File | Change |
|------|--------|
| `src/api/mobile_worker_router.py` | NEW — GET /mobile/tasks, POST /mobile/tasks/{id}/photo |
| `tests/test_mobile_worker_contract.py` | NEW |

**Tests:** ~28 contract tests.

---

### Phase 189 — Push Notification Foundation (LINE / FCM)
**Goal:** Infrastructure for push notifications to workers and owners.  
`notification_channel_registry` table: maps `{tenant_id, user_id, channel_type, channel_id}`.  
Initial channels: LINE (Phase 124 already wired), FCM (Firebase) for mobile push.  
Foundation for Phase 190 notification dispatch.

**Schema:**
```sql
CREATE TABLE notification_channels (
  id           BIGSERIAL PRIMARY KEY,
  tenant_id    TEXT NOT NULL,
  user_id      TEXT NOT NULL,
  channel_type TEXT NOT NULL,  -- 'line' | 'fcm' | 'email'
  channel_id   TEXT NOT NULL,  -- LINE user_id or FCM token or email
  active       BOOLEAN NOT NULL DEFAULT true,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, user_id, channel_type)
);
```

**Files:**
| File | Change |
|------|--------|
| `migrations/phase_189_notification_channels.sql` | NEW DDL |
| `src/channels/notification_dispatcher.py` | NEW — route to LINE or FCM |
| `tests/test_notification_dispatcher_contract.py` | NEW |

**Tests:** ~25 contract tests.

---

### Phase 190 — Milestone: Operational Platform Checkpoint
**Goal:** System audit, documentation refresh, and architectural validation before  
entering the next major wave (UI build, multi-tenant hardening, production readiness).

Deliverables:
1. Update `docs/core/current-snapshot.md` — full Phase 190 state
2. Update `docs/core/roadmap.md` — reflect Phases 141–190 completion
3. Update `docs/core/live-system.md` — API surface inventory
4. Create `docs/core/system-audit-phase190.md` — gap analysis at this milestone
5. Write `releases/handoffs/handoff_to_new_chat Phase-190.md`

**Tests:** No new code tests. All existing tests must still pass.  
**Milestone state:** ~4800+ tests expected. All major product surfaces API-complete.

---

## Summary Table (Full 50 Phases)

| Phase | Title | Theme | Effort | Impact |
|-------|-------|-------|--------|--------|
| 141 | Rate-Limit Enforcement | Outbound Stability | S | Prevents OTA bans |
| 142 | Retry + Exponential Backoff | Outbound Stability | S | Resilience |
| 143 | Idempotency Keys | Outbound Stability | S | Safety |
| 144 | Sync Result Persistence | Outbound Stability | M | Auditability |
| 145 | Sync Log Inspector API | Outbound Visibility | S | Operational |
| 146 | Sync Health Dashboard | Outbound Visibility | S | Operational |
| 147 | Failed Sync Replay | Outbound Visibility | M | Operational |
| 148 | Sync Callback Webhook | Outbound Visibility | S | Optional |
| 149 | RFC 5545 Compliance | iCal | S | Correctness |
| 150 | VTIMEZONE Support | iCal | M | Correctness |
| 151 | iCal Cancel Push | iCal Lifecycle | M | Lifecycle |
| 152 | API Cancel Push | Outbound Lifecycle | M | Lifecycle |
| 153 | API Amend Push | Outbound Lifecycle | M | Lifecycle |
| 154 | Unified Sync Dispatcher | Architecture | M | Architecture |
| 155 | Channel Map CRUD API | Channel Mgmt | M | Self-serve |
| 156 | Provider Registry API | Channel Mgmt | S | Ops |
| 157 | Property Metadata Table | Channel Mgmt | M | Foundation |
| 158 | Amendment History API | Booking Enrichment | S | Product |
| 159 | Guest Profile Normalisation | Booking Enrichment | M | Product |
| 160 | Booking Search Enhanced | Booking Enrichment | M | Product |
| 161 | Booking Flag API | Booking Enrichment | S | Ops |
| 162 | Multi-Currency Conversion | Financial | M | Financial |
| 163 | Financial Correction Event | Financial | M | Financial |
| 164 | Reconciliation Suggestions | Financial | M | Ops |
| 165 | Owner Payout CSV Export | Financial | S | Product |
| 166 | Structured Log Adoption | Observability | M | Observability |
| 167 | Outbound Stress Harness | Testing | M | Testing |
| 168 | Admin Audit Log | Compliance | M | Compliance |
| 169 | Health Check Enrichment | Monitoring | S | Monitoring |
| 170 | IPI First Outbound Sync | **Strategic** | L | **Proactive sync** |
| 171 | Guest Pre-Arrival Intake | Guest Layer | M | Product |
| 172 | Property Readiness View | Operations | M | Product |
| 173 | Arrivals + Departures Summary | Operations | S | Product |
| 174 | Operations Calendar View | Operations | M | Product |
| 175 | Outbound Replay Fixtures | Testing | M | Testing |
| 176 | Permission Model Foundation | Roles | M | **Platform** |
| 177 | Worker Role Scoping | Roles | S | Security |
| 178 | Owner Role Scoping | Roles | S | Security |
| 179 | Manager Delegated Permissions | Roles | M | Product |
| 180 | Permission Audit Trail | Compliance | S | Compliance |
| 181 | Operations Dashboard API | UI Layer | M | **Product** |
| 182 | Booking Detail Enriched API | UI Layer | M | Product |
| 183 | Task Center API | UI Layer | M | Product |
| 184 | Integration Health Full API | UI Layer | S | Product |
| 185 | Staff Status View API | UI Layer | S | Product |
| 186 | Owner Portal Dashboard API | Owner Layer | M | **Product** |
| 187 | Owner Revenue Timeline API | Owner Layer | M | Product |
| 188 | Worker Mobile Task API | Worker Layer | M | **Product** |
| 189 | Push Notification Foundation | Communication | M | Platform |
| 190 | **Milestone: Platform Checkpoint** | Audit | M | **Strategic** |

**Effort key:** S = 1 session (~20–25 tests), M = 1–2 sessions (~25–35 tests), L = 2–3 sessions.

---

## Architectural Invariants That Govern All 50 Phases

> These rules must NEVER be violated in any of the above phases.

| Invariant | Source |
|-----------|--------|
| `apply_envelope` is the ONLY write authority for canonical booking state | Phase 35 |
| `event_log` is append-only — no row is ever updated | Phase 35 |
| `booking_id = {source}_{reservation_ref}` — deterministic, never changes | Phase 36 |
| `booking_state` must NEVER contain financial calculations | Phase 62 |
| `tenant_id` comes from verified JWT `sub` — never from payload body | Phase 61 |
| Outbound sync is always best-effort and non-blocking | Phase 135 |
| Outbound sync never writes to `booking_state` or `event_log` | Phase 135 |
| iCal is degraded mode only — never the primary sync strategy | Phase 135 |
| Every outbound attempt is auditable — no silent failures | Phase 144 |
| Source channel is never sent an outbound lock | Phase 135 |
| Reconciliation layer is READ-ONLY — corrections go through canonical pipeline | Phase 89 |
| Epistemic tier: FULL→A, ESTIMATED→B, PARTIAL→C. Worst tier wins in aggregations | Phase 116 |
| Owner surfaces are role-scoped — owners see only their properties | Phase 121 |
| CRITICAL ACK SLA = 5 minutes (locked, cannot be shortened) | Phase 111 |

---

*Document created: 2026-03-10 by Antigravity (post Phase-140 handoff boot)*  
*Sources: handoff Phase-140, phases-141-170.md, outbound-sync-layer.md, future-improvements.md, ui-architecture.md*
