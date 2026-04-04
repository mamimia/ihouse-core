# Phase 1063 — Conditional Checkout Flow

**Status:** Implemented  
**Date:** 2026-04-04  
**Commit:** `8673e12`  
**File:** `ihouse-ui/app/(app)/ops/checkout/page.tsx`

---

## Problem

The checkout wizard showed a hardcoded 5-step sequence to every worker for every booking:

```
Inspection → Closing Meter → Issues → Deposit → Summary
```

This was static regardless of:
- Whether the property had electricity billing enabled
- Whether an opening meter reading existed at check-in
- Whether any deposit was collected
- Whether inspection was clean or had issues

A property with no deposit and no electricity billing was forced through the same 5-step flow as a full-feature property.

---

## Solution: `computeStepFlow(baseline)`

A pure function that derives the minimal applicable step sequence from real baseline data returned by `GET /worker/bookings/{id}/checkout-baseline`.

```typescript
function computeStepFlow(baseline): CheckoutStep[] {
    const flow = ['inspection'];
    if (electricity_enabled && has_opening_meter) flow.push('closing_meter');
    flow.push('issues');  // always present; routing gated by inspectionOk
    if (deposit_enabled || has_deposit) flow.push('deposit');
    flow.push('complete');
    return flow;
}
```

### Resulting flows by configuration

| Property config | Step flow |
|---|---|
| Electricity + deposit | `inspection → meter → issues → deposit → complete` (5 steps) |
| Electricity only, no deposit | `inspection → meter → issues → complete` (4 steps) |
| Deposit only, no electricity | `inspection → issues → deposit → complete` (4 steps) |
| Neither (cash-only, no billing) | `inspection → issues → complete` (3 steps) |
| Clean inspection (any config) | Issues step skipped in routing (worker never lands there) |

---

## Gate conditions

### `closing_meter` step included when:
- `charge_rules.electricity_enabled === true` **AND**
- `opening_meter.meter_value !== null` (an opening reading exists from check-in)

### `deposit` step included when:
- `charge_rules.deposit_enabled === true` **OR**
- `baseline.deposit.amount > 0` (actual cash deposit was collected, regardless of config flag)

### `issues` step routing:
- Always in `stepFlow` for back-navigation correctness
- Only reached via forward navigation if `inspectionOk === false`
- Transparent if inspection is clean (worker never sees it)

---

## Changes made

### New function: `computeStepFlow(baseline)`
- Top-level pure function, defined before the component
- Returns `CheckoutStep[]` — the minimal applicable flow for this booking

### New derived state (inside `CheckoutWizard`)
```typescript
const stepFlow = computeStepFlow(baselineLoading ? null : baseline);
const stepNumber = (s) => stepFlow.indexOf(s) + 1;
const totalSteps = stepFlow.length;
```
While baseline is loading, defaults to full 5-step flow (safe fallthrough).

### New `goNext(current)` helper
Returns the next step in `stepFlow` after the given step.
Replaces hardcoded `setStep('deposit')` / `setStep('issues')` calls.

### `goBack()` updated
Uses `['list', ...stepFlow]` instead of hardcoded 5-step array.
Cannot navigate back through a step that was excluded from the flow.

### `StepHeader` step/total
All `step={N} total={5}` usages replaced with `step={stepNumber(s)} total={totalSteps}`.
Progress bar and step indicator always reflect real position in the applicable sequence.

### Closing meter step
- Render guarded: `step === 'closing_meter' && stepFlow.includes('closing_meter')`
- `onSkip` updated to use `goNext('closing_meter')` not hardcoded `'deposit'`
- `saveClosingMeter` skip path uses `goNext('closing_meter')`

### Deposit step
- Render guarded: `step === 'deposit' && stepFlow.includes('deposit')`

### Inspection continue button
- Label adapts: `Continue → Meter` / `Continue → Deposit` / `Continue → Summary`
- Target adapts via `goNext('inspection')` or `'issues'` for issues-found path

### Issues continue button
- Label adapts: `Continue → Deposit Resolution` / `Continue → Summary`
- Uses `goNext('issues')`

### `CheckoutBaseline` type
- `charge_rules` expanded to include `deposit_enabled`, `deposit_amount`, `deposit_currency`
- These fields already exist in the backend response since Phase 993 — no backend change required

---

## Backend changes

**None.** The `/checkout-baseline` endpoint already returns `charge_rules.deposit_enabled` and `charge_rules.electricity_enabled` since Phase 993. The frontend was simply not using them for flow gating.

---

## What remains open

1. **Property-level checkout notes / checklist configuration** — some properties may have specific checkout steps (e.g. collect key, check pool cover, lock gate). These are not yet modelled in config. When a `checkout_checklist` field is added to property config, `computeStepFlow` can expand to include those steps.

2. **Issue step visibility for clean inspections** — currently, if inspection is clean, the issues step is silently skipped. A future pass could add a brief "No issues? Confirm." screen as an explicit checkpoint for properties where issue-reporting is mandatory.

3. **Damage photos in the issue flow** — the issue form exists but does not yet prompt for a photo of the damage inline. This is acceptable for now but degrades evidence quality.
