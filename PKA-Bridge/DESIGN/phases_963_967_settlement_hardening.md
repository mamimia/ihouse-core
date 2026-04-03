# Phases 963–967 — Settlement Model Hardening

## Product Context

Phases 952–962 delivered the initial settlement framework. The business owner has now
clarified five product rules that tighten the model. This document describes the
corrections and each Phase that implements them.

---

## 1. Corrected Product Rules

### Rule 1 — Hard Wizard, Not Warning-Only

If a property has `deposit_enabled=true`, the check-in endpoint **MUST refuse** to
complete without `deposit_collected=true` + valid `deposit_amount`.

If a property has `electricity_enabled=true`, the check-in endpoint **MUST refuse**
to complete without a valid `meter_reading`.

The current warning-only behavior (Phases 957) is replaced with hard 400 rejections.

An explicit admin override path (`force_override=true` + `override_reason`) is the
ONLY way to bypass a required step.

### Rule 2 — Deposit Is Real From Check-in Onward

The check-in endpoint must write **directly to `cash_deposits`** (the real settlement
record). The `checkin_deposit_records` table remains as a secondary operational
audit trail, but `cash_deposits` is the primary record from the moment the worker
submits the check-in wizard.

The old design (worker creates a soft note → admin later formalizes) is eliminated.

### Rule 3 — Auto-Electricity Deduction

When `/settlement/calculate` runs, the system must **automatically create** a
`deposit_deductions` row with `category='electricity'` based on the meter delta
and the property rate. This is not a suggestion — it is an enforced calculation.

The old electricity-only storage on `booking_settlement_records` without writing
a deduction row is replaced.

### Rule 4 — Owner Boundary Is Minimal

Owner sees:
- Whether deposit is enabled and at what amount (Phase 954 — **no change needed**)
- Suggestion history and admin response (Phase 954 — **no change needed**)

Owner does NOT see: settlement records, deductions, meter readings, refund/retain
calculations, electricity math. **Confirmed: already correct in current code.**

### Rule 5 — Admin Full Settlement Record

Admin must see everything in one coherent record. The full record response shape
from Phase 962 (`settlement_history_router.py`) is already correct but needs to
include the structured deduction categories (`electricity`, `damage`, `miscellaneous`)
and add a `miscellaneous_deductions_total` field.

---

## 2. Phase Assignment

| Phase | What Changes | Files Modified |
|---|---|---|
| **963** | Check-in: hard wizard enforcement | `checkin_settlement_router.py` |
| **964** | Check-in: direct `cash_deposits` write | `checkin_settlement_router.py` |
| **965** | DB + checkout: deduction category constraint (`electricity`, `damage`, `miscellaneous`) | Migration + `checkout_settlement_router.py` |
| **966** | Checkout calculate: auto-creates electricity deduction row | `checkout_settlement_router.py` |
| **967** | Settlement history: add `miscellaneous_deductions_total` + structured category breakdown; add `booking_settlement_records.miscellaneous_deductions_total` column | Migration + `settlement_history_router.py` + `checkout_settlement_router.py` |

---

## 3. End-to-End Settlement Schema (Corrected)

### Full Record Model — what admin sees for one booking:

```
settlement:
  id                      UUID
  status                  draft | calculated | finalized | voided
  deposit_held            NUMERIC         — amount physically collected at check-in
  deposit_currency        TEXT
  opening_meter_value     NUMERIC         — kWh on meter at check-in
  closing_meter_value     NUMERIC         — kWh on meter at checkout
  electricity_kwh_used    NUMERIC         — closing − opening
  electricity_rate_kwh    NUMERIC         — snapshotted from property_charge_rules
  electricity_charged     NUMERIC         — kwh_used × rate
  electricity_currency    TEXT
  opening_meter_reading_id  UUID          — linked to electricity_meter_readings row
  closing_meter_reading_id  UUID
  damage_deductions_total   NUMERIC       — sum of deposit_deductions where category='damage'
  miscellaneous_deductions_total NUMERIC  — sum of deposit_deductions where category='miscellaneous'
  total_deductions        NUMERIC         — electricity + damage + miscellaneous
  refund_amount           NUMERIC         — MAX(0, deposit_held − total_deductions)
  retained_amount         NUMERIC         — deposit_held − refund_amount
  created_by              TEXT            — actor who started the settlement
  finalized_by            TEXT            — actor who finalized
  finalized_at            TIMESTAMPTZ
  voided_by / voided_at / void_reason
  created_at / updated_at

booking:
  booking_id, guest_name, check_in, check_out, property_id, status

deposit:
  cash_deposit:           { id, amount, currency, collected_by, collected_at, status }
  checkin_record:          { id, ... } — secondary operational receipt

electricity:
  opening:                { id, meter_value, meter_photo_url, recorded_by, recorded_at }
  closing:                { id, meter_value, meter_photo_url, recorded_by, recorded_at }
  kwh_used, rate_kwh, charged, currency

deductions:
  by_category:
    electricity:          [ { id, description, amount, ... } ]
    damage:               [ { id, description, amount, photo_url, ... } ]
    miscellaneous:        [ { id, description, amount, ... } ]
  total_deductions

charge_rule_at_stay:      { deposit_enabled, deposit_amount, electricity_enabled, rate_kwh, ... }

audit_trail:              [ { action, actor_id, performed_at, details }, ... ]
```

