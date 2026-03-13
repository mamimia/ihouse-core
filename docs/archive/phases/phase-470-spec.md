# Phase 470 — Financial Data Enrichment

**Status:** Closed
**Prerequisite:** Phase 469
**Date Closed:** 2026-03-13

## Goal

Add batch enrichment capability to upgrade PARTIAL confidence financial records to FULL/ESTIMATED by re-running the financial extractor on stored raw_financial_fields. Add confidence monitoring endpoint.

## Design / Files

| File | Change |
|------|--------|
| `src/api/financial_router.py` | MODIFIED — Added POST /financial/enrich (batch enrichment) and GET /financial/confidence-report (confidence distribution) |

## Result

**POST /financial/enrich scans PARTIAL rows, re-extracts, appends FULL/ESTIMATED rows (append-only). GET /financial/confidence-report returns {provider → {FULL: n, PARTIAL: n, ...}} breakdown. Compiles OK.**
