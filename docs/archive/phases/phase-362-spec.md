# Phase 362 — Webhook Retry & DLQ Dashboard Enhancement

**Status:** Closed
**Prerequisite:** Phase 361 (Test Suite Health & Coverage Gaps)
**Date Closed:** 2026-03-12

## Goal

Enhance the DLQ dashboard with batch replay capability and payload inspection for faster operational triage.

## Design / Files

| File | Change |
|------|--------|
| `ihouse-ui/app/admin/dlq/page.tsx` | MODIFIED — Added batch replay button (▶▶ Replay All) with progress toast, expandable payload preview per entry |

## Features Added

1. **Batch Replay Button** — Processes all pending/error entries sequentially, shows progress ("Replaying 3/12…"), and reports final ok/fail counts via toast notification.
2. **Payload Preview** — Each entry card shows truncated payload preview (first 200 chars). Click to expand/collapse for full view.

## Result

TypeScript: **0 errors**. No regressions.
