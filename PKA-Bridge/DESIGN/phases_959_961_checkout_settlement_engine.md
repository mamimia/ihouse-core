# Phases 959–961 — Checkout Settlement Engine

## Overview

This workstream adds the **checkout side** of the settlement flow:
closing meter capture, electricity usage calculation, settlement assembly, and finalization.

It is a **settlement subsystem**, not booking revenue accounting.
The output is a durable `booking_settlement_records` row — an immutable snapshot of
what was held, what was deducted, what is refunded, and what is retained.

---

## Phase Assignment

| Phase | Scope |
|---|---|
| **959** | Closing meter reading endpoint (reuses `electricity_meter_readings`, `reading_type='closing'`) |
| **960** | `booking_settlement_records` DB table |
| **961** | Settlement engine router: calculate preview, add deductions, finalize, admin read |

---

## 1. Status Machine — `booking_settlement_records.status`

```
                 ┌───────┐
  worker creates │       │
  ─────────────► │ draft │
                 │       │
                 └───┬───┘
                     │
              calculate (engine runs)
                     │
                     ▼
              ┌────────────┐
              │ calculated │  ← read-only preview, can add damage deductions here
              └─────┬──────┘
                    │
           admin/ops finalizes
                    │
                    ▼
             ┌──────────┐
             │ finalized │  ← terminal, immutable
             └──────────┘

At any time before finalized → voided (terminal, rare, requires reason)
```

**Invariants:**
- At most one non-voided settlement per booking (enforced by DB unique partial index).
- `draft → calculated` is triggered by the calculate endpoint (idempotent, can re-run).
- `calculated → finalized` is irreversible. All amounts are locked at this point.
- Only `admin` or `ops` can finalize.
- Voiding requires admin only + void_reason.

---

## 2. Calculation Engine — How Numbers Are Produced

```
deposit_held           = amount from checkin_deposit_records (or cash_deposits)

electricity_kwh_used   = closing_meter_value - opening_meter_value
electricity_charged    = electricity_kwh_used × electricity_rate_kwh
                         (rate snapshotted from property_charge_rules at calculation time)

damage_deductions_total = sum of deposit_deductions linked to this booking's deposit

total_deductions       = electricity_charged + damage_deductions_total

refund_amount          = MAX(0, deposit_held - total_deductions)
retained_amount        = deposit_held - refund_amount
```

**Rate snapshotting:** The `electricity_rate_kwh` used for calculation is read from
`property_charge_rules` at the moment calculate is called and stored on the settlement record.
Subsequent changes to the property's rate do not affect the settlement.

---

## 3. API Endpoints

### Phase 959 — Closing Meter Reading

```
POST /worker/bookings/{booking_id}/closing-meter
     Write the closing electricity meter reading.
     Reuses electricity_meter_readings table (reading_type='closing').
     Body: { meter_reading, meter_photo_url?, notes? }
     Auth: checkin, checkout, ops, admin.
     Read guard: checks whether an opening reading exists — warns if missing.
```

### Phase 961 — Settlement Engine

```
POST /worker/bookings/{booking_id}/settlement/start
     Create a draft settlement record for this booking.
     Only allowed if no non-voided settlement exists yet.
     Auth: checkin, checkout, ops, admin.
     Response: { settlement_id, status: 'draft' }

POST /worker/bookings/{booking_id}/settlement/calculate
     Run the calculation engine on the draft or calculated settlement.
     Reads: opening meter, closing meter, charge rule rate, deposit held,
            existing deposit_deductions rows (damage).
     Writes: all computed amounts to booking_settlement_records.
     Transitions: draft → calculated (idempotent — re-runnable from calculated too).
     Response: full settlement preview with all computed fields.
     Auth: checkin, checkout, ops, admin.

POST /worker/bookings/{booking_id}/settlement/deductions
     Add a damage deduction to the deposit_deductions table (linked to cash_deposits
     for this booking). Re-triggers calculate automatically to update totals.
     Body: { description, amount, category, photo_url? }
     Transitions: calculated → draft → recalculate (deductions update invalidates calc)
     Auth: checkout, ops, admin.

DELETE /worker/bookings/{booking_id}/settlement/deductions/{deduction_id}
       Remove a damage deduction. Re-triggers calculate.
       Auth: checkout, ops, admin.

POST /worker/bookings/{booking_id}/settlement/finalize
     Lock the settlement. Writes finalized_by, finalized_at, transitions to finalized.
     Also triggers cash_deposits.status = 'returned' with the refund_amount
     (or 'forfeited' if refund_amount = 0 and retained_amount > 0).
     Auth: ops, admin only.
     Body: { notes? }

POST /admin/bookings/{booking_id}/settlement/void
     Void a non-finalized settlement. Requires void_reason.
     Auth: admin only.
     Body: { void_reason }
```

### Admin Read Endpoints (Phase 961)

```
GET  /admin/bookings/{booking_id}/settlement
     Full settlement view: all fields + deductions breakdown + meter readings.
     Auth: admin, manager.

GET  /admin/properties/{property_id}/settlements
     List all settlement records for the property.
     Filters: ?status=draft|calculated|finalized|voided
     Auth: admin, manager.
```

---

## 4. Role Access Matrix

| Endpoint | admin | manager | ops | checkout/checkin | owner |
|---|---|---|---|---|---|
| POST closing-meter | ✅ | ❌ | ✅ | ✅ | ❌ |
| POST settlement/start | ✅ | ❌ | ✅ | ✅ | ❌ |
| POST settlement/calculate | ✅ | ❌ | ✅ | ✅ | ❌ |
| POST settlement/deductions | ✅ | ❌ | ✅ | ✅ checkout | ❌ |
| DELETE settlement/deductions | ✅ | ❌ | ✅ | ✅ checkout | ❌ |
| POST settlement/finalize | ✅ | ❌ | ✅ | ❌ | ❌ |
| POST settlement/void | ✅ | ❌ | ❌ | ❌ | ❌ |
| GET settlement (admin) | ✅ | ✅ | ❌ | ❌ | ❌ |
| GET settlements by property | ✅ | ✅ | ❌ | ❌ | ❌ |

---

## 5. Invariants

- `booking_settlement_records` NEVER writes to `event_log`, `booking_state`, or `booking_financial_facts`.
- Electricity `electricity_rate_kwh` is snapshotted at calculate time, not read live at finalize.
- `finalized` records are immutable — no field may ever be updated after status=finalized.
- Finalize triggers `cash_deposits` status update (returned or forfeited) — this is the ONLY cross-table write this router makes.
- All actor IDs (created_by, finalized_by, voided_by) are real user_ids from JWT.
- All mutations write to `admin_audit_log`.

---

## 6. Out of Scope for This Workstream

- `booking_financial_facts` integration — settlement is an operational record, not revenue accounting.
- Owner-facing settlement visibility — owner sees deposit policy only (Phase 954).
- Payout recalculation — settlement retained_amount is an operational fact; payout pipeline is separate.
- SMS/LINE notification on finalization — future workstream.
