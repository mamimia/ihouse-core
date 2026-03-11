# Phase 274 — Supabase Migration Reproducibility

**Status:** Closed
**Prerequisite:** Phase 273 (Documentation Integrity Sync XIII)
**Date Closed:** 2026-03-11

## Goal

Make the Supabase database reproducible from scratch. Before this phase, there was no single authoritative migration sequence — a fresh Supabase project could not be bootstrapped without manual steps and tribal knowledge.

## Problem

| Area | State Before Phase 274 |
|------|------------------------|
| Core tables (event_log, booking_state, etc.) | Defined only in `artifacts/supabase/schema.sql` — not in a migration file |
| Application tables (properties, workers, etc.) | 8 SQL files in `migrations/` — non-timestamped, no order guarantee |
| Bootstrap documentation | None — no single guide explaining the full sequence |

## Solution

1. **Created** `supabase/migrations/20260311220000_phase274_core_schema_baseline.sql` — canonical, idempotent baseline migration covering all 10 core tables from Phases 1-50, including the `event_kind` enum, all indexes, constraints, and seed data for `event_kind_registry`.

2. **Created** `supabase/BOOTSTRAP.md` — complete 3-step bootstrap sequence: core baseline → app tables → timestamped migrations.

## Files

| File | Change |
|------|--------|
| `supabase/migrations/20260311220000_phase274_core_schema_baseline.sql` | NEW — core schema baseline |
| `supabase/BOOTSTRAP.md` | NEW — bootstrap guide |
| `docs/archive/phases/phase-274-spec.md` | NEW — this file |

## What This Enables

- Any developer can bootstrap a fresh Supabase project with a documented, ordered sequence
- CI/CD can validate migrations exist for all tables
- Phase 277 (Schema Alignment Verification) can now run against the documented baseline

## Invariant

`apply_envelope` RPC function is NOT included in the migration file (it's too complex for standard migration tooling and must be applied via Supabase SQL editor). The BOOTSTRAP.md documents this step explicitly.
