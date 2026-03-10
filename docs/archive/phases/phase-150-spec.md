# Phase 150 — iCal VTIMEZONE Support

**Status:** Closed
**Prerequisite:** Phase 149 — RFC 5545 VCALENDAR Compliance Audit
**Date Closed:** 2026-03-10

## Goal

RFC 5545 compliance continuation. When a timezone identifier is known via
`property_channel_map.timezone` (new nullable column), the iCal payload emits a
`VTIMEZONE` component (RFC 5545 §3.6.5) and `TZID`-qualified `DTSTART`/`DTEND`
lines. When the column is absent or NULL, the existing UTC behaviour is unchanged —
zero regression risk to the iCal path used by Hotelbeds, TripAdvisor, and Despegar.

## Invariant

iCal is degraded-mode only — never the primary sync strategy (Phase 135, unchanged).

## Design / Files

| File | Change |
|------|--------|
| `migrations/phase_150_property_channel_map_timezone.sql` | NEW — `ALTER TABLE property_channel_map ADD COLUMN IF NOT EXISTS timezone TEXT` |
| `src/adapters/outbound/ical_push_adapter.py` | MODIFIED — dual templates (`_ICAL_TEMPLATE_UTC`, `_ICAL_TEMPLATE_TZID`), `_VTIMEZONE_BLOCK`, `_build_ical_body()` helper, `timezone: Optional[str]` param on `push()`, PRODID Phase 150, `UTC` constant, `_ICAL_TEMPLATE` backward-compat alias |
| `tests/test_ical_timezone_contract.py` | NEW — 54 contract tests, Groups A-J |
| `tests/test_rfc5545_compliance_contract.py` | MODIFIED — PRODID assertion Phase 149 → Phase 150 (1 line) |
| `tests/test_ical_date_injection_contract.py` | MODIFIED — PRODID assertion Phase 149 → Phase 150 (1 line) |

### Key design decisions

- **VTIMEZONE STANDARD sub-component** uses `TZOFFSETFROM/TZOFFSETTO:+0000` placeholder. DST handling deferred to future phase when real UTC offset data is available.
- **TZID value** is the raw IANA identifier (e.g. `Asia/Bangkok`). iCal consumers use the VTIMEZONE block to validate.
- **`DTSTART;TZID=Asia/Bangkok:20260115T000000`** — midnight local time; `T000000` appended to the YYYYMMDD date string.
- **UTC path unchanged** — `timezone_id=None` or `timezone_id=""` both take the Phase 149 UTC code path.
- **`_ICAL_TEMPLATE` alias** maintained for Phase 149 tests that import the name directly.

## Result

**3890 tests pass, 2 pre-existing SQLite skips (unrelated, unchanged).**
1 new DB column (`property_channel_map.timezone TEXT`). No API surface changes.  
54 new contract tests across Groups A-J.
