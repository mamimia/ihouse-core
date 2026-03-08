# Phase 52 Spec — GitHub Actions CI Pipeline

## Objective

Add automated CI that runs the full test suite on every push and pull request,
giving an automatic safety net before any future adapter expansion.

## Status

In Progress

## Rationale

180+ tests exist. Without CI:
- Regressions discovered late (after manual run, if remembered)
- Cannot safely add multiple adapters in parallel
- No merge gate against broken code

Real SaaS companies (Airbnb, Stripe, Booking.com) require passing CI
before any code merges. This is the prerequisite for Phase 53+ (new adapters).

## Scope

### In scope

1. `.github/workflows/ci.yml`
   - Trigger: push + pull_request on all branches
   - Python setup with correct version (3.14)
   - Install dependencies from requirements or pyproject
   - Run: `PYTHONPATH=src pytest tests/ --ignore=tests/invariants -q`
   - (SQLite invariant tests excluded — require IHOUSE_ALLOW_SQLITE=1)

2. E2E tests (Supabase live) — optional/manual only
   - Require SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY secrets
   - Not part of automatic CI run (too expensive for every push)

### Out of scope

- Deployment pipeline
- Docker
- Coverage reporting (Phase 55+ candidate)
- Secret scanning

## CI Test Split

| Suite | Run in CI | Reason |
|-------|-----------|--------|
| Unit + contract tests | ✅ Always | Fast, no external deps |
| E2E live Supabase tests | ❌ Manual only | Requires secrets + live DB |
| SQLite invariant tests | ❌ Excluded | Require IHOUSE_ALLOW_SQLITE=1 |

## Invariants — must not change

- No canonical code touched
- No DB schema changes
- No migration files

## Expected outcome

Green CI badge on every push.
Future adapters: any regression → CI fails immediately.
