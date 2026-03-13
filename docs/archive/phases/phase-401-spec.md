# Phase 401 — Invite Flow Backend

**Status:** Closed
**Prerequisite:** Phase 399 (Access Token System)
**Date Closed:** 2026-03-13

## Goal

Build invite flow: create, validate, accept. Fixed UI deception where the accept button was `setAccepted(true)` with no backend call.

## Design / Files

| File | Change |
|------|--------|
| `src/api/invite_router.py` | NEW — POST /admin/invites, GET /invite/validate/{token}, POST /invite/accept/{token} |
| `tests/test_invite_flow.py` | NEW — 6 contract tests |
| `ihouse-ui/app/(public)/invite/[token]/page.tsx` | MODIFIED — accept button calls real POST endpoint |
| `src/main.py` | MODIFIED — router registration |

## Result

**6 tests pass, 0 skipped.**
