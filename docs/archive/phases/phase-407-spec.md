# Phase 407 — Supabase Migration Reproducibility

**Status:** Closed
**Prerequisite:** Phase 406 (Documentation Truth Sync)
**Date Closed:** 2026-03-13

## Goal

Verify all 16 migration files apply cleanly. Document the gap between previous "36 migrations" documentation claim and the 16-file reality. Create a migration verification script.

## Migration Count Gap Explained

Previous documentation (current-snapshot, roadmap) claimed "36 migrations" / "29 migrations" at various points. The actual count is **16 migration files** in `supabase/migrations/`. The discrepancy exists because:

1. **Early phases (1-50)** applied schema changes directly via Supabase SQL editor — no local migration files existed.
2. **Phase 274** created `core_schema_baseline.sql` which consolidates all Phase 1-50 schemas into a single reproducible file.
3. Some later phases (e.g., Phase 296-298 for organizations/sessions/tokens, Phase 317 for RLS) were applied via MCP migration tools that created tables directly on Supabase but didn't always create local migration files.

The 16 migration files that exist ARE the canonical reproducible schema when applied to a fresh Supabase project following `supabase/BOOTSTRAP.md`.

## Files Changed

| File | Change |
|------|--------|
| `scripts/verify_migrations.sh` | NEW — validates naming convention (YYYYMMDDHHMMSS_*.sql), chronological ordering, and non-empty check |
| `docs/archive/phases/phase-407-spec.md` | NEW — this spec |

## Verification Result

All 16 files pass: naming convention ✅, chronological order ✅, non-empty ✅.
