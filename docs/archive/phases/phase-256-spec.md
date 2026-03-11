# Phase 256 — Codebase Brand Migration (Customer-Facing Surfaces)

**Status:** Closed
**Prerequisite:** Phase 255 (Documentation Audit + Brand Canonical Placement)
**Date Closed:** 2026-03-11

## Goal

Migrate all customer-facing strings in the backend codebase from "iHouse" to "Domaniqo". Internal identifiers (env vars `IHOUSE_*`, file names, module names, import paths) intentionally left unchanged — iHouse remains the internal codename.

## Invariant

Customer-facing brand = **Domaniqo**. Internal codename = **iHouse Core**. Env vars (`IHOUSE_*`) are internal implementation details and remain unchanged.

## Files Changed

| File | Change |
|------|--------|
| `src/main.py` | MODIFIED — app title: "iHouse Core" → "Domaniqo Core"; logger name: "ihouse-core" → "domaniqo-core"; startup/shutdown log messages updated; OpenAPI description header updated; contact name "iHouse Engineering" → "Domaniqo Engineering"; contact URL → domaniqo.com |
| `tests/test_main_app.py` | MODIFIED — test_app_title assertion updated: "iHouse Core" → "Domaniqo Core" |

## Result

**~5,900 tests pass, 0 failures. Exit 0.**
