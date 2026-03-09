# Phase 110 — OTA Reconciliation Implementation

**Status:** Closed
**Prerequisite:** Phase 109 (Booking Date Range Search)
**Date Closed:** 2026-03-09

## Goal

Implement the detection engine for the reconciliation layer defined in Phase 89 (discovery-only). Build `GET /admin/reconciliation` API endpoint that exposes the offline reconciliation report to operators.

## Invariant (locked Phase 89, confirmed Phase 110)

- The reconciliation layer is **read-only** — it reads `booking_state` and `booking_financial_facts` only.
- It may **never** write to any table.
- Correction requires a new canonical event through POST /webhooks/{provider}.
- No live OTA API calls.

## Design / Files

| File | Change |
|------|--------|
| `src/adapters/ota/reconciliation_detector.py` | NEW — Detection engine: `run_reconciliation()`, `_detect_financial_facts_missing()`, `_detect_stale_bookings()`. Reads booking_state + booking_financial_facts. |
| `src/api/admin_router.py` | MODIFIED — Phase 110 added to docstring + `GET /admin/reconciliation` endpoint added |
| `tests/test_reconciliation_detector_contract.py` | NEW — 27 tests, Groups A–J |

## What is detected (offline — no OTA API)

| Finding Kind | Description | Severity |
|---|---|---|
| `FINANCIAL_FACTS_MISSING` | Booking in booking_state has no row in booking_financial_facts | WARNING |
| `STALE_BOOKING` | Active booking not updated in > 30 days | INFO |

## What requires live OTA API (deferred)

- `BOOKING_MISSING_INTERNALLY` — OTA has booking we don't have
- `BOOKING_STATUS_MISMATCH` — status differs from OTA  
- `DATE_MISMATCH` — dates differ from OTA
- `FINANCIAL_AMOUNT_DRIFT` — amounts differ from OTA
- `PROVIDER_DRIFT` — provider field differs from envelope

## Endpoint Contract

```
GET /admin/reconciliation
  ?include_findings=false  (default — summary only, for performance)
  ?include_findings=true   (inline full findings list)

Auth: Bearer JWT required. sub → tenant_id.

200 → {
  tenant_id, generated_at, total_checked,
  finding_count, critical_count, warning_count, info_count,
  has_critical, has_warnings, top_kind, partial,
  findings: [...] (if include_findings=true)
}
500 → INTERNAL_ERROR on Supabase failure
```

## Test Groups

| Group | What it tests |
|-------|---------------|
| A | Detector: clean tenant (no findings, empty tenant, ISO 8601 timestamp) |
| B | Detector: FINANCIAL_FACTS_MISSING (single, multiple, deterministic finding_id, canceled also flagged) |
| C | Detector: STALE_BOOKING (40 days → stale, canceled not stale, fresh not stale, custom threshold) |
| D | Detector: combined findings, accurate counts (warning/info/critical) |
| E | Detector: edge cases (None updated_at, bad date, DB failure, Z suffix) |
| F | API: summary response fields (include_findings=false by default) |
| G | API: include_findings=true — findings list + record schema |
| H | API: auth guard — 403 on missing JWT |
| I | API: Supabase exception → 500 INTERNAL_ERROR, no leak |
| J | API: tenant_id in response matches authenticated tenant |

## Result

**2464 tests pass, 2 pre-existing SQLite skips.**
No DB schema changes. No migrations. booking_state + booking_financial_facts read-only.
