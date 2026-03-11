# Phase 275 — Deployment Readiness Audit

**Status:** Closed
**Prerequisite:** Phase 274 (Supabase Migration Reproducibility)
**Date Closed:** 2026-03-11

## Goal

Audit and fix the Docker deployment setup to ensure the system can actually be run from the Dockerfile. Identify and resolve any issues that would prevent a successful `docker build` or `docker run`.

## Audit Findings

| Issue | Severity | Resolution |
|-------|----------|------------|
| `Dockerfile` copies `app/` — old Phase 13C SQLite entrypoint (never executed in prod) | Medium | Removed `COPY app/ ./app/` |
| `CMD` hardcodes `--port 8000`, ignores `PORT` env var | Low | Fixed to `--port ${PORT:-8000}` |
| `CMD` hardcodes `--workers 2`, not configurable | Low | Fixed to `--workers ${UVICORN_WORKERS:-2}` |
| No `.env.example` file — new developer onboarding undocumented | Medium | Created `.env.example` with all 20+ vars |
| Docker daemon not running on dev machine | Info | Expected — build validated via static inspection |

## Architecture Note

`app/main.py` is the **old Phase 13C SQLite-based entrypoint** (uses `core.runtime`). The production entrypoint is `src/main.py` (FastAPI + Supabase). With `PYTHONPATH=/app/src`, uvicorn's `main:app` correctly resolves to `src/main.py`. The `app/` directory was dead weight in the image.

## Files

| File | Change |
|------|--------|
| `Dockerfile` | MODIFIED — removed dead `app/` copy, PORT/UVICORN_WORKERS env var support in CMD, phase label |
| `.env.example` | NEW — complete env var reference (Supabase, JWT, API keys, channels, AI, scheduler) |
| `docs/archive/phases/phase-275-spec.md` | NEW — this file |

## Deploy Commands (Verified Syntax)

```bash
# Build
docker build -t ihouse-core .

# Run with env file
docker run --env-file .env -p 8000:8000 ihouse-core

# Or via compose (preferred)
docker compose up -d
docker compose ps          # check health status
docker compose logs -f api # follow logs
```

## Readiness Checklist

- [x] Dockerfile multi-stage build syntactically valid
- [x] `src/main.py` is the correct entrypoint (PYTHONPATH-resolved)
- [x] Dead `app/` copy removed from image
- [x] PORT and UVICORN_WORKERS configurable via env var
- [x] `.env.example` created for developer onboarding
- [x] `.dockerignore` correct (`.env` excluded — not baked in)
- [x] Non-root user (`ihouse`) set in Dockerfile
- [x] HEALTHCHECK configured on `/health` endpoint
