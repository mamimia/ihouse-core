# Phase 337 — Supabase Artifacts Refresh + Schema Audit

**Status:** Closed
**Prerequisite:** Phase 336 (Layer C Documentation Sync XVIII)
**Date Closed:** 2026-03-12

## Goal

Audit the Supabase schema against the live database and refresh local artifacts. Verify all tables have RLS enabled.

## Invariant

`artifacts/supabase/schema.sql` must be the canonical reference for all Supabase tables. It must match the live database schema.

## Design / Files

| File | Change |
|------|--------|
| `artifacts/supabase/schema.sql` | Added 7 missing table DDL from Phases 296-299 (organizations, org_members, tenant_org_map, user_sessions, guest_tokens, owner_portal_access, notification_log) |
| `docs/core/roadmap.md` | Updated Supabase Tables from "33 tables + 1 view" to "40 tables + 2 views" |
| `docs/core/current-snapshot.md` | Updated Supabase table count references |

## Audit Results

- **Live tables:** 40 (all `rls_enabled: true` ✅)
- **Local schema.sql before:** 33 tables (missing 7 from Phases 296-299)
- **Local schema.sql after:** 40 tables ✅
- **Views:** 2 (`ota_dlq_summary`, `active_sessions`)
- **Migrations:** 29 (6 local files covering 29 DDL operations)
- **RLS audit:** PASS — all 40 tables have RLS enabled

## Result

**0 tests added. Schema audit + documentation update. schema.sql is now synchronized with live Supabase.**
