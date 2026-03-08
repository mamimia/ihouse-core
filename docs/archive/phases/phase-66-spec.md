# Phase 66 — booking_financial_facts Supabase Projection

**Status:** Closed
**Prerequisite:** Phase 65 (Financial Data Foundation — BookingFinancialFacts in memory)
**Date Closed:** 2026-03-08

## Goal

Persist the in-memory `BookingFinancialFacts` extracted in Phase 65 to a dedicated Supabase table after every successful `BOOKING_CREATED` event.

## Invariant (Locked Phase 62+)

`booking_state` must NEVER contain financial data.
`booking_financial_facts` is a **separate projection table** — not a column in `booking_state`.

## Files

| File | Change |
|------|--------|
| `src/adapters/ota/financial_writer.py` | NEW — best-effort writer, always non-raising |
| `src/adapters/ota/service.py` | MODIFIED — calls `write_financial_facts` after BOOKING_CREATED APPLIED |
| `scripts/migrate_phase66_financial_facts.py` | NEW — migration helper |
| `tests/test_financial_writer_contract.py` | NEW — 16 contract tests (all mocked) |

## Supabase Table: booking_financial_facts

Append-only, RLS enabled.

```sql
CREATE TABLE booking_financial_facts (
  id                   BIGSERIAL PRIMARY KEY,
  booking_id           TEXT         NOT NULL,
  tenant_id            TEXT         NOT NULL,
  provider             TEXT         NOT NULL,
  total_price          NUMERIC(12,4),
  currency             CHAR(3),
  ota_commission       NUMERIC(12,4),
  taxes                NUMERIC(12,4),
  fees                 NUMERIC(12,4),
  net_to_property      NUMERIC(12,4),
  source_confidence    TEXT         NOT NULL,   -- FULL | PARTIAL | ESTIMATED
  raw_financial_fields JSONB        NOT NULL DEFAULT '{}',
  event_kind           TEXT         NOT NULL,   -- BOOKING_CREATED | BOOKING_AMENDED
  recorded_at          TIMESTAMPTZ  NOT NULL DEFAULT now()
);
```

Indexes: `ix_bff_booking_id`, `ix_bff_tenant_id`
Policies: `service_role_insert`, `service_role_select`

## financial_writer.py Design

- `write_financial_facts(booking_id, tenant_id, event_kind, facts, client=None)`
- Best-effort only — catches all exceptions, logs to stderr, never raises
- Decimal → str conversion for NUMERIC column compatibility
- Only called when `facts` is not None and `booking_id` is non-empty

## E2E Verification

```
BOOKING_CREATED payload →
  extract_financial_facts("bookingcom", payload) →
  write_financial_facts(booking_id="bookingcom_P66_E2E_001", ...) →
  SELECT * FROM booking_financial_facts WHERE booking_id = 'bookingcom_P66_E2E_001'
  → 1 row: total_price=300.0, currency=EUR, ota_commission=45.0, net_to_property=255.0, source_confidence=FULL ✅
```

## Result

**388 tests pass, 2 skipped.**
No canonical business semantics changed.
No `booking_state` writes.
