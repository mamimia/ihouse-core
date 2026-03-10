# Phase 161 — Financial Correction API (Foundation)

**Date closed:** 2026-03-10  
**Status:** ✅ Closed  
**Tests added:** ~20 contract tests  
**Total after phase:** ~4160 passing

## Goal

Allow operators to submit a manual financial correction for a booking when OTA financial data is wrong or missing. Corrections are written as new `booking_financial_facts` rows with `event_kind='FINANCIAL_CORRECTION'` and a correction_reason field.

## Deliverables

### New Files
- `src/api/financial_correction_router.py` — `POST /financial/{booking_id}/correct` (body: total_price, currency, ota_commission, net_to_property, correction_reason, corrected_by); writes new `booking_financial_facts` row; 404 if booking_id not found in financial facts; JWT required

### Modified Files
- `src/main.py` — financial_correction_router registered

### New Test Files
- `tests/test_financial_correction_contract.py` — ~20 contract tests

## Key Design Decisions
- Corrections are ADDITIVE — new row, not UPDATE. Most-recent row wins in all aggregation queries (established pattern from Phase 66)
- `event_kind='FINANCIAL_CORRECTION'` — distinguishable from `BOOKING_CREATED` / `BOOKING_AMENDED` rows
- `corrected_by` field records which user submitted the correction (from JWT sub claim)
- Source confidence on correction rows is always `FULL` (operator is asserting ground truth)
- Audit trail: every correction appears in the financial history timeline automatically

## Architecture Invariants Preserved
- `apply_envelope` is the only write authority to `booking_state` ✅
- Financial correction is a new `booking_financial_facts` row — never touches `booking_state` ✅
