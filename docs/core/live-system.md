# iHouse Core — Live System

This document describes the current technical architecture of the
running system.

**Last updated: Phase 208 — Platform Checkpoint III (2026-03-11)**

## Core Architecture

The system follows an event-sourced architecture.

Core principles:

- `event_log` is the canonical ledger of all system events
- `apply_envelope` is the only allowed write gate
- projections derive read models from the ledger
- the system must support deterministic rebuild from the event log

## Write Path

External OTA sources enter the system through a layered canonical path:

```
HTTP endpoint (POST /webhooks/{provider})
→ verify_webhook_signature
→ validate_ota_payload
→ OTA service entry (ingest_provider_event)
→ shared OTA pipeline
→ canonical envelope
→ IngestAPI.append_event
→ CoreExecutor.execute
→ Supabase RPC
→ apply_envelope
```

The OTA service entry is thin — it accepts provider-facing inputs and delegates shared processing.

The shared OTA pipeline performs:
- provider registry resolution
- adapter normalization
- structural validation
- semantic classification
- semantic validation
- canonical envelope construction
- canonical envelope validation

The canonical external OTA events are:
- `BOOKING_CREATED`
- `BOOKING_CANCELED`
- `BOOKING_AMENDED`

HTTP error codes:
- `403` → SignatureVerificationError or JWT auth failure
- `429` → per-tenant rate limit exceeded (Retry-After header set)
- `400` → PayloadValidationResult.valid = False
- `200` → envelope accepted, idempotency_key returned
- `503` → health check only, Supabase unreachable
- `500` → unexpected exception (never surfaces internals)

The canonical ingest API is the bridge from envelope construction into core execution.

CoreExecutor is the single execution boundary for canonical envelopes.

OTA code does not call apply_envelope directly.

The replay harness verifies the OTA path through the same canonical execution boundary without introducing a second write path.

The RPC validates:
- `event_version`
- `event_kind`
- emitted events

If valid:
1. envelope is recorded in `event_log`
2. projections update `booking_state`

## Read Path

Reads do not query the ledger directly. Reads use projections.

Primary projection: `public.booking_state`

## Safety Guarantees

- idempotent envelope processing
- deterministic state rebuild
- strict event validation
- single canonical write gate
- provider semantics isolated from core state mutation
- replay verification through the same OTA ingress contract
- no adapter-level state mutation
- no `booking_state` reads inside OTA adapters
- HMAC-SHA256 signature verification at HTTP boundary (dev-mode skip when secret not set)
- JWT Bearer auth — tenant_id from verified sub claim (Phase 61+)
- per-tenant rate limiting — sliding window, 429 + Retry-After (Phase 62+)
- `booking_state` is operational only — must never contain financial data (Phase 62+ invariant)
- RLS enabled on all public tables — tenant isolation enforced at DB layer (Phase 199)

## Current OTA Adapter Status

All **14 providers** implemented at full parity:

| Provider | CREATE | CANCEL | AMENDED | Phase |
|----------|:------:|:------:|:-------:|-------|
| Booking.com | ✅ | ✅ | ✅ | Phases 35-50 |
| Expedia | ✅ | ✅ | ✅ | Phases 35-50 |
| Airbnb | ✅ | ✅ | ✅ | Phases 35-50 |
| Agoda | ✅ | ✅ | ✅ | Phases 35-50 |
| Trip.com | ✅ | ✅ | ✅ | Phases 35-50 |
| Vrbo | ✅ | ✅ | ✅ | Phase 83 |
| Google Vacation Rentals | ✅ | ✅ | ✅ | Phase 85 |
| Traveloka | ✅ | ✅ | ✅ | Phase 88 |
| MakeMyTrip | ✅ | ✅ | ✅ | Phase 94 |
| Klook | ✅ | ✅ | ✅ | Phase 96 |
| Despegar | ✅ | ✅ | ✅ | Phase 98 |
| Hotelbeds | ✅ | ✅ | ✅ | Phase 125 |
| Hostelworld | ✅ | ✅ | ✅ | Phase 195 |
| Rakuten Travel | ✅ | ✅ | ✅ | Phase 198 |

## Current API Surface

### Ingestion

| Endpoint | Description | Phase |
|----------|-------------|-------|
| `POST /webhooks/{provider}` | OTA webhook ingestion (sig verify + ingest) | 58 |

### Health & Admin

| Endpoint | Description | Phase |
|----------|-------------|-------|
| `GET /health` | Supabase ping, DLQ count, ok/degraded/unhealthy | 64 |
| `GET /admin/summary` | Tenant summary — booking counts, DLQ, financial totals | 72 |
| `GET /admin/metrics` | DLQ + ordering buffer metrics | 82 |
| `GET /admin/dlq` | List dead-letter entries with filters | 131 |
| `GET /admin/dlq/{envelope_id}` | Single DLQ entry with full payload | 131 |
| `POST /admin/dlq/{envelope_id}/replay` | Replay a failed DLQ entry | 205 |
| `GET /admin/audit` | Admin audit log (action, actor, timestamp) | 171 |
| `GET /admin/health/providers` | Per-OTA last-event timestamp, event counts | 127 |

