# Phase 279 — CI Pipeline Hardening

**Status:** Closed
**Prerequisite:** Phase 278 (Production Environment Configuration)
**Date Closed:** 2026-03-11

## Goal

Harden the existing GitHub Actions CI pipeline to catch issues before they reach production.

## Changes to `.github/workflows/ci.yml`

### Before (Baseline)
| Job | Status |
|-----|--------|
| Test Suite | Python 3.12, runs, exit 0 |
| Lint (ruff) | Non-blocking (`|| true`) — issues logged but never fail CI |
| Smoke | Only when secret is set |

### After (Phase 279)
| Job | Status |
|-----|--------|
| Test Suite | **Python 3.14** (matches Dockerfile), `IHOUSE_DEV_MODE=false` enforced |
| Lint (ruff) | **Blocking** — `E,F,W` subset (ignores E501/E741/W503) |
| **Migrations** | **NEW** — validates SQL files exist, parseable, BOOTSTRAP.md present |
| **Security** | **NEW** — verifies prod template has DEV_MODE=false, .env in dockerignore, no hardcoded secrets |
| Smoke | Requires ALL prior jobs to pass (not just test) |

## Hardening Details

### Python Version Alignment
- Was: `3.12` in CI, `3.14-slim` in Dockerfile → runtime mismatch
- Now: `3.14` in both

### Lint (Blocking)
- Previous: `ruff check src/ || true` — always passed
- Now: `ruff check src/ --select E,F,W --ignore E501,E741,W503`
- Scope: pyflakes (F), pycodestyle errors (E), warnings (W)
- Excluded: E501 (line length — large codebase), E741 (ambiguous names), W503 (stylistic)

### Migration Validation Job (NEW)
1. Verifies `supabase/migrations/*.sql` files ≥ 5 (minimum count guard)
2. Validates each file: non-empty AND contains known SQL keywords
3. Verifies `supabase/BOOTSTRAP.md` exists

### Security Gate Job (NEW)
1. Checks `.env.production.example` does NOT have `IHOUSE_DEV_MODE=true`
2. Scans `src/` for suspicious hardcoded secret patterns
3. Verifies `.env` is listed in `.dockerignore`

### CI Secret Requirements
No new secrets required for the 4 core jobs (test, lint, migrations, security).  
Smoke still requires `IHOUSE_API_KEY` to be set in GitHub repo secrets.
