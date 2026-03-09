# Phase 86 — Conflict Detection Layer

**Status:** Closed
**Prerequisite:** Phase 85 — Google Vacation Rentals Adapter
**Date Closed:** 2026-03-09

## Goal

Purely read-only conflict detection that scans `booking_state` and flags booking integrity issues. Never writes. Visibility-only tool.

## Detection Categories

| Kind | Severity | Description |
|---|---|---|
| `DATE_OVERLAP` | ERROR | Two ACTIVE bookings on same property with overlapping dates |
| `MISSING_DATES` | WARNING | ACTIVE booking has no check_in or check_out in state |
| `MISSING_PROPERTY` | ERROR | ACTIVE booking has no property_id (cannot conflict-check) |
| `DUPLICATE_REF` | ERROR | Two bookings share same (provider, reservation_id) pair |

## Data Structures

| Type | Notes |
|---|---|
| `ConflictKind` (Enum) | DATE_OVERLAP / MISSING_DATES / MISSING_PROPERTY / DUPLICATE_REF |
| `ConflictSeverity` (Enum) | ERROR > WARNING |
| `Conflict` (frozen dataclass) | Single detected conflict |
| `ConflictReport` (dataclass) | Full scan result: conflicts, partial, scanned_count, error_count, has_errors |

## Public API

```python
detect_conflicts(db, tenant_id) -> ConflictReport
```

- Never raises — partial=True if DB query fails
- All queries are tenant-scoped
- Results sorted ERROR first
- Duplicate overlap detection: O(n²) per property — acceptable for expected booking volumes

## Design Rules (Locked)

- **No writes** — never calls apply_envelope, never writes to any table
- **Visibility only** — does not block ingestion; purely a reporting surface
- **date overlap** uses exclusive checkout: check_out_a == check_in_b = valid (turnaround day)
- **`_get_field`**: reads top-level column first, falls back to `state_json` (jsonb)

## Files

| File | Change |
|---|---|
| `src/adapters/ota/conflict_detector.py` | NEW — ConflictKind, ConflictSeverity, Conflict, ConflictReport, detect_conflicts |
| `tests/test_conflict_detector_contract.py` | NEW — 58 contract tests (Groups A–I) |

## Result

**920 passed, 2 skipped.**
No Supabase schema changes. No new migrations.
