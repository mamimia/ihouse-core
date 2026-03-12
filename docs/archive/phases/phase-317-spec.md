# Phase 317 — Supabase RLS Audit II

**Status:** Closed
**Prerequisite:** Phase 316 (Full Test Suite Verification + Fix)
**Date Closed:** 2026-03-12

## Goal

Audit all Supabase tables for RLS coverage. Create missing tables from Phases 296-299 with RLS. Fix all security advisor findings.

## Findings

### Pre-existing tables (33)
All 33 tables already had RLS enabled with proper policies (service_role ALL + tenant-scoped authenticated reads). No changes needed.

### Missing tables (7 — created in this phase)
Tables from Phases 296-299 existed only as SQL artifacts but were never applied to live Supabase.

### Security advisor findings (4 — all fixed)
1. `active_sessions` view — SECURITY DEFINER → changed to SECURITY INVOKER
2. `sync_tenant_org_map` function — mutable search_path → locked to `public`
3. `update_rate_cards_updated_at` function — mutable search_path → locked to `public`
4. `update_task_templates_updated_at` function — mutable search_path → locked to `public`

## Files Changed

| File | Change |
|------|--------|
| Supabase migration `phase317_rls_audit_tables_and_policies` | NEW — 7 tables + trigger + view + RLS enable + 14 policies |
| Supabase migration `phase317_security_advisor_fixes` | NEW — SECURITY INVOKER view + 3 search_path fixes |

## Result

**40 tables total (was 33). All have RLS enabled. 0 security advisor lints. No new code tests (schema-only).**