### Deduction Categories (Formal)

| Category | Written by | Description |
|---|---|---|
| `electricity` | **Auto-generated** by `/settlement/calculate`. System-created. Not manually added. |
| `damage` | Worker or ops via `/settlement/deductions`. Requires description + amount. Optional photo. |
| `miscellaneous` | Worker or ops via `/settlement/deductions`. Requires description + amount. |

---

## 4. Check-in Flow (Corrected)

```
Worker arrives at check-in wizard for booking B at property P.

1. Frontend calls GET /worker/bookings/B/charge-config (Phase 953)
   → Response tells the wizard: deposit_enabled=true, amount=5000, electricity_enabled=true

2. Check-in wizard renders required steps:
   ✅ Identity / passport capture (already built)
   ✅ Deposit collection step (if deposit_enabled)
   ✅ Opening meter photo + reading (if electricity_enabled)

3. Worker submits POST /worker/bookings/B/checkin-settlement

   Endpoint behavior (Phase 963):
   a) Reads property_charge_rules for this property
   b) If deposit_enabled=true:
      - REJECT 400 if deposit_collected=false or deposit_amount missing
      - Unless force_override=true + override_reason (admin override)
   c) If electricity_enabled=true:
      - REJECT 400 if meter_reading missing
      - Unless force_override=true + override_reason
   d) On success:
      - Writes to cash_deposits directly (Phase 964) — the real deposit record
      - Writes to checkin_deposit_records — secondary audit trail
      - Writes to electricity_meter_readings (opening)
      - Writes audit events

4. Check-in task transitions to COMPLETED — worker's task surface clears.
```

---

## 5. Checkout Settlement Flow (Corrected)

```
Worker arrives at checkout flow for booking B.

1. Inspect property, capture checkout photos

2. POST /worker/bookings/B/closing-meter (Phase 959)
   - Writes closing reading to electricity_meter_readings

3. POST /worker/bookings/B/settlement/start (Phase 961)
   - Creates draft settlement, reads deposit_held from cash_deposits

4. POST /worker/bookings/B/settlement/calculate (Phase 966)
   - Auto-creates deposit_deductions row with category='electricity'
     if electricity delta > 0 (replaces old behavior of storing only on settlement record)
   - Sums damage + miscellaneous deductions
   - Computes: total_deductions, refund_amount, retained_amount
   - Stores snapshot on booking_settlement_records

5. Optionally: POST /worker/bookings/B/settlement/deductions
   - category: damage | miscellaneous
   - (electricity deductions are auto-created, not manual)

6. POST /worker/bookings/B/settlement/calculate (re-run after adding deductions)
   - Refreshes all totals

7. POST /worker/bookings/B/settlement/finalize (ops/admin only)
   - Locks settlement → finalized
   - Updates cash_deposits status: returned or forfeited
```

---

## 6. Owner Boundary (Confirmed)

| Owner can | Owner cannot |
|---|---|
| See deposit enabled + amount | See settlement records |
| Submit deposit suggestion | See deduction details |
| See suggestion status + admin note | See electricity readings or math |
| | See refund/retain calculations |
| | See damage deductions |
| | See miscellaneous charges |
| | Access any `/admin/` settlement endpoint |

**No code changes needed** — Phase 954 endpoints already enforce this correctly.
