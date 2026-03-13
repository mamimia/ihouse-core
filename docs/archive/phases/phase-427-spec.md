# Phase 427 — Supabase Live Connection Verification

**Status:** Closed
**Prerequisite:** Phase 426 (Full Test Suite Run + Baseline)
**Date Closed:** 2026-03-13

## Goal

Verify the live Supabase connection, confirm all migrations are applied, and validate that the canonical `apply_envelope` RPC function exists and the database schema matches expectations.

## Invariant (if applicable)

All existing invariants preserved. Confirmed: `apply_envelope` is indeed the single canonical write gate in the live database.

## Design / Files

| File | Change |
|------|--------|
| (no files changed) | Verification-only phase |

## Result

**Supabase project `reykggmlcehswrxjviup` — ACTIVE_HEALTHY**

| Metric | Live Value |
|--------|-----------|
| Tables | 43 (all RLS-enabled) |
| Applied migrations | 35 (16 in local repo, rest via SQL editor/MCP) |
| Public functions | 15 (including `apply_envelope`) |
| Events (event_log) | 5,335 |
| Bookings (booking_state) | 1,516 |
| Tenants | 14 |
| Provider capabilities | 14 |
| Properties | 1 |
| Channel mappings | 1 |
| Exchange rates | 26 |

Note: Local repo has 16 migration files but DB has 35 applied. Early phases used SQL editor directly, and Phase 274 baseline consolidated early schemas. This is documented and expected.
