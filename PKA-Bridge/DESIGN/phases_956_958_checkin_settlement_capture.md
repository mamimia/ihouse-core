# Phases 956–958 — Check-in Settlement Capture (Deposit + Electricity Meter)

## Overview

This workstream adds the **check-in side** of the operational settlement record.

When a check-in worker completes a check-in for a booking at a property that has
charge rules configured (Phase 952), they need to:

1. **Capture the deposit received** — durable record of how much was taken, by whom, when.
2. **Capture the opening electricity meter reading** — meter value + photo + timestamp + actor.

Both are booking-linked operational facts, not financial reporting records.

---

## Phase Assignment

| Phase | Scope |
|---|---|
| **956** | DB: `electricity_meter_readings` + `checkin_deposit_records` tables |
| **957** | `checkin_settlement_router.py` — worker endpoints for check-in capture |
| **958** | Admin read endpoints: view per-booking settlement capture state |

---

## 1. Design Decisions

### Why two tables instead of extending `cash_deposits`?

`cash_deposits` (Phase 687) requires `require_capability("financial")`. That guard
is correct — it prevents arbitrary writes to the financial settlement record.
Check-in workers don't have the financial capability and shouldn't need it.

The operational pattern is:
- Worker captures deposit at check-in → `checkin_deposit_records`
- Admin/manager confirms and formalises it → `cash_deposits` (via Phase 687 endpoint)
- At checkout, deductions/return/forfeit flow through Phase 688-689

`cash_deposit_id` on `checkin_deposit_records` is populated when the financial
record is created, linking the two. The admin can see both sides.

### Why is `electricity_meter_readings` append-only?

Meter readings should never be modified in place — corrections must be
traceable. A correction creates a new row with `supercedes_id` pointing to the
row it corrects. The active reading for a booking is the most recent non-superceded row.

### Why is `reading_type = opening | closing`?

The same table holds both check-in (opening) and checkout (closing) readings.
The closing read is written by a future Phase 957 checkout endpoint.
The delta (`closing.meter_value - opening.meter_value`) × `electricity_rate_kwh`
gives the billable electricity charge at settlement time.

---

## 2. Tables

### `electricity_meter_readings`

```
id              UUID PK
tenant_id       TEXT NOT NULL
booking_id      TEXT NOT NULL
property_id     TEXT NOT NULL
reading_type    TEXT  opening | closing
meter_value     NUMERIC(12,2)       -- kWh value on the meter face
meter_unit      TEXT  default kWh
meter_photo_url TEXT                -- uploaded photo URL
recorded_by     TEXT                -- real user_id from JWT
recorded_at     TIMESTAMPTZ
supercedes_id   UUID                -- correction chain
notes           TEXT
created_at      TIMESTAMPTZ
```

### `checkin_deposit_records`

```
id              UUID PK
tenant_id       TEXT NOT NULL
booking_id      TEXT NOT NULL
property_id     TEXT NOT NULL
amount          NUMERIC(10,2)
currency        TEXT  default THB
collected_by    TEXT                -- real user_id from JWT (check-in worker)
collected_at    TIMESTAMPTZ
cash_deposit_id TEXT                -- populated when Phase 687 cash_deposits row created
notes           TEXT
created_at      TIMESTAMPTZ
```

---

## 3. API Endpoints

### Phase 957 — Worker: Check-in Settlement Capture

```
POST /worker/bookings/{booking_id}/checkin-settlement
     Unified check-in capture. Writes deposit record and/or meter opening reading
     depending on what the property has configured and what the worker submits.
     Auth: checkin, ops, worker, admin.
     Body: {
       -- Deposit section (required if deposit_enabled=true for this property)
       deposit_collected   bool              -- was deposit physically taken?
       deposit_amount      number            -- actual amount collected
       deposit_currency    string            -- default: from charge rule
       deposit_notes       string | null

       -- Electricity section (required if electricity_enabled=true)
       meter_reading       number            -- value shown on the meter face (kWh)
       meter_photo_url     string | null     -- URL of uploaded photo
       meter_notes         string | null
     }
     Response: {
       booking_id
       deposit_record_id   UUID | null      (if deposit_collected=true)
       meter_reading_id    UUID | null      (if meter_reading submitted)
       warnings            string[]         (e.g. "property has deposit but none submitted")
     }

GET  /worker/bookings/{booking_id}/checkin-settlement
     Read current check-in settlement capture state for this booking.
     Returns the most recent deposit record and current opening meter reading.
     Auth: checkin, ops, worker, admin, manager.

POST /worker/bookings/{booking_id}/meter-reading/correction
     Submit a corrected meter reading (creates new row with supercedes_id).
     Auth: checkin, ops, admin.
     Body: { meter_reading, meter_photo_url, supercedes_id, notes }
```

### Phase 958 — Admin: Settlement Capture Review

```
GET  /admin/bookings/{booking_id}/settlement-capture
     Full operational view: charge rule at time of check-in, deposit record,
     opening meter reading. Admin/manager only.
     Used to verify worker captured everything before checkout settlement proceeds.

GET  /admin/properties/{property_id}/settlement-captures
     List all bookings for this property where settlement capture has open items.
     Filters: ?deposit_missing=true  ?meter_missing=true  ?date_from=  ?date_to=
```

---

## 4. Role Access

| Endpoint | admin | manager | ops | worker/checkin | owner |
|---|---|---|---|---|---|
| POST checkin-settlement | ✅ | ❌ | ✅ | ✅ | ❌ |
| GET checkin-settlement (worker) | ✅ | ✅ | ✅ | ✅ | ❌ |
| POST meter correction | ✅ | ❌ | ✅ | ✅ checkin | ❌ |
| GET settlement-capture (admin) | ✅ | ✅ | ❌ | ❌ | ❌ |
| GET settlement-captures by property | ✅ | ✅ | ❌ | ❌ | ❌ |

---

## 5. Invariants

- This router NEVER writes to `event_log`, `booking_state`, `booking_financial_facts`, or `cash_deposits`.
- `cash_deposits` is written exclusively by `deposit_settlement_router` (Phase 687) under the financial capability.
- `checkin_deposit_records.cash_deposit_id` is populated when Phase 687 runs — the link is written by deposit_settlement_router, not by this router.
- Electricity meter readings are append-only. No UPDATE ever runs on `electricity_meter_readings`.
- `recorded_by` and `collected_by` are always the real `user_id` from JWT — never hardcoded.
- A booking may have zero check-in settlement capture records (property has no charge rules configured).

---

## 6. Future Integration (Not in Scope)

- **Phase 957 checkout closing meter** — write `closing` reading at checkout, compute delta.
- **Electricity billing at settlement** — `(closing - opening) × electricity_rate_kwh` added as a deduction category to `deposit_deductions`.
- **Admin settlement dashboard** — unified view of opening meter + closing meter + deposit lifecycle per booking.
