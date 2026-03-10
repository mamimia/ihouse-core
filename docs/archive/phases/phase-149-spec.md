# Phase 149 — RFC 5545 VCALENDAR Compliance Audit

**Status:** Closed  
**Prerequisite:** Phase 148 (Sync Result Webhook Callback)  
**Date Closed:** 2026-03-10

## Goal

Audit the iCal VCALENDAR payload emitted by `ICalPushAdapter` against RFC 5545 and add all
missing required fields. The payload previously lacked `CALSCALE`, `METHOD`, `DTSTAMP`, and
`SEQUENCE`, making it technically non-compliant with the standard.

## Invariant

`DTSTAMP` is generated at push time using `datetime.now(tz=timezone.utc)` — it is a creation
timestamp, not a booking date. `SEQUENCE:0` is hardcoded because iHouse always pushes complete
replacement payloads; amendment increment is not attempted in this phase.

## Design / Files

| File | Change |
|------|--------|
| `src/adapters/outbound/ical_push_adapter.py` | MODIFIED — added `from datetime import datetime, timezone`; `_ICAL_TEMPLATE` gains `CALSCALE:GREGORIAN`, `METHOD:PUBLISH`, `DTSTAMP:{dtstamp}`, `SEQUENCE:0`; PRODID bumped to Phase 149; `push()` computes `dtstamp` via `datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")` |
| `tests/test_rfc5545_compliance_contract.py` | NEW — 37 contract tests (Groups A–J): VCALENDAR header, VEVENT fields, DTSTAMP UTC format, SEQUENCE:0, CALSCALE/METHOD positioning, CRLF line endings, BEGIN/END nesting, injected dates, template smoke |
| `tests/test_ical_date_injection_contract.py` | MODIFIED — PRODID assertion updated Phase 140 → Phase 149 (1 line) |

### Fields added to `_ICAL_TEMPLATE`

| Field | RFC 5545 | Position |
|-------|----------|----------|
| `CALSCALE:GREGORIAN` | §3.7.1 | VCALENDAR header (before BEGIN:VEVENT) |
| `METHOD:PUBLISH` | §3.7.2 | VCALENDAR header (before BEGIN:VEVENT) |
| `DTSTAMP:YYYYMMDDTHHMMSSZ` | §3.8.7.2 | VEVENT (UTC, generated at push time) |
| `SEQUENCE:0` | §3.8.7.4 | VEVENT |

## Result

**3836 tests pass, 2 pre-existing SQLite skips (unrelated).**
No DB schema changes. No new API routes.
