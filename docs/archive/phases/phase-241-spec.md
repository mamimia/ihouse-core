# Phase 241 — Booking Financial Reconciliation Dashboard API

**Status:** Closed
**Prerequisite:** Phase 240 (Documentation Integrity Sync)
**Date Closed:** 2026-03-11

## Goal

Expose a cross-provider aggregate view of the system's reconciliation health. Unlike the per-month exception inbox (`GET /admin/reconciliation?period=YYYY-MM`), the dashboard aggregates all findings across all providers to give a system-wide health overview.

## Design

New endpoint: `GET /admin/reconciliation/dashboard`

Wraps existing `run_reconciliation()` from `reconciliation_detector.py` (Phase 110). Read-only — never bypasses `apply_envelope`. Groups findings by provider with severity tiers (HIGH ≥ 3, MEDIUM 1-2, OK 0).

Response fields: `tenant_id`, `generated_at`, `total_bookings_checked`, `total_findings`, `critical_count`, `warning_count`, `info_count`, `findings_by_kind`, `by_provider` (sorted worst-first), `partial`.

## Files

| File | Change |
|------|--------|
| `src/api/admin_reconciliation_router.py` | NEW — GET /admin/reconciliation/dashboard |
| `src/main.py` | MODIFIED — registered admin_reconciliation_router (Phase 241) |
| `tests/test_reconciliation_dashboard_contract.py` | NEW — 28 contract tests |

## Result

**~5,587 tests pass. 0 failures. Exit 0.**
28 new contract tests (5 groups: shape, clean tenant, findings, severity unit, auth).
