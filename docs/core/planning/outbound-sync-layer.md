# iHouse Core — Outbound Channel Sync Layer

> **Status:** Planning — approved for implementation starting Phase 135.
> **Recorded:** Phase 131 (2026-03-09)
> **Backlog entry:** `docs/core/improvements/future-improvements.md` → "API First Outbound Channel Sync"

---

## The Gap

iHouse Core today is **inbound-complete but outbound-blind**.

It knows the truth about every booking — source, dates, property, financial state.
It cannot yet propagate that truth outward to other connected channels.

Without outbound sync, a booking received from Trip.com does not automatically close
the same dates on Airbnb, Booking.com, Expedia, and Vrbo.
The system knows. The channels do not.
That is an overbooking risk window. It is unacceptable for a production property platform.

---

## What Already Exists That Supports This

| Component | Role in Outbound Sync |
|-----------|----------------------|
| `apply_envelope` | Single write gate → natural trigger point after APPLIED |
| `booking_state` | Source of truth for occupied dates — what to propagate |
| `service.py` best-effort hooks | Pattern already used by `task_writer` and `financial_writer` |
| `availability_router.py` | Per-date occupancy already computed — logic reusable |
| `conflicts_router.py` | Overlap detection proven — same logic applies to lock decisions |
| `integration_health_router.py` | Per-provider health surface — extend for outbound sync health |
| OTA adapter registry | Provider identity already exists — extends to write capability |
| DLQ + ordering buffer | Retry infrastructure pattern already established |
| `reconciliation_router.py` | Exception inbox — failed outbound locks belong here |

---

## Architectural Rules (Locked — Must Never Be Violated)

1. **Outbound sync is always best-effort and non-blocking.**
   It must never delay or block the inbound `apply_envelope` response.
   The booking is canonical regardless of outbound sync outcome.

2. **Outbound sync never writes to `booking_state` or `event_log`.**
   It reads from them. It writes only to its own tables.

3. **`apply_envelope` remains the only write authority for canonical booking state.**
   Outbound sync does not bypass it, ever.

4. **iCal is degraded mode — always surfaced clearly.**
   If a channel is iCal-only, operators must see it as lower-confidence sync mode.
   iCal is fallback / bridge only. Never the primary strategy.

5. **Every outbound attempt is auditable.**
   No silent failures. Every attempt, result, retry, and failure is recorded.

6. **The source channel is never sent an outbound lock.**
   The booking came from that channel — it already knows. Lock the others.

---

## New Tables Required

### `property_channel_map`

Maps internal `property_id` to external listing IDs per provider.

```sql
CREATE TABLE property_channel_map (
  id              BIGSERIAL PRIMARY KEY,
  tenant_id       TEXT        NOT NULL,
  property_id     TEXT        NOT NULL,
  provider        TEXT        NOT NULL,  -- 'bookingcom', 'airbnb', etc.
  external_id     TEXT        NOT NULL,  -- provider's listing / property ID
  inventory_type  TEXT        NOT NULL DEFAULT 'single_unit',
                                         -- 'single_unit' | 'multi_unit' | 'shared'
  sync_mode       TEXT        NOT NULL DEFAULT 'api_first',
                                         -- 'api_first' | 'ical_fallback' | 'disabled'
  enabled         BOOLEAN     NOT NULL DEFAULT true,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, property_id, provider)
);
```

RLS: tenant_id isolation required. Service role all. Authenticated read own rows.

### `channel_sync_log`

Tracks every outbound sync attempt.

