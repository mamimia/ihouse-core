# Phase 830 — System Re-Baseline + Data Seed + Zero-State Reset

**Status:** Closed
**Prerequisite:** Phase 813 (Git Commit + Push)
**Date Closed:** 2026-03-17

## Goal

Re-baseline the entire iHouse Core system after the Operational Core Wave (Phases A–D), establish truthful closure standards, build comprehensive data seed tooling with full test/demo environment reset capability, prove auth login E2E, define task lifecycle policy, and reset the system to true zero-state for clean intake proofs.

## What was delivered

1. **System Re-Baseline** — Reality audit of all surfaces, wiring, and proofs. Classified every item as: truly proven, render/surface only, code-level only, disconnected/deferred, or truly missing.

2. **Data Seed Script** (`scripts/seed_demo.py`) — Seeds 7 tables (19 rows) covering properties, bookings (6 states), financial facts, tasks, deposits, issues, permissions. Supports `--dry-run`, `--clean`, `--reset-all-test`, and `--reset-all-test-dry-run`.

3. **Full Environment Reset** — `--reset-all-test` deletes ALL test/demo data across 24+ tables in FK-safe leaf-to-root order. 5 guardrails: env guard (blocks on IHOUSE_ENV=production), tenant allowlist (15 prefix patterns), dry-run mode, FK-safe deletion order, post-reset verification. Includes event_log global purge.

4. **Auth Login E2E Proof** — POST /auth/dev-login → JWT → /auth/me → /bookings → /properties → /worker/tasks, all 200 OK.

5. **Task Lifecycle Policy** — Production: no hard delete, use CANCELLED + canceled_reason. Hard delete allowed only in dev/demo reset scripts.

6. **True Zero-State** — System reset to 0 rows across all 16+ tables. Ready for new-customer-like intake proofs.

## Invariant

- Tasks are NEVER hard-deleted in production. Use CANCELLED + canceled_reason.
- `--reset-all-test` NEVER runs when IHOUSE_ENV=production.
- Only tenant_ids matching `_TEST_TENANT_PREFIXES` are deleted by reset.

## Design / Files

| File | Change |
|------|--------|
| `src/scripts/seed_demo.py` | NEW — Comprehensive seed + reset script with 5 guardrails |
| `docs/core/current-snapshot.md` | MODIFIED — Updated to Phase 830 reality |
| `docs/core/work-context.md` | MODIFIED — Updated current/last phase, next objective |
| `docs/core/phase-timeline.md` | MODIFIED — Phase 830 entry appended |
| `docs/core/construction-log.md` | MODIFIED — Phase 830 entry appended |

## Result

- 7 tables seeded, 6 schema mismatches discovered and fixed
- ~15,543 test residue rows deleted across 24+ tables
- Auth login proven E2E (5 endpoints, all 200 OK)
- System at true zero-state (0 rows in all data tables)
- Task lifecycle policy established and approved
