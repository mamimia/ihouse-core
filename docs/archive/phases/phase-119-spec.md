# Phase 119 — Reconciliation Inbox API

**Status:** Closed  
**Prerequisite:** Phase 118 — Financial Dashboard API  
**Date Closed:** 2026-03-09

## Goal

Implement a single exception-first reconciliation inbox endpoint (`GET /admin/reconciliation?period=YYYY-MM`) that surfaces only bookings requiring operator attention. An empty inbox means financials are clean for the period. Items are sorted by urgency (Tier C first) and include a human-readable `correction_hint` where inferable.

## Invariants

- Reads from `booking_financial_facts` ONLY — never `booking_state`
- Deduplication: most-recent `recorded_at` per `booking_id`
- Tenant isolation enforced at DB query level
- JWT auth required
- `period` param required, YYYY-MM format — 400 INVALID_PERIOD on bad/missing value
- Sort: Tier C first, then booking_id alphabetically
- A booking with zero flags is NOT included in the response

## Design / Files

| File | Change |
|------|--------|
| `src/api/reconciliation_router.py` | NEW — GET /admin/reconciliation. 4 exception flags, _correction_hint builder, _build_exception_item, _TIER_SORT_ORDER |
| `tests/test_reconciliation_router_contract.py` | NEW — 32 tests, Groups A–L |
| `src/main.py` | MODIFIED — registered reconciliation_router, added "reconciliation" OpenAPI tag |

## Exception Flags

| Flag | Trigger |
|------|---------|
| `RECONCILIATION_PENDING` | lifecycle_status == RECONCILIATION_PENDING |
| `PARTIAL_CONFIDENCE` | source_confidence == PARTIAL |
| `MISSING_NET_TO_PROPERTY` | net_to_property is NULL |
| `UNKNOWN_LIFECYCLE` | lifecycle_status == UNKNOWN |

## Result

**2823 tests pass at closure, 2860 after Phase 120, 2 pre-existing SQLite skips (unrelated).**  
Empty inbox design verified. Correction hints cover all flag combinations.
