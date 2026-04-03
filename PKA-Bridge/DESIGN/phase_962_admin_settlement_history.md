# Phase 962 — Admin Settlement History Surface

## Overview

Pure read-only aggregation surface for admin. No new tables.
All data is assembled from existing tables written by Phases 687–961.

The purpose is to provide a **durable long-term history view** so admin can go back
months later and reconstruct exactly what happened for any booking or any property
— who collected what, what was consumed, what was deducted, what was refunded.

---

## Why This Is a Separate Phase

Phases 957–961 already have single-booking admin read endpoints (`GET /admin/bookings/{id}/settlement`).
Phase 962 adds the **cross-property, cross-time, portfolio-level** history surface:

- **Cross-property list** — all settlements across the tenant, filterable by date, property, status.
- **Full durable record** — single endpoint returning the complete settlement story
  for one booking, joining all 8 source tables into one structured doc.
- **Portfolio summary** — aggregate numbers for a time window (totals per status).

The distinction matters because the Phase 961 endpoint shows the active settlement only.
Phase 962 shows **all settlements including voided**, with the full audit trail,
and supports the "months later review" use case.

---

## Phase Assignment

| Phase | Scope |
|---|---|
| **962a** | `GET /admin/settlements` — cross-property history list |
| **962b** | `GET /admin/settlements/{settlement_id}/full-record` — one complete durable record |
| **962c** | `GET /admin/bookings/{booking_id}/settlement-record` — same record keyed by booking_id |
| **962d** | `GET /admin/settlements/summary` — portfolio aggregate for a time window |

All in one file: `settlement_history_router.py`

---

## 1. Full Record Structure

The "full record" for one booking uses a fixed join order across all source tables:

```
booking_settlement_records   ← settlement snapshot (amounts, status, actors)
    ↓
booking_state                ← guest name, check-in/out dates, property_id
    ↓
checkin_deposit_records      ← operational deposit receipt from check-in worker
    ↓
cash_deposits                ← financial deposit record (Phase 687), null if not yet created
    ↓
deposit_deductions           ← damage deductions linked to cash_deposit
    ↓
electricity_meter_readings   ← opening + closing readings (separate rows)
    ↓
property_charge_rules        ← charge rule at time of booking (rate snapshot reference)
    ↓
admin_audit_log              ← full audit trail filtered by booking_id + settlement entity types
```

Response shape:
```json
{
  "settlement": { ... all booking_settlement_records fields ... },
  "booking": {
    "booking_id": "...",
    "guest_name": "...",
    "check_in": "2026-03-15",
    "check_out": "2026-03-20",
    "property_id": "..."
  },
  "deposit": {
    "checkin_record": { ... checkin_deposit_records row ... },
    "cash_deposit":   { ... cash_deposits row or null ... },
    "deductions":     [ ... deposit_deductions rows ... ],
    "total_deductions": 1200.00
  },
  "electricity": {
    "opening": { id, meter_value, meter_photo_url, recorded_by, recorded_at },
    "closing":  { id, meter_value, meter_photo_url, recorded_by, recorded_at },
    "kwh_used": 45.32,
    "rate_kwh": 4.50,
    "charged":  203.94
  },
  "charge_rule_at_stay": { ... property_charge_rules row ... },
  "audit_trail": [
    { action, actor_id, performed_at, details },
    ...
  ]
}
```

---

## 2. API Endpoints

```
GET /admin/settlements
    Cross-property settlement history list.
    Returns booking_settlement_records rows enriched with booking context.
    Filters:
      ?property_id=          filter by property
      ?status=               draft|calculated|finalized|voided
      ?date_from=            ISO date — filter by created_at ≥
      ?date_to=              ISO date — filter by created_at ≤
      ?limit=                default 50, max 200
      ?offset=               pagination
    Auth: admin, manager.

GET /admin/settlements/summary
    Portfolio aggregate for a time window.
    Returns counts and totals grouped by status for the filtered period.
    Fields: total_count, finalized_count, total_deposit_held,
            total_refunded, total_retained, total_electricity_charged,
            total_damage_deductions
    Same filters as list endpoint (property_id, date_from, date_to).
    Auth: admin, manager.
    NOTE: /summary must be registered BEFORE /admin/settlements/{settlement_id}
    to avoid FastAPI routing the literal string "summary" as a settlement_id.

GET /admin/settlements/{settlement_id}/full-record
    Complete durable record for one settlement (by settlement UUID).
    Assembles full record from all 8 source tables.
    Auth: admin, manager.

GET /admin/bookings/{booking_id}/settlement-record
    Same full record, keyed by booking_id instead of settlement_id.
    Returns the most recent non-voided settlement, or the voided one if
    no other exists (with status flag).
    Auth: admin, manager.
```

---

## 3. Role Access

| Endpoint | admin | manager | ops | owner | worker |
|---|---|---|---|---|---|
| All Phase 962 endpoints | ✅ | ✅ | ❌ | ❌ | ❌ |

Owners have no access to the full settlement history surface.
Owner visibility (deposit policy only) remains at Phase 954 endpoints.

---

## 4. Invariants

- All Phase 962 endpoints are read-only. No writes, no side effects.
- Tenant isolation is always enforced: every query uses `tenant_id` from JWT.
- admin_audit_log is included in full records filtered by settlement entity types
  (`booking_settlement_record`, `electricity_meter_reading`, `checkin_deposit_record`).
- The summary endpoint returns 0s (not 404) when no records match the filters.
- Long-term durability is guaranteed by the underlying tables — no data in this
  workstream is ephemeral or time-limited.
