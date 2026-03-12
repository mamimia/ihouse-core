# Phase 388 — Access-Link System Foundation

**Status:** Closed
**Prerequisite:** Phase 387 (Mobile Field Staff)
**Date Closed:** 2026-03-13

## Goal

Public token-authenticated pages: guest QR portal, staff invitation, owner onboarding.

## Invariant

Public token pages must never expose PII on invalid/expired tokens — error views only.

## Design / Files

| File | Change |
|------|--------|
| `ihouse-ui/app/(public)/guest/[token]/page.tsx` | NEW — Guest portal UI. Backend endpoint /guest/portal/{token} does NOT exist |
| `ihouse-ui/app/(public)/invite/[token]/page.tsx` | NEW — Staff invitation UI. Backend endpoint /invite/validate/{token} does NOT exist |
| `ihouse-ui/app/(public)/onboard/[token]/page.tsx` | NEW — 3-step onboarding form. Backend endpoints /onboard/validate and /onboard/submit do NOT exist |

## Result

TypeScript 0 errors. All three pages are UI shells only — backend token validation/storage endpoints are not implemented. Pages will always show error/expired view in practice.