### Bookings

| Endpoint | Description | Phase |
|----------|-------------|-------|
| `GET /bookings/{booking_id}` | Single booking state | 71 |
| `GET /bookings` | Booking list (property_id, status, limit filters) | 106 |
| `GET /bookings/{booking_id}/timeline` | Chronological event audit trail | 132 |
| `GET /amendments/{booking_id}` | Amendment history | 104 |
| `GET /payment-status/{booking_id}` | Payment lifecycle state (7 states) | 103 |
| `GET /availability/{property_id}` | Availability projection (date range) | 126 |

### Financial

| Endpoint | Description | Phase |
|----------|-------------|-------|
| `GET /financial/{booking_id}` | Per-booking financial facts | 67 |
| `GET /financial/summary` | Portfolio-level summary (gross, net, commissions) | 116 |
| `GET /financial/by-provider` | Revenue breakdown per OTA | 116 |
| `GET /financial/by-property` | Revenue breakdown per property | 116 |
| `GET /financial/lifecycle-distribution` | Revenue by payment lifecycle state | 116 |
| `GET /financial/multi-currency-overview` | Per-currency aggregation (Phase 191) | 191 |
| `GET /financial/dashboard` | Status card, RevPAR, lifecycle-by-property | 118 |
| `GET /financial/reconciliation` | Stale/missing payment reconciliation inbox | 119 |
| `GET /financial/cashflow` | Weekly inflow buckets, 30/60/90d projection | 120 |
| `GET /financial/ota-comparison` | Per-OTA commission, net-to-gross, revenue share | 122 |
| `GET /owner-statement/{property_id}` | Owner statement (per-booking line items) | 101 |
| `GET /owner-statement/{property_id}/pdf` | PDF export | 188 |

### Tasks

| Endpoint | Description | Phase |
|----------|-------------|-------|
| `GET /tasks` | Task list (tenant-scoped, filters: status, kind, property) | 113 |
| `GET /tasks/{task_id}` | Single task detail | 113 |
| `PATCH /tasks/{task_id}/status` | Transition task status | 113 |
| `POST /tasks/pre-arrival/{booking_id}` | Trigger pre-arrival guest task generation | 206 |

### Worker

| Endpoint | Description | Phase |
|----------|-------------|-------|
| `GET /worker/tasks` | Worker's own assigned tasks | 123 |
| `PATCH /worker/tasks/{task_id}/acknowledge` | Acknowledge a task (starts ACK SLA clock) | 123 |
| `PATCH /worker/tasks/{task_id}/complete` | Mark task complete | 123 |
| `GET /worker/preferences` | Worker's channel preferences | 201 |
| `PUT /worker/preferences` | Upsert channel preference | 201 |
| `DELETE /worker/preferences/{channel_type}` | Remove a channel preference | 201 |
| `GET /worker/notifications` | Historical notification deliveries | 202 |

### Guests

| Endpoint | Description | Phase |
|----------|-------------|-------|
| `GET /guests` | Guest list (tenant-scoped) | 192 |
| `GET /guests/{guest_id}` | Single guest profile | 192 |
| `POST /guests` | Create guest profile | 192 |
| `PATCH /guests/{guest_id}` | Update guest profile | 192 |
| `GET /bookings/{booking_id}/guest` | Guest linked to a booking | 194 |
| `POST /bookings/{booking_id}/guest` | Link guest to booking | 194 |

### Properties

| Endpoint | Description | Phase |
|----------|-------------|-------|
| `GET /properties` | Property list (tenant-scoped) | 165 |
| `GET /properties/{property_id}` | Single property metadata | 165 |

### Conflicts

| Endpoint | Description | Phase |
|----------|-------------|-------|
| `GET /conflicts` | Active conflict list | 128 |
| `GET /conflicts/{conflict_id}` | Single conflict detail | 128 |
| `POST /conflicts/resolve` | Manual conflict resolution | 184 |
| `POST /conflicts/auto-check/{booking_id}` | Manual trigger of auto-conflict check | 207 |

### Escalation Channels (Webhooks)

| Endpoint | Description | Phase |
|----------|-------------|-------|
| `GET /line/webhook` | LINE webhook challenge | 124 |
| `POST /line/webhook` | LINE task acknowledgement | 124 |
| `GET /whatsapp/webhook` | WhatsApp webhook challenge (Meta) | 196 |
| `POST /whatsapp/webhook` | WhatsApp task acknowledgement | 196 |

## Future Evolution

Additional projections and domain modules may be added without breaking the canonical ledger model.

Future OTA expansion must preserve the explicit boundary between OTA entry, envelope construction, core ingest, and canonical execution.