```sql
CREATE TABLE channel_sync_log (
  id              BIGSERIAL PRIMARY KEY,
  tenant_id       TEXT        NOT NULL,
  booking_id      TEXT        NOT NULL,
  provider        TEXT        NOT NULL,
  external_id     TEXT        NOT NULL,
  event_type      TEXT        NOT NULL,  -- 'AVAILABILITY_BLOCK' | 'AVAILABILITY_UNBLOCK'
  check_in        DATE        NOT NULL,
  check_out       DATE        NOT NULL,
  status          TEXT        NOT NULL DEFAULT 'pending',
                                         -- 'pending' | 'sent' | 'confirmed' | 'failed' | 'retrying' | 'exhausted'
  attempt_count   INT         NOT NULL DEFAULT 0,
  last_attempt_at TIMESTAMPTZ,
  next_retry_at   TIMESTAMPTZ,
  failure_reason  TEXT,
  confirmed_at    TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Indexes: `(tenant_id, booking_id)`, `(status, next_retry_at)`, `(tenant_id, provider, status)`.

### `provider_capability_registry`

Declarative write capabilities per provider. Populated at migration time.

```sql
CREATE TABLE provider_capability_registry (
  provider        TEXT  PRIMARY KEY,
  write_mode      TEXT  NOT NULL,  -- 'api_first' | 'ical_fallback' | 'disabled'
  api_family      TEXT,            -- 'connectivity_api', 'supply_api', 'ical', null
  partner_gated   BOOLEAN NOT NULL DEFAULT false,
  notes           TEXT,
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Seed data at migration time:

| provider | write_mode | partner_gated |
|----------|-----------|--------------|
| bookingcom | api_first | true |
| expedia | api_first | true |
| vrbo | api_first | true |
| agoda | api_first | true |
| airbnb | api_first | true |
| gvr | api_first | true |
| hotelbeds | api_first | true |
| makemytrip | api_first | true |
| tripcom | ical_fallback | false |
| traveloka | ical_fallback | false |
| despegar | ical_fallback | false |
| klook | disabled | false |

> Note: Trip.com, Traveloka, Despegar are initially classified as `ical_fallback`.
> They should be reclassified to `api_first` if a verified write path is found.

---

## Pipeline Integration Point

```
POST /webhooks/{provider}
  → signature verify → JWT → rate limit → validate
  → ingest_provider_event
    → pipeline → apply_envelope → APPLIED
    → financial_writer (best-effort, existing)
    → task_writer (best-effort, existing)
    → outbound_sync_trigger (best-effort, NEW)   ← ADD HERE
```

`outbound_sync_trigger.py` — called after BOOKING_CREATED APPLIED:

1. Read `property_channel_map` for the booking's `property_id` and `tenant_id`
2. Exclude the source channel
3. For each mapped channel: read write_mode from `provider_capability_registry`
4. Create `channel_sync_log` row with `status = 'pending'`
5. If write_mode = `api_first` and client available: attempt sync immediately
6. If write_mode = `ical_fallback`: mark as `sent` (iCal is pulled by channel, not pushed)
7. Return — never block

Also triggered after BOOKING_CANCELED APPLIED for `AVAILABILITY_UNBLOCK` events.

---

## Provider Capability Tiers

### Tier A — API-First, Full Write Path

All require partner program enrollment. Design now; wire when enrolled.

| Provider | API | Source |
|----------|-----|--------|
| **Booking.com** | Connectivity API — Rates & Availability | developers.booking.com/connectivity |
| **Expedia Group** | Availability and Rates API | developers.expediagroup.com/supply |
| **Vrbo** | Integration Central | integration-central.vrbo.com |
| **Agoda** | Direct Supply API / YCS | developer.agoda.com/supply |
| **Airbnb** | Software-Connected Listings | airbnb.com/help/article/2348 |

> Airbnb note: Airbnb's model is software-connected listing sync, not a raw REST write.
> The `airbnb_writer.py` must be designed around channel-manager style auth and sync primitives,
> not the same pattern as Booking.com REST API calls.

### Tier B — Partner/Feed-Gated

| Provider | Write Path | Notes |
|----------|-----------|-------|
| **Google Vacation Rentals** | ARI/feed push | Distribution surface, not classic OTA — semantics differ |
| **Hotelbeds** | Hotel Booking API | B2B bedbank — inventory semantics differ from B2C |
| **MakeMyTrip** | Channel-manager network (80+ CMs) | Bridge through CM partner required |

### Tier C — Verify Write Path First

| Provider | Current Classification | Action |
|----------|----------------------|--------|
| **Trip.com** | ical_fallback | Research and verify real write API / partner model |
| **Traveloka** | ical_fallback | Research and verify |
| **Despegar** | ical_fallback | Research and verify |

### Tier D — Not Applicable for Villa Inventory Locking

| Provider | Reason |
|----------|--------|
| **Klook** | Activities marketplace — not villa availability inventory model |

### Fallback — iCal

For any channel classified as `ical_fallback`:
- `GET /ical/{property_id}` serves a blocked iCal feed
- Channel polls the feed on its own schedule
- This is lower-confidence sync — not real-time
- **Must be surfaced in the product as degraded sync mode**

---

## New Source Files

```
src/
  outbound/
    __init__.py
    outbound_sync_trigger.py    ← Main trigger (Phase 137)
    sync_planner.py             ← Builds SyncPlan from mapping + capability registry
    sync_retry_engine.py        ← Processes failed rows with backoff (Phase 145)
    ical_writer.py              ← iCal fallback feed generator (Phase 144)
    bookingcom_writer.py        ← Tier A (Phase 139)
    expedia_writer.py           ← Tier A (Phase 140)
    vrbo_writer.py              ← Tier A (Phase 141)
    agoda_writer.py             ← Tier A (Phase 142)
    airbnb_writer.py            ← Tier A (Phase 143)
    gvr_writer.py               ← Tier B (Phase 151)
    makemytrip_writer.py        ← Tier B (Phase 152)
    tripcom_writer.py           ← Tier C — only if write path verified (Phase 153)
    traveloka_writer.py         ← Tier C — only if verified (Phase 154)
    despegar_writer.py          ← Tier C — only if verified (Phase 154)

src/api/
  channel_map_router.py         ← CRUD for property_channel_map (Phase 135)
  sync_log_router.py            ← Read-only sync log API (Phase 137)
  sync_health_router.py         ← Sync health dashboard (Phase 146)
```

---

## New API Endpoints

| Endpoint | Phase | Description |
|----------|-------|-------------|
| `POST /admin/properties/{id}/channels` | 135 | Register channel mapping |
| `GET /admin/properties/{id}/channels` | 135 | List channel mappings |
| `DELETE /admin/properties/{id}/channels/{provider}` | 135 | Remove mapping |
| `GET /admin/provider-capabilities` | 136 | List provider write capabilities |
| `GET /admin/sync-log?booking_id=&status=` | 137 | Read-only sync log |
| `GET /ical/{property_id}` | 144 | iCal feed for fallback channels |
| `GET /admin/sync-health` | 146 | Per-property, per-channel sync health |

---

## Product Truth — What Operators See

After this is fully built, the product can show:

```
Booking received from Airbnb — Villa A — March 10–15
✅ Internal availability closed
✅ Booking.com closed — confirmed (10:03:22)
✅ Expedia closed — confirmed (10:03:24)
⚠️  Vrbo — pending (retry scheduled 10:08:22)
⚠️  Trip.com — iCal fallback (lower confidence sync mode)
❌  Agoda — failed after 3 attempts — manager alerted
```

---

## Phase Rollout Plan

| Phase | Title | Key Deliverable |
|-------|-------|----------------|
| **135** | Property-Channel Mapping Foundation | `property_channel_map` DDL + CRUD API |
| **136** | Provider Capability Registry | `provider_capability_registry` DDL + seed data + GET endpoint |
| **137** | Channel Sync Log + Trigger Hook | `channel_sync_log` DDL + `outbound_sync_trigger.py` wired into `service.py` |
| **138** | Availability Unblock on Cancellation | Extend trigger for BOOKING_CANCELED → AVAILABILITY_UNBLOCK |
| **139** | Booking.com Availability Writer | `bookingcom_writer.py` — Tier A first |
| **140** | Expedia Availability Writer | `expedia_writer.py` |
| **141** | Vrbo Availability Writer | `vrbo_writer.py` |
| **142** | Agoda Availability Writer | `agoda_writer.py` |
| **143** | Airbnb Availability Writer | `airbnb_writer.py` — software-connected model |
| **144** | iCal Fallback Writer | `ical_writer.py` + `GET /ical/{property_id}` |
| **145** | Outbound Sync Retry Engine | `sync_retry_engine.py` — exponential backoff, max retries, escalation |
| **146** | Sync Health Dashboard | `GET /admin/sync-health` |
| **147** | Reconciliation Integration | Extend reconciliation inbox with `OUTBOUND_SYNC_FAILED` flag |
| **148** | Conflict Center: Unsynced Risk Flag | `OUTBOUND_SYNC_AT_RISK` in conflicts endpoint |
| **149** | Booking Timeline: Sync Events | Extend `/bookings/{id}/history` with sync events |
| **150** | Property Summary: Sync Coverage | Extend `/properties/summary` with channel sync coverage stats |
| **151** | GVR Outbound | `gvr_writer.py` — ARI feed push |
| **152** | MakeMyTrip Outbound | `makemytrip_writer.py` — via CM bridge |
| **153** | Trip.com Outbound Verification | Verify write path; implement or formally classify as ical_fallback |
| **154** | Traveloka + Despegar Verification | Same pattern as 153 |
| **155** | Provider Capability Matrix UI | Full operator view of channel portfolio and sync status |

---

*Spec approved and recorded: Phase 131 closure / Phase 132 planning.*
*Full architecture plan: `brain/outbound_sync_plan.md` (Antigravity artifact)*
