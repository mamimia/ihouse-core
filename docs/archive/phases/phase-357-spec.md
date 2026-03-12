# Phase 357 — Supabase Schema Truth Sync II (Closed) — 2026-03-12

## Category
🗄️ Schema Audit / Documentation

## Objective
Cross-check `artifacts/supabase/schema.sql` against all `.table()` calls in `src/` to identify
tables used in code but absent from the schema export.

## Audit Method
```
grep -rh '.table("' src/ --include="*.py" | extract table names | sort -u
```

## Tables Missing from Schema (Found in Code)
All 4 were referenced in multiple source files but completely absent from schema.sql:

| Table | Phase | Used In |
|-------|-------|---------|
| `admin_audit_log` | 171 | `admin_router.py`, `conflict_resolution_writer.py` |
| `booking_guest_link` | 194 | `task_router.py` |
| `conflict_resolution_queue` | 207 | `conflict_resolution_writer.py` |
| `properties` | 165 | `properties_router.py`, `onboarding_router.py`, `ai_context_router.py`, +4 others |

## Changes Made
- `artifacts/supabase/schema.sql` — header updated (Phase 284 → 357), table count 34 → 44
- 4 CREATE TABLE IF NOT EXISTS definitions appended with correct column shapes

## No Code Changes
Schema.sql is documentation/reference only. No migrations created (tables likely already exist
in live Supabase from earlier phases that didn't update the schema export).
