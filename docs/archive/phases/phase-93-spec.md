# Phase 93 — Payment Lifecycle / Revenue State Projection

**Status:** In Progress → To be closed after tests pass
**Prerequisite:** Phase 65-66 (BookingFinancialFacts), Phase 92 (system audit)
**Date:** 2026-03-09

## Goal

Introduce `payment_lifecycle.py` — a read-only financial status state machine
that projects a booking's payment lifecycle state from its `BookingFinancialFacts`
and the canonical envelope type.

## Financial Status States

| State | Meaning |
|-------|---------|
| `GUEST_PAID` | Guest has fully paid the OTA; booking is active |
| `OTA_COLLECTING` | OTA is collecting payment from guest (partial / in progress) |
| `PAYOUT_PENDING` | OTA owes payout to property; not yet released |
| `PAYOUT_RELEASED` | Net payout has been released to property |
| `RECONCILIATION_PENDING` | Mismatch detected; financial data incomplete or contradictory |
| `OWNER_NET_PENDING` | Net-to-owner calculation exists, payout not yet confirmed |
| `UNKNOWN` | Insufficient data to determine state |

## Invariants

- payment_lifecycle.py is READ-ONLY. Zero writes to any data store.
- Does NOT modify booking_state, financial_facts, or any canonical envelope.
- Projection is deterministic: same facts → same state, always.
- All states are derived purely from BookingFinancialFacts + envelope type.
- booking_state must NEVER contain financial calculations (invariant locked Phase 62+).

## Design

```
project_payment_lifecycle(
    financial_facts: BookingFinancialFacts,
    envelope_type: str,          # BOOKING_CREATED | BOOKING_CANCELED | BOOKING_AMENDED
) -> PaymentLifecycleState
```

Rule table:
- BOOKING_CANCELED → always RECONCILIATION_PENDING (funds must be assessed)
- confidence PARTIAL or insufficient data → UNKNOWN
- net_to_property is None, total_price present → PAYOUT_PENDING
- net_to_property present, total_price present → OWNER_NET_PENDING
- confidence FULL, all amounts present → GUEST_PAID

## Files

| File | Change |
|------|--------|
| `src/adapters/ota/payment_lifecycle.py` | NEW |
| `tests/test_payment_lifecycle_contract.py` | NEW |

## Result

**~1720 tests pass, 2 skipped.**
No Supabase schema changes. No new migrations. No booking_state writes.
