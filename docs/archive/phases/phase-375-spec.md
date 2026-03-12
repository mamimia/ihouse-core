# Phase 375 — Route Group Split

**Status:** Closed
**Prerequisite:** Phase 374 (Platform Checkpoint XIX)
**Date Closed:** 2026-03-13

## Goal

Split the Next.js app into `(public)/` and `(app)/` route groups to separate public-facing and authenticated surfaces. Root layout stripped to a minimal shell.

## Design / Files

| File | Change |
|------|--------|
| `ihouse-ui/app/(public)/layout.tsx` | NEW — Public layout (no sidebar) |
| `ihouse-ui/app/(app)/layout.tsx` | NEW — Protected layout with AdaptiveShell |
| `ihouse-ui/app/layout.tsx` | MODIFIED — Stripped to minimal shell (html/body only) |
| `ihouse-ui/app/(public)/login/page.tsx` | MOVED — From app/login/ |

## Result

TypeScript 0 errors. Route groups established.
