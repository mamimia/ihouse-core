# Phase 247 — Guest Feedback Collection API

**Status:** Closed
**Prerequisite:** Phase 246 (Rate Card & Pricing Rules Engine)
**Date Closed:** 2026-03-11

## Goal

Close the guest communication loop by collecting structured post-stay feedback.
No JWT required for guest submission — controlled by a per-booking verification token.

## New Table

**`guest_feedback`** (migration: `20260311165100_phase247_guest_feedback.sql`)

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | auto-generated |
| booking_id | TEXT | links to booking |
| tenant_id | TEXT | RLS scoped |
| property_id | TEXT | denormalized for admin queries |
| rating | SMALLINT | 1–5, CHECK constraint |
| category | TEXT | nullable (cleanliness, location, value...) |
| comment | TEXT | nullable free-text |
| submitted_at | TIMESTAMPTZ | auto now() |
| verification_token | TEXT | UNIQUE — one-use token |
| token_used | BOOLEAN | idempotency guard |

Unique index on `verification_token`. RLS enabled.

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/guest-feedback/{booking_id}` | None (token-gated) | Submit feedback |
| `GET` | `/admin/guest-feedback` | JWT | Aggregated feedback + NPS |

## NPS

- Rating 5 = Promoter, 4 = Passive, 1–3 = Detractor
- `NPS = (Promoters − Detractors) / Total × 100` (−100 to +100)

## Files

| File | Change |
|------|--------|
| `supabase/migrations/20260311165100_phase247_guest_feedback.sql` | NEW |
| `src/api/guest_feedback_router.py` | NEW |
| `src/main.py` | MODIFIED — registered guest_feedback_router |
| `tests/test_guest_feedback_contract.py` | NEW — 30 contract tests (9 groups) |

## Result

**~5,760 tests pass. 0 failures. Exit 0.**
30 new contract tests across 9 groups.
