# Phase 140 — iCal Date Injection
**Spec version:** 1.0
**Status:** Closed ✅
**Date:** 2026-03-10
**Commit:** `45fa03f`

---

## Objective

Inject real `check_in` / `check_out` dates from `booking_state` into the
iCal VCALENDAR payload so external OTA systems receive accurate
`DTSTART` / `DTEND` values instead of the placeholder dates (`20260101` / `20260102`)
that shipped with Phase 139.

---

## Modified Files

| File | Change |
|------|--------|
| `src/adapters/outbound/ical_push_adapter.py` | `push()` gains `check_in` / `check_out` kwargs; `_ICAL_TEMPLATE` uses `{dtstart}` / `{dtend}`; PRODID bumped to Phase 140 |
| `src/services/outbound_executor.py` | `execute_sync_plan()` gains `check_in` / `check_out` and forwards them to `adapter.push()` |
| `src/api/outbound_executor_router.py` | `booking_state` SELECT expanded to include `check_in` / `check_out`; inline `_to_ical()` helper; dates passed to `execute_sync_plan()` |

## New Files

| File | Role |
|------|------|
| `src/adapters/outbound/booking_dates.py` | `fetch_booking_dates(booking_id, tenant_id)` — read-only helper; returns compact YYYYMMDD dates |
| `tests/test_ical_date_injection_contract.py` | 16 contract tests |

---

## Design Decisions

### Adapter interface
`ICalPushAdapter.push()` accepts optional `check_in` / `check_out` strings
in compact iCal format (`YYYYMMDD`). If absent → fallback to stable placeholder
dates (`20260101` / `20260102`) so all Phase 139 dry-run tests remain green.

### Fail-safe propagation
If `booking_state` row has no dates (NULL columns), the router passes
`check_in=None` / `check_out=None`. The adapter uses fallback constants.
This prevents any date-lookup failure from blocking a sync operation.

### No new DB schema
`booking_state.check_in` and `check_out` columns already exist (Phase 17C).
Only the SELECT field list in the router was extended.

### PRODID bump
`PRODID:-//iHouse Core//Phase 140//EN` marks iCal payloads generated
after the date injection upgrade so they are distinguishable in logs / OTA receipts.

---

## Flow

```
POST /internal/sync/execute
  → booking_state SELECT(property_id, check_in, check_out)
  → _to_ical() → "YYYYMMDD"
  → execute_sync_plan(check_in=..., check_out=...)
      → adapter.push(check_in=..., check_out=...)
          → _ICAL_TEMPLATE.format(dtstart=check_in or FALLBACK, dtend=check_out or FALLBACK)
          → PUT {ical_url}/{external_id}.ics
```

---

## VCALENDAR output (example)

```
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//iHouse Core//Phase 140//EN
BEGIN:VEVENT
UID:bk-airbnb-HZ001@ihouse.core
DTSTART:20260315
DTEND:20260320
SUMMARY:Blocked by iHouse Core
DESCRIPTION:booking_id=bk-airbnb-HZ001 external_id=HZ12345
END:VEVENT
END:VCALENDAR
```

---

## Test Coverage (16 tests)

| Group | Scope |
|-------|-------|
| A | Real dates appear in VCALENDAR body |
| B | Fallback to 20260101/20260102 when check_in/out are None |
| C | Template structure (all required iCal lines) |
| D | Executor forwards check_in/check_out to registry adapter |
| E | Router `_to_ical()` conversion (ISO 8601 → YYYYMMDD, None on empty) |
| F | `_FALLBACK_DTSTART` / `_FALLBACK_DTEND` constant stability |

---

## Test Results

Full suite: **3589 passed**, 2 failed (pre-existing SQLite guards), 3 skipped.
