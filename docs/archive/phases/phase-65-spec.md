# Phase 65 — Financial Data Foundation

**Status:** Closed
**Prerequisite:** Phase 64 (Enhanced Health Check)
**Date Closed:** 2026-03-08

## Goal

Extract and preserve financial data from all 5 OTA provider payloads into a structured, immutable `BookingFinancialFacts` dataclass. No DB writes in this phase.

## Invariant (Locked Phase 62+)

`booking_state` must NEVER contain financial calculations, payout amounts, commission, or owner-net values.
`financial_facts` lives on `NormalizedBookingEvent` only.

## Design

### BookingFinancialFacts

```python
@dataclass(frozen=True)
class BookingFinancialFacts:
    provider: str
    total_price: Optional[Decimal]
    currency: Optional[str]
    ota_commission: Optional[Decimal]
    taxes: Optional[Decimal]
    fees: Optional[Decimal]
    net_to_property: Optional[Decimal]
    source_confidence: str              # FULL | PARTIAL | ESTIMATED
    raw_financial_fields: Dict[str, Any]
```

### source_confidence

| Value | Meaning |
|-------|---------|
| `FULL` | All key financial fields present |
| `PARTIAL` | Some key fields missing / absent |
| `ESTIMATED` | Net or commission was derived (e.g. from commission_percent × total) |

### Provider Field Mapping

| Provider | Source Fields | Confidence |
|----------|--------------|------------|
| Booking.com | `total_price`, `currency`, `commission`, `net` | FULL / PARTIAL |
| Expedia | `total_amount`, `currency`, `commission_percent` | ESTIMATED when derivable |
| Airbnb | `payout_amount`, `booking_subtotal`, `taxes`, `currency` | FULL / PARTIAL |
| Agoda | `selling_rate`, `net_rate`, `currency` | FULL / PARTIAL |
| Trip.com | `order_amount`, `channel_fee`, `currency` | ESTIMATED when derivable |

## Files

| File | Change |
|------|--------|
| `src/adapters/ota/financial_extractor.py` | NEW — BookingFinancialFacts + per-provider extractors |
| `src/adapters/ota/schemas.py` | MODIFIED — `financial_facts: Optional[BookingFinancialFacts] = None` on NormalizedBookingEvent |
| `src/adapters/ota/bookingcom.py` | MODIFIED — `normalize()` calls `extract_financial_facts()` |
| `src/adapters/ota/expedia.py` | MODIFIED — same |
| `src/adapters/ota/airbnb.py` | MODIFIED — same |
| `src/adapters/ota/agoda.py` | MODIFIED — same |
| `src/adapters/ota/tripcom.py` | MODIFIED — same |
| `tests/test_financial_extractor_contract.py` | NEW — 52 contract tests |

## Result

**372 tests pass, 2 skipped.**
No canonical business semantics changed.
No Supabase tables, migrations, or booking_state writes.
