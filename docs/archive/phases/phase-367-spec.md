# Phase 367 — Frontend Error Boundary & Offline State

**Status:** Closed  
**Date Closed:** 2026-03-12

## Goal

Add global error boundary and offline connectivity detection to frontend.

## Files

| File | Change |
|------|--------|
| `ihouse-ui/components/ErrorBoundary.tsx` | NEW — React class error boundary with graceful fallback UI |
| `ihouse-ui/components/OfflineBanner.tsx` | NEW — Online/offline event listener with animated red banner |
| `ihouse-ui/components/ClientProviders.tsx` | NEW — Client wrapper composing ErrorBoundary + OfflineBanner |
| `ihouse-ui/app/layout.tsx` | MODIFIED — wrapped children with ClientProviders |

## Result

TypeScript: **0 errors**. No regressions.
